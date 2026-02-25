"""
Cisco IOS/IOS-XE Adapter

Supports Cisco IOS, IOS-XE, and NX-OS devices.
"""

from typing import Dict, List
from netmiko import ConnectHandler
from .base_adapter import VendorAdapter, ConfigIntent, IntentType
import logging


class CiscoIOSAdapter(VendorAdapter):
    """Adapter for Cisco IOS/IOS-XE devices"""
    
    VENDOR = "cisco"
    PLATFORM = "ios"
    
    def connect(self, device_info: Dict) -> bool:
        """Connect to Cisco device via SSH"""
        try:
            self.connection = ConnectHandler(
                device_type='cisco_ios',
                host=device_info['ip'],
                username=device_info['username'],
                password=device_info['password'],
                port=device_info.get('port', 22),
                timeout=device_info.get('timeout', 30)
            )
            
            self.logger.info(f"Connected to Cisco device {device_info['ip']}")
            return True
        
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close SSH connection"""
        if self.connection:
            self.connection.disconnect()
            self.connection = None
    
    def translate_intent(self, intent: ConfigIntent) -> List[str]:
        """Translate intent to Cisco IOS commands"""
        
        if intent.intent_type == IntentType.CREATE_VLAN:
            return self._translate_vlan(intent.parameters)
        
        elif intent.intent_type == IntentType.CONFIGURE_INTERFACE:
            return self._translate_interface(intent.parameters)
        
        elif intent.intent_type == IntentType.SET_IP_ADDRESS:
            return self._translate_ip_address(intent.parameters)
        
        elif intent.intent_type == IntentType.ENABLE_ROUTING:
            return self._translate_routing(intent.parameters)
        
        elif intent.intent_type == IntentType.CREATE_ACL:
            return self._translate_acl(intent.parameters)
        
        else:
            raise ValueError(f"Unsupported intent: {intent.intent_type}")
    
    def _translate_vlan(self, params: Dict) -> List[str]:
        """Translate VLAN creation to Cisco commands"""
        commands = [
            f"vlan {params['vlan_id']}",
            f"name {params['name']}"
        ]
        
        if params.get('description'):
            commands.append(f"! {params['description']}")
        
        if params.get('mtu'):
            commands.append(f"mtu {params['mtu']}")
        
        commands.append("exit")
        
        return commands
    
    def _translate_interface(self, params: Dict) -> List[str]:
        """Translate interface configuration"""
        iface = params['interface_name']
        commands = [f"interface {iface}"]
        
        if params.get('description'):
            commands.append(f"description {params['description']}")
        
        # Layer 2 config
        if params.get('switchport_mode'):
            commands.append("switchport")
            commands.append(f"switchport mode {params['switchport_mode']}")
            
            if params['switchport_mode'] == 'access' and params.get('access_vlan'):
                commands.append(f"switchport access vlan {params['access_vlan']}")
            
            elif params['switchport_mode'] == 'trunk' and params.get('allowed_vlans'):
                vlan_list = ','.join(map(str, params['allowed_vlans']))
                commands.append(f"switchport trunk allowed vlan {vlan_list}")
        
        # Layer 3 config
        if params.get('ip_address') and params.get('subnet_mask'):
            commands.append("no switchport")  # Make routed port
            commands.append(f"ip address {params['ip_address']} {params['subnet_mask']}")
        
        # Admin status
        if params.get('enabled', True):
            commands.append("no shutdown")
        else:
            commands.append("shutdown")
        
        # Speed/duplex
        if params.get('speed'):
            commands.append(f"speed {params['speed']}")
        if params.get('duplex'):
            commands.append(f"duplex {params['duplex']}")
        
        commands.append("exit")
        
        return commands
    
    def _translate_ip_address(self, params: Dict) -> List[str]:
        """Translate IP address configuration"""
        return [
            f"interface {params['interface']}",
            "no switchport",
            f"ip address {params['ip']} {params['mask']}",
            "no shutdown",
            "exit"
        ]
    
    def _translate_routing(self, params: Dict) -> List[str]:
        """Translate routing protocol configuration"""
        protocol = params['protocol'].lower()
        commands = []
        
        if protocol == 'ospf':
            commands = [
                f"router ospf {params['process_id']}",
                f"router-id {params.get('router_id', '1.1.1.1')}"
            ]
            
            for network in params.get('networks', []):
                commands.append(
                    f"network {network['network']} {network['wildcard']} area {network['area']}"
                )
            
            commands.append("exit")
        
        elif protocol == 'bgp':
            commands = [
                f"router bgp {params['as_number']}"
            ]
            
            for neighbor in params.get('neighbors', []):
                commands.append(
                    f"neighbor {neighbor['ip']} remote-as {neighbor['as']}"
                )
            
            commands.append("exit")
        
        elif protocol == 'static':
            commands = [
                f"ip route {params['network']} {params['mask']} {params['next_hop']}"
            ]
        
        return commands
    
    def _translate_acl(self, params: Dict) -> List[str]:
        """Translate ACL configuration"""
        acl_name = params['name']
        commands = [f"ip access-list extended {acl_name}"]
        
        for rule in params.get('rules', []):
            action = rule['action']  # permit/deny
            protocol = rule['protocol']  # ip/tcp/udp/icmp
            source = rule['source']
            dest = rule['destination']
            
            cmd = f"{action} {protocol} {source} {dest}"
            
            if rule.get('port'):
                cmd += f" eq {rule['port']}"
            
            commands.append(cmd)
        
        commands.append("exit")
        
        return commands
    
    def apply_config(self, commands: List[str]) -> Dict:
        """Apply commands to Cisco device"""
        if not self.is_connected():
            return {
                'success': False,
                'error': 'Not connected to device'
            }
        
        try:
            # Enter config mode and apply
            output = self.connection.send_config_set(commands)
            
            # Save config
            save_output = self.connection.send_command('write memory')
            
            return {
                'success': True,
                'output': output,
                'save_output': save_output,
                'commands': commands
            }
        
        except Exception as e:
            self.logger.error(f"Failed to apply config: {e}")
            return {
                'success': False,
                'error': str(e),
                'commands': commands
            }
    
    def get_running_config(self) -> str:
        """Get running configuration"""
        if not self.is_connected():
            raise ConnectionError("Not connected to device")
        
        return self.connection.send_command("show running-config")
    
    def verify_config(self, intent: ConfigIntent) -> bool:
        """Verify configuration was applied"""
        try:
            if intent.intent_type == IntentType.CREATE_VLAN:
                vlan_id = intent.parameters['vlan_id']
                output = self.connection.send_command(f"show vlan id {vlan_id}")
                return intent.parameters['name'] in output
            
            elif intent.intent_type == IntentType.CONFIGURE_INTERFACE:
                iface = intent.parameters['interface_name']
                output = self.connection.send_command(f"show running-config interface {iface}")
                return len(output) > 0
            
            # Add more verification as needed
            return True
        
        except Exception as e:
            self.logger.error(f"Verification failed: {e}")
            return False