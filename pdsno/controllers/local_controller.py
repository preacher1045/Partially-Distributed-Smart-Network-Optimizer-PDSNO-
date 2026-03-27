# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""
Local Controller

Extends BaseController with device discovery capabilities.
Orchestrates ARP, ICMP, and SNMP scans, merges results, and reports to RC.
"""

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pdsno.controllers.base_controller import BaseController
from pdsno.discovery import ARPScanner, ICMPScanner, SNMPScanner
from pdsno.datastore import NIBStore, Device, DeviceStatus, Config, ConfigStatus, Event
from pdsno.datastore.models import ConfigCategory
from pdsno.controllers.context_manager import ContextManager
from pdsno.communication.message_format import MessageEnvelope, MessageType
from pdsno.communication.mqtt_client import ControllerMQTTClient
from pdsno.config import (
    ApprovalWorkflowEngine,
    ConfigSensitivityClassifier,
    ExecutionToken,
    ExecutionTokenManager,
    SensitivityLevel,
)


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
        http_client=None,
        simulate: bool = False,
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
        self.http_client = http_client
        self.simulate = simulate
        self.last_scan_devices: Dict[str, Device] = {}  # MAC -> Device

        self.sensitivity_classifier = ConfigSensitivityClassifier()
        self.approval_engine = ApprovalWorkflowEngine(
            controller_id=controller_id,
            controller_role="local",
            nib_store=nib_store,
        )
        self.execution_token_manager = ExecutionTokenManager(
            controller_id=controller_id,
            shared_secret=self._load_execution_shared_secret(),
        )
        
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
        arp_result = self.run_algorithm(
            arp_scanner,
            {'subnet': self.subnet, 'simulate': self.simulate}
        )
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
        icmp_result = self.run_algorithm(
            icmp_scanner,
            {'ip_list': ip_list, 'simulate': self.simulate}
        )
        icmp_devices = {d['ip']: d for d in icmp_result.get('devices', [])}
        
        self.logger.info(f"ICMP scan: {len(icmp_devices)}/{len(ip_list)} reachable")
        
        # Step 3: SNMP Scan (optional enrichment)
        snmp_scanner = SNMPScanner()
        snmp_result = self.run_algorithm(
            snmp_scanner,
            {'ip_list': ip_list, 'simulate': self.simulate}
        )
        snmp_devices = {d['ip']: d for d in snmp_result.get('devices', [])}
        
        self.logger.info(f"SNMP scan: {len(snmp_devices)}/{len(ip_list)} responded")
        
        # Step 4: Merge results by MAC
        merged_devices = self._merge_scan_results(arp_devices, icmp_devices, snmp_devices)
        
        # Step 5: Detect deltas
        delta = self._detect_deltas(merged_devices)
        
        # Step 6: Write only changed devices to NIB
        changed_devices = delta['new'] + delta['updated']
        self._write_devices_to_nib(changed_devices)
        
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
                'last_seen': arp_dev['timestamp'],
                'protocol': arp_dev.get('protocol', 'ARP')
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

            if ip in snmp_devices:
                device['discovery_method'] = 'snmp'
            elif ip in icmp_devices:
                device['discovery_method'] = 'icmp'
            else:
                device['discovery_method'] = 'arp'
            
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
                # Compare core and enrichment/status fields so late-arriving
                # SNMP details or reachability transitions are persisted.
                last_device = self.last_scan_devices[mac]
                current_snapshot = (
                    device.get('ip'),
                    device.get('hostname'),
                    device.get('vendor'),
                    device.get('model'),
                    device.get('reachable'),
                    device.get('discovery_method')
                )
                last_snapshot = (
                    last_device.ip_address,
                    last_device.hostname,
                    last_device.vendor,
                    last_device.device_type,
                    last_device.status == DeviceStatus.ACTIVE,
                    (last_device.metadata or {}).get('discovery_method')
                )
                if current_snapshot != last_snapshot:
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
            mac = dev_dict['mac']
            existing = self.nib_store.get_device_by_mac(mac)

            # Convert to Device model
            device = Device(
                device_id=existing.device_id if existing else "",
                ip_address=dev_dict['ip'],
                mac_address=mac,
                hostname=dev_dict.get('hostname'),
                vendor=dev_dict.get('vendor'),
                device_type=dev_dict.get('model'),
                status=DeviceStatus.ACTIVE if dev_dict.get('reachable') else DeviceStatus.QUARANTINED,
                last_seen=datetime.fromisoformat(dev_dict['last_seen']),
                local_controller=self.controller_id,
                region=self.region,
                discovery_method=dev_dict.get('discovery_method'),
                version=existing.version if existing else 0,
                metadata={
                    'rtt_ms': dev_dict.get('rtt_ms'),
                    'uptime_seconds': dev_dict.get('uptime_seconds'),
                    'discovery_method': dev_dict.get('discovery_method'),
                    'protocol': dev_dict.get('protocol', 'ARP')
                }
            )
            
            # Upsert device (will handle new vs update automatically)
            result = self.nib_store.upsert_device(device)
            
            if not result.success:
                self.logger.warning(
                    f"Failed to write device {mac} to NIB: {result.error}"
                )

            # Keep discovery cache in sync with observed state even when a
            # write conflicts, preventing repeated "new" loops.
            self.last_scan_devices[mac] = device
    
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

    def submit_config_proposal(
        self,
        rc_id: str,
        device_id: str,
        config_lines: List[str],
        rollback_payload: Optional[Dict] = None,
        policy_version: Optional[str] = None,
    ) -> Dict:
        """Create and submit a configuration proposal to the Regional Controller."""
        sensitivity = self.sensitivity_classifier.classify(config_lines)
        request = self.approval_engine.create_request(
            device_id=device_id,
            config_lines=config_lines,
            sensitivity=sensitivity,
        )

        submitted = self.approval_engine.submit_request(request.request_id)
        if not submitted:
            return {
                "status": "failed",
                "reason": "submit_failed",
                "proposal_id": request.request_id,
            }

        config_record = Config(
            config_id=request.request_id,
            device_id=device_id,
            config_hash=self._hash_config(config_lines),
            category=self._to_config_category(sensitivity),
            status=ConfigStatus.PENDING if request.state.value == "PENDING_APPROVAL" else ConfigStatus.APPROVED,
            proposed_by=self.controller_id,
            proposed_at=datetime.now(timezone.utc),
            policy_version=policy_version,
            rollback_payload=str(rollback_payload) if rollback_payload else None,
            config_data=json.dumps(request.to_dict()),
        )
        create_result = self.nib_store.create_config_proposal(config_record)
        if not create_result.success and "already exists" not in (create_result.error or "").lower():
            return {
                "status": "failed",
                "reason": create_result.error,
                "proposal_id": request.request_id,
            }

        if request.state.value == "APPROVED":
            return {
                "status": "approved",
                "decision": "APPROVE",
                "proposal_id": request.request_id,
                "sensitivity": sensitivity.value,
                "execution_mode": "auto_approved",
            }

        payload = {
            "proposal_id": request.request_id,
            "device_id": device_id,
            "config_lines": config_lines,
            "target_devices": [device_id],
            "suggested_sensitivity": sensitivity.value,
            "rollback_payload": rollback_payload or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "policy_version": policy_version,
            "origin": self.controller_id,
        }

        response = None
        if self.http_client:
            response = self.http_client.send(
                sender_id=self.controller_id,
                recipient_id=rc_id,
                message_type=MessageType.CONFIG_PROPOSAL,
                payload=payload,
            )
        elif self.message_bus:
            response = self.message_bus.send(
                sender_id=self.controller_id,
                recipient_id=rc_id,
                message_type=MessageType.CONFIG_PROPOSAL,
                payload=payload,
            )

        response_payload = response.payload if response else {}
        return {
            "status": "submitted",
            "proposal_id": request.request_id,
            "sensitivity": sensitivity.value,
            "response": response_payload,
        }

    def handle_execution_instruction(self, envelope: MessageEnvelope) -> MessageEnvelope:
        """Validate execution token and simulate execution for approved config."""
        payload = envelope.payload or {}
        proposal_id = payload.get("proposal_id")
        device_id = payload.get("device_id")
        token_payload = payload.get("execution_token") or {}
        config_lines = payload.get("config_lines") or []

        self.logger.info(
            f"LC received execution instruction for {proposal_id} on device {device_id}; "
            f"token={token_payload.get('token_id', 'N/A')[:12]}..."
        )

        status = "FAILED"
        reason = None

        try:
            token = ExecutionToken.from_dict(token_payload)
            valid, error = self.execution_token_manager.verify_token(
                token,
                expected_device=device_id,
            )
            if not valid:
                reason = error or "TOKEN_INVALID"
                self.logger.warning(f"Token validation failed for {proposal_id}: {reason}")
            else:
                self.logger.info(f"LC executing config for {proposal_id} (token valid)")
                self._mark_config_executing(proposal_id)
                execution_result = self._execute_config_change(device_id, config_lines)
                status = "EXECUTED" if execution_result.get("success") else "FAILED"
                reason = execution_result.get("reason")
                self.logger.info(
                    f"LC execution completed for {proposal_id}: status={status}, "
                    f"applied {execution_result.get('applied_lines', 0)} lines"
                )
        except Exception as exc:
            reason = str(exc)
            self.logger.warning(f"LC execution exception for {proposal_id}: {exc}")

        self._mark_config_terminal_state(proposal_id, status)
        self.approval_engine.set_execution_result(
            proposal_id,
            {
                "status": status,
                "reason": reason,
                "executor": self.controller_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        event = Event(
            event_id=f"event-{uuid.uuid4().hex[:12]}",
            event_type="EXECUTION",
            actor=self.controller_id,
            subject=proposal_id,
            action="Applied execution instruction" if status == "EXECUTED" else "Execution failed",
            decision=status,
            timestamp=datetime.now(timezone.utc),
            details={
                "proposal_id": proposal_id,
                "device_id": device_id,
                "status": status,
                "reason": reason,
            },
        )
        self.nib_store.write_event(event)

        return MessageEnvelope(
            sender_id=self.controller_id,
            recipient_id=envelope.sender_id,
            message_type=MessageType.EXECUTION_RESULT,
            correlation_id=envelope.message_id,
            payload={
                "proposal_id": proposal_id,
                "executor": self.controller_id,
                "status": status,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _load_execution_shared_secret(self) -> bytes:
        secret = os.getenv("PDSNO_EXECUTION_TOKEN_SECRET")
        if secret:
            return hashlib.sha256(secret.encode("utf-8")).digest()
        return hashlib.sha256(f"pdsno-exec-token::{self.region}".encode("utf-8")).digest()

    @staticmethod
    def _hash_config(config_lines: List[str]) -> str:
        return hashlib.sha256("\n".join(config_lines).encode("utf-8")).hexdigest()

    @staticmethod
    def _to_config_category(sensitivity: SensitivityLevel) -> ConfigCategory:
        return {
            SensitivityLevel.LOW: ConfigCategory.LOW,
            SensitivityLevel.MEDIUM: ConfigCategory.MEDIUM,
            SensitivityLevel.HIGH: ConfigCategory.HIGH,
        }[sensitivity]

    def _mark_config_executing(self, proposal_id: str):
        config = self.nib_store.get_config(proposal_id)
        if not config:
            return
        self.nib_store.update_config_status(
            config_id=proposal_id,
            status=ConfigStatus.EXECUTING,
            version=config.version,
        )

    def _mark_config_terminal_state(self, proposal_id: str, status: str):
        config = self.nib_store.get_config(proposal_id)
        if not config:
            return
        mapped_status = ConfigStatus.EXECUTED if status == "EXECUTED" else ConfigStatus.FAILED
        self.nib_store.update_config_status(
            config_id=proposal_id,
            status=mapped_status,
            version=config.version,
        )

    def _execute_config_change(self, device_id: str, config_lines: List[str]) -> Dict:
        # Actual device execution is integrated in later phases; this preserves end-to-end flow.
        if not device_id or not config_lines:
            return {"success": False, "reason": "MISSING_EXECUTION_INPUT"}
        return {"success": True, "applied_lines": len(config_lines)}