"""
Local Controller

Extends BaseController with device discovery capabilities.
Orchestrates ARP, ICMP, and SNMP scans, merges results, and reports to RC.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pdsno.controllers.base_controller import BaseController
from pdsno.discovery import ARPScanner, ICMPScanner, SNMPScanner
from pdsno.datastore import NIBStore, Device, DeviceStatus, NIBResult
from pdsno.controllers.context_manager import ContextManager
from pdsno.communication.message_format import MessageEnvelope, MessageType
from pdsno.communication.mqtt_client import ControllerMQTTClient


class LocalController(BaseController):
    """
    Local Controller - Device discovery and low-level management.
    
    Responsibilities:
    - Discover devices on assigned subnet
    - Report discoveries to Regional Controller
    - Execute LOW-sensitivity config changes
    - Manage local device state
    """
    
    def __init__(
        self,
        controller_id: str,
        region: str,
        subnet: str,
        context_manager: ContextManager,
        nib_store: NIBStore,
        message_bus=None,
        mqtt_broker: Optional[str] = None,
        mqtt_port: int = 1883,
        key_manager=None  # Phase 6D: Key distribution
    ):
        super().__init__(
            controller_id=controller_id,
            role="local",
            context_manager=context_manager,
            region=region,
            nib_store=nib_store
        )
        
        self.subnet = subnet
        self.message_bus = message_bus
        self.last_scan_devices: Dict[str, Device] = {}  # MAC -> Device
        
        # MQTT client setup
        self.mqtt_client = None
        if mqtt_broker:
            self.mqtt_client = ControllerMQTTClient(
                controller_id=controller_id,
                broker_host=mqtt_broker,
                broker_port=mqtt_port
            )
            self.logger.info(f"MQTT client configured for broker {mqtt_broker}:{mqtt_port}")
        
        # Phase 6D: Key distribution (optional)
        self.key_manager = key_manager
        self.key_protocol = None
        if key_manager:
            from pdsno.security.key_distribution import KeyDistributionProtocol
            self.key_protocol = KeyDistributionProtocol(controller_id, key_manager)
            self.logger.info("Key distribution protocol initialized")
        
        self.logger.info(f"Local Controller {controller_id} initialized for subnet {subnet}")
    
    def run_discovery_cycle(self, regional_controller_id: Optional[str] = None) -> Dict:
        """
        Execute a complete discovery cycle.
        
        Steps:
        1. Run ARP scan to discover MAC addresses
        2. Run ICMP scan on discovered IPs
        3. Run SNMP scan for enrichment
        4. Merge results by MAC address
        5. Detect deltas (new/updated/inactive devices)
        6. Write to NIB
        7. Send discovery report to RC
        
        Returns:
            Discovery cycle summary
        """
        self.logger.info(f"Starting discovery cycle for subnet {self.subnet}")
        cycle_start = datetime.now(timezone.utc)
        
        # Step 1: ARP Scan
        arp_scanner = ARPScanner()
        arp_result = self.run_algorithm(arp_scanner, {'subnet': self.subnet})
        arp_devices = arp_result.get('devices', [])
        
        self.logger.info(f"ARP scan found {len(arp_devices)} devices")
        
        if not arp_devices:
            self.logger.info("No devices found in ARP scan, cycle complete")
            return {
                "status": "complete",
                "devices_found": 0,
                "new_devices": 0,
                "updated_devices": 0,
                "inactive_devices": 0
            }
        
        # Step 2: ICMP Scan (only on discovered IPs)
        ip_list = [d['ip'] for d in arp_devices]
        icmp_scanner = ICMPScanner()
        icmp_result = self.run_algorithm(icmp_scanner, {'ip_list': ip_list})
        icmp_devices = {d['ip']: d for d in icmp_result.get('devices', [])}
        
        self.logger.info(f"ICMP scan: {len(icmp_devices)}/{len(ip_list)} reachable")
        
        # Step 3: SNMP Scan (optional enrichment)
        snmp_scanner = SNMPScanner()
        snmp_result = self.run_algorithm(snmp_scanner, {'ip_list': ip_list})
        snmp_devices = {d['ip']: d for d in snmp_result.get('devices', [])}
        
        self.logger.info(f"SNMP scan: {len(snmp_devices)}/{len(ip_list)} responded")
        
        # Step 4: Merge results by MAC
        merged_devices = self._merge_scan_results(arp_devices, icmp_devices, snmp_devices)
        
        # Step 5: Detect deltas
        delta = self._detect_deltas(merged_devices)
        
        # Step 6: Write to NIB
        self._write_devices_to_nib(merged_devices)
        
        # Step 7: Send discovery report to RC (if message bus connected)
        if regional_controller_id and self.message_bus:
            self._send_discovery_report(regional_controller_id, delta)
        
        cycle_duration = (datetime.now(timezone.utc) - cycle_start).total_seconds()
        
        summary = {
            "status": "complete",
            "cycle_duration_seconds": cycle_duration,
            "devices_found": len(merged_devices),
            "new_devices": len(delta['new']),
            "updated_devices": len(delta['updated']),
            "inactive_devices": len(delta['inactive']),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self.logger.info(
            f"Discovery cycle complete: {summary['devices_found']} devices, "
            f"{summary['new_devices']} new, {summary['updated_devices']} updated, "
            f"{summary['inactive_devices']} inactive in {cycle_duration:.2f}s"
        )
        
        return summary
    
    def _merge_scan_results(
        self,
        arp_devices: List[Dict],
        icmp_devices: Dict[str, Dict],
        snmp_devices: Dict[str, Dict]
    ) -> List[Dict]:
        """
        Merge results from all three scanners by MAC address.
        
        Returns:
            List of merged device dicts with all available data
        """
        merged = []
        
        for arp_dev in arp_devices:
            ip = arp_dev['ip']
            mac = arp_dev['mac']
            
            # Start with ARP data
            device = {
                'ip': ip,
                'mac': mac,
                'last_seen': arp_dev['timestamp']
            }
            
            # Add ICMP data if available
            if ip in icmp_devices:
                device['reachable'] = True
                device['rtt_ms'] = icmp_devices[ip].get('rtt_ms')
            else:
                device['reachable'] = False
            
            # Add SNMP data if available
            if ip in snmp_devices:
                snmp = snmp_devices[ip]
                device['hostname'] = snmp.get('hostname')
                device['vendor'] = snmp.get('vendor')
                device['model'] = snmp.get('model')
                device['uptime_seconds'] = snmp.get('uptime_seconds')
            
            merged.append(device)
        
        return merged
    
    def _detect_deltas(self, current_devices: List[Dict]) -> Dict:
        """
        Detect changes since last scan.
        
        Returns:
            {
                'new': [...],        # Devices not in last scan
                'updated': [...],    # Devices with changed attributes
                'inactive': [...],   # Devices from last scan not in current scan
                'unchanged': [...]   # Devices with no changes
            }
        """
        current_by_mac = {d['mac']: d for d in current_devices}
        
        new = []
        updated = []
        unchanged = []
        
        # Check current devices against last scan
        for mac, device in current_by_mac.items():
            if mac not in self.last_scan_devices:
                new.append(device)
            else:
                # Compare attributes (simplified - just check IP for now)
                last_device = self.last_scan_devices[mac]
                if device['ip'] != last_device.ip_address:
                    updated.append(device)
                else:
                    unchanged.append(device)
        
        # Check for devices that disappeared
        inactive = []
        for mac, last_device in self.last_scan_devices.items():
            if mac not in current_by_mac:
                inactive.append({
                    'mac': mac,
                    'ip': last_device.ip_address,
                    'hostname': last_device.hostname
                })
        
        return {
            'new': new,
            'updated': updated,
            'inactive': inactive,
            'unchanged': unchanged
        }
    
    def _write_devices_to_nib(self, devices: List[Dict]):
        """Write discovered devices to NIB"""
        for dev_dict in devices:
            # Convert to Device model
            device = Device(
                device_id="",  # Will be assigned by NIB
                ip_address=dev_dict['ip'],
                mac_address=dev_dict['mac'],
                hostname=dev_dict.get('hostname'),
                vendor=dev_dict.get('vendor'),
                device_type=dev_dict.get('model'),
                status=DeviceStatus.ACTIVE if dev_dict.get('reachable') else DeviceStatus.QUARANTINED,
                last_seen=datetime.fromisoformat(dev_dict['last_seen']),
                managed_by_lc=self.controller_id,
                region=self.region,
                metadata={
                    'rtt_ms': dev_dict.get('rtt_ms'),
                    'uptime_seconds': dev_dict.get('uptime_seconds')
                }
            )
            
            # Upsert device (will handle new vs update automatically)
            result = self.nib_store.upsert_device(device)
            
            if not result.success:
                self.logger.warning(
                    f"Failed to write device {dev_dict['mac']} to NIB: {result.error}"
                )
            else:
                # Update last_scan_devices for delta detection next cycle
                self.last_scan_devices[dev_dict['mac']] = device
    
    def _send_discovery_report(self, rc_id: str, delta: Dict):
        """Send delta-only discovery report to Regional Controller"""
        # Only send if there are changes
        if not (delta['new'] or delta['updated'] or delta['inactive']):
            self.logger.debug("No changes to report to RC")
            return
        
        payload = {
            "lc_id": self.controller_id,
            "subnet": self.subnet,
            "region": self.region,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "new_devices": delta['new'],
            "updated_devices": delta['updated'],
            "inactive_devices": delta['inactive']
        }
        
        self.logger.info(
            f"Sending discovery report to {rc_id}: "
            f"{len(delta['new'])} new, {len(delta['updated'])} updated, "
            f"{len(delta['inactive'])} inactive"
        )
        
        # Try MQTT first if available
        if self.mqtt_client and self.mqtt_client.connected:
            topic = f"pdsno/discovery/{self.region}/{self.controller_id}"
            success = self.mqtt_client.publish(
                topic=topic,
                message_type=MessageType.DISCOVERY_REPORT,
                payload=payload,
                qos=1
            )
            if success:
                self.logger.debug(f"Discovery report published to MQTT topic {topic}")
                return
            else:
                self.logger.warning("MQTT publish failed, falling back to message bus")
        
        # Fall back to message bus
        try:
            self.message_bus.send(
                sender_id=self.controller_id,
                recipient_id=rc_id,
                message_type=MessageType.DISCOVERY_REPORT,
                payload=payload
            )
        except Exception as e:
            self.logger.error(f"Failed to send discovery report: {e}")
    
    def connect_mqtt(self) -> bool:
        """Connect to MQTT broker"""
        if not self.mqtt_client:
            raise RuntimeError("MQTT client not configured")
        
        return self.mqtt_client.connect()
    
    def disconnect_mqtt(self):
        """Disconnect from MQTT broker"""
        if self.mqtt_client:
            self.mqtt_client.disconnect()
    
    def subscribe_to_policy_updates(self):
        """
        Subscribe to policy updates from RC.
        
        Listens on: pdsno/policy/{region}
        """
        if not self.mqtt_client:
            raise RuntimeError("MQTT client not configured")
        
        topic = f"pdsno/policy/{self.region}"
        
        self.mqtt_client.subscribe(
            topic,
            self._handle_policy_update,
            qos=1
        )
        
        self.logger.info(f"Subscribed to policy updates on {topic}")
    
    def _handle_policy_update(self, envelope: MessageEnvelope):
        """Handle policy update from RC"""
        self.logger.info(f"Policy update received from {envelope.sender_id}")
        
        policy = envelope.payload
        
        # Store policy in context
        self.update_context({'region_policy': policy})