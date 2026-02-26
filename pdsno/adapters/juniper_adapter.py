"""
Juniper JunOS Adapter

Supports Juniper Networks devices running JunOS.
Uses Junos PyEZ library for NETCONF-based management.
"""

from typing import Dict, List
from jnpr.junos import Device
from jnpr.junos.utils.config import Config
from jnpr.junos.exception import ConnectError, ConfigLoadError, CommitError
from .base_adapter import VendorAdapter, ConfigIntent, IntentType


class JuniperAdapter(VendorAdapter):
    """Adapter for Juniper JunOS devices"""
    
    VENDOR = "juniper"
    PLATFORM = "junos"
    
    def __init__(self, device_info: Dict):
        """Initialize Juniper adapter"""
        super().__init__(device_info)
        self.config_manager = None
    
    def connect(self, device_info: Dict) -> bool:
        """Connect to Juniper device via NETCONF"""
        try:
            self.connection = Device(
                host=device_info['ip'],
                user=device_info['username'],
                password=device_info['password'],
                port=device_info.get('port', 830),
                normalize=True
            )
            
            # Open connection
            self.connection.open()
            
            # Initialize config manager
            self.config_manager = Config(self.connection)
            
            self.logger.info(f"Connected to Juniper device {device_info['ip']}")
            return True
        
        except ConnectError as e:
            self.logger.error(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close NETCONF connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.config_manager = None
    
    def translate_intent(self, intent: ConfigIntent) -> List[str]:
        """Translate intent to Juniper set commands"""
        
        if intent.intent_type == IntentType.CREATE_VLAN:
            return self._translate_vlan(intent.parameters)
        
        elif intent.intent_type == IntentType.CONFIGURE_INTERFACE:
            return self._translate_interface(intent.parameters)
        
        elif intent.intent_type == IntentType.SET_IP_ADDRESS:
            return self._translate_ip_address(intent.parameters)
        
        elif intent.intent_type == IntentType.ENABLE_ROUTING:
            return self._translate_routing(intent.parameters)
        
        elif intent.intent_type == IntentType.CREATE_ACL:
            return self._translate_firewall(intent.parameters)
        
        else:
            raise ValueError(f"Unsupported intent: {intent.intent_type}")
    
    def _translate_vlan(self, params: Dict) -> List[str]:
        """Translate VLAN creation to Juniper set commands"""
        vlan_name = params['name']
        vlan_id = params['vlan_id']
        
        commands = [
            f"set vlans {vlan_name} vlan-id {vlan_id}"
        ]
        
        if params.get('description'):
            commands.append(f"set vlans {vlan_name} description '{params['description']}'")
        
        if params.get('l3_interface'):
            commands.append(f"set vlans {vlan_name} l3-interface {params['l3_interface']}")
        
        return commands
    
    def _translate_interface(self, params: Dict) -> List[str]:
        """Translate interface configuration to Juniper set commands"""
        iface = self._normalize_interface_name(params['interface_name'])
        commands = []
        
        # Description
        if params.get('description'):
            commands.append(
                f"set interfaces {iface} description '{params['description']}'"
            )
        
        # Layer 2 configuration (switchport)
        if params.get('switchport_mode'):
            mode = params['switchport_mode']
            
            if mode == 'access':
                # Access mode
                commands.append(
                    f"set interfaces {iface} unit 0 family ethernet-switching interface-mode access"
                )
                
                if params.get('access_vlan'):
                    vlan_name = params.get('vlan_name', f"vlan{params['access_vlan']}")
                    commands.append(
                        f"set interfaces {iface} unit 0 family ethernet-switching vlan members {vlan_name}"
                    )
            
            elif mode == 'trunk':
                # Trunk mode
                commands.append(
                    f"set interfaces {iface} unit 0 family ethernet-switching interface-mode trunk"
                )
                
                if params.get('allowed_vlans'):
                    for vlan in params['allowed_vlans']:
                        vlan_name = f"vlan{vlan}"  # Or use actual VLAN names
                        commands.append(
                            f"set interfaces {iface} unit 0 family ethernet-switching vlan members {vlan_name}"
                        )
        
        # Layer 3 configuration (routed interface)
        elif params.get('ip_address') and params.get('subnet_mask'):
            ip = params['ip_address']
            mask = self._netmask_to_prefix(params['subnet_mask'])
            
            commands.append(
                f"set interfaces {iface} unit 0 family inet address {ip}/{mask}"
            )
        
        # Admin status
        if not params.get('enabled', True):
            commands.append(f"set interfaces {iface} disable")
        else:
            commands.append(f"delete interfaces {iface} disable")
        
        # Speed/duplex
        if params.get('speed'):
            speed_map = {
                '100': '100m',
                '1000': '1g',
                '10000': '10g'
            }
            speed = speed_map.get(str(params['speed']), params['speed'])
            commands.append(f"set interfaces {iface} speed {speed}")
        
        if params.get('duplex'):
            commands.append(f"set interfaces {iface} link-mode {params['duplex']}-duplex")
        
        return commands
    
    def _translate_ip_address(self, params: Dict) -> List[str]:
        """Translate IP address configuration"""
        iface = self._normalize_interface_name(params['interface'])
        ip = params['ip']
        mask = self._netmask_to_prefix(params['mask'])
        
        return [
            f"set interfaces {iface} unit 0 family inet address {ip}/{mask}"
        ]
    
    def _translate_routing(self, params: Dict) -> List[str]:
        """Translate routing protocol configuration"""
        protocol = params['protocol'].lower()
        commands = []
        
        if protocol == 'ospf':
            # OSPF configuration
            process_id = params.get('process_id', 0)
            
            commands.append(f"set protocols ospf area 0.0.0.{process_id}")
            
            for network in params.get('networks', []):
                interface = network.get('interface')
                commands.append(
                    f"set protocols ospf area {network['area']} interface {interface}"
                )
        
        elif protocol == 'bgp':
            # BGP configuration
            as_number = params['as_number']
            
            commands.append(f"set routing-options autonomous-system {as_number}")
            
            for neighbor in params.get('neighbors', []):
                neighbor_ip = neighbor['ip']
                neighbor_as = neighbor['as']
                
                commands.append(
                    f"set protocols bgp group external-peers type external"
                )
                commands.append(
                    f"set protocols bgp group external-peers neighbor {neighbor_ip} peer-as {neighbor_as}"
                )
        
        elif protocol == 'static':
            # Static route
            network = params['network']
            mask = self._netmask_to_prefix(params['mask'])
            next_hop = params['next_hop']
            
            commands.append(
                f"set routing-options static route {network}/{mask} next-hop {next_hop}"
            )
        
        return commands
    
    def _translate_firewall(self, params: Dict) -> List[str]:
        """Translate ACL to Juniper firewall filter"""
        filter_name = params['name']
        commands = []
        
        term_num = 1
        for rule in params.get('rules', []):
            term_name = f"term{term_num}"
            
            # Match conditions
            protocol = rule.get('protocol', 'ip')
            if protocol != 'ip':
                commands.append(
                    f"set firewall family inet filter {filter_name} term {term_name} from protocol {protocol}"
                )
            
            source = rule['source']
            if source != 'any':
                commands.append(
                    f"set firewall family inet filter {filter_name} term {term_name} from source-address {source}"
                )
            
            dest = rule['destination']
            if dest != 'any':
                commands.append(
                    f"set firewall family inet filter {filter_name} term {term_name} from destination-address {dest}"
                )
            
            if rule.get('port'):
                commands.append(
                    f"set firewall family inet filter {filter_name} term {term_name} from destination-port {rule['port']}"
                )
            
            # Action
            action = 'accept' if rule['action'] == 'permit' else 'discard'
            commands.append(
                f"set firewall family inet filter {filter_name} term {term_name} then {action}"
            )
            
            term_num += 1
        
        return commands
    
    def _normalize_interface_name(self, name: str) -> str:
        """
        Convert Cisco-style interface names to Juniper format.
        
        Examples:
            GigabitEthernet0/0/1 -> ge-0/0/1
            TenGigabitEthernet0/1/0 -> xe-0/1/0
        """
        name = name.lower()
        
        # Map common prefixes
        if 'gigabitethernet' in name or 'gi' in name:
            prefix = 'ge'
        elif 'tengigabitethernet' in name or 'te' in name:
            prefix = 'xe'
        elif 'fastethernet' in name or 'fa' in name:
            prefix = 'fe'
        else:
            # Return as-is if already in Juniper format
            return name
        
        # Extract numbers (e.g., "0/0/1" from "GigabitEthernet0/0/1")
        import re
        match = re.search(r'(\d+[/\d]*)', name)
        if match:
            numbers = match.group(1)
            return f"{prefix}-{numbers}"
        
        return name
    
    def _netmask_to_prefix(self, netmask: str) -> int:
        """Convert netmask to prefix length"""
        # Convert netmask to binary and count 1s
        octets = netmask.split('.')
        binary = ''.join([bin(int(octet))[2:].zfill(8) for octet in octets])
        return binary.count('1')
    
    def apply_config(self, commands: List[str]) -> Dict:
        """Apply configuration to Juniper device"""
        if not self.is_connected():
            return {
                'success': False,
                'error': 'Not connected to device'
            }
        
        try:
            # Load configuration as set commands
            self.config_manager.load(
                '\n'.join(commands),
                format='set'
            )
            
            # Check differences
            diff = self.config_manager.diff()
            
            # Commit configuration
            self.config_manager.commit()
            
            self.logger.info("Configuration committed successfully")
            
            return {
                'success': True,
                'diff': diff,
                'commands': commands
            }
        
        except ConfigLoadError as e:
            self.logger.error(f"Config load failed: {e}")
            self.config_manager.rollback()
            return {
                'success': False,
                'error': f"Config load failed: {e}",
                'commands': commands
            }
        
        except CommitError as e:
            self.logger.error(f"Commit failed: {e}")
            self.config_manager.rollback()
            return {
                'success': False,
                'error': f"Commit failed: {e}",
                'commands': commands
            }
    
    def get_running_config(self) -> str:
        """Get running configuration"""
        if not self.is_connected():
            raise ConnectionError("Not connected to device")
        
        # Get configuration in set format
        config = self.connection.rpc.get_config(
            options={'format': 'set'}
        )
        
        return config.text
    
    def verify_config(self, intent: ConfigIntent) -> bool:
        """Verify configuration was applied"""
        try:
            config = self.get_running_config()
            
            if intent.intent_type == IntentType.CREATE_VLAN:
                vlan_name = intent.parameters['name']
                return f"vlans {vlan_name}" in config
            
            elif intent.intent_type == IntentType.CONFIGURE_INTERFACE:
                iface = self._normalize_interface_name(intent.parameters['interface_name'])
                return f"interfaces {iface}" in config
            
            return True
        
        except Exception as e:
            self.logger.error(f"Verification failed: {e}")
            return False