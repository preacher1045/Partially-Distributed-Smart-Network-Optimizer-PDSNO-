"""
Arista EOS Adapter

Supports Arista Networks devices running EOS.
Uses eAPI (JSON-RPC) for management.
"""

from typing import Dict, List
import requests
from requests.auth import HTTPBasicAuth
import json
from .base_adapter import VendorAdapter, ConfigIntent, IntentType
import logging


class AristaAdapter(VendorAdapter):
    """Adapter for Arista EOS devices"""
    
    VENDOR = "arista"
    PLATFORM = "eos"
    
    def __init__(self, device_info: Dict):
        """Initialize Arista adapter"""
        super().__init__(device_info)
        self.eapi_url = None
        self.auth = None
        self.session = None
    
    def connect(self, device_info: Dict) -> bool:
        """Connect to Arista device via eAPI"""
        try:
            # eAPI typically runs on HTTPS port 443
            protocol = 'https' if device_info.get('use_https', True) else 'http'
            port = device_info.get('port', 443)
            
            self.eapi_url = f"{protocol}://{device_info['ip']}:{port}/command-api"
            self.auth = HTTPBasicAuth(
                device_info['username'],
                device_info['password']
            )
            
            # Create session
            self.session = requests.Session()
            self.session.verify = device_info.get('verify_ssl', False)
            
            # Test connection with a simple command
            result = self._execute_commands(['show version'])
            
            if result:
                self.logger.info(f"Connected to Arista device {device_info['ip']}")
                return True
            else:
                return False
        
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close eAPI session"""
        if self.session:
            self.session.close()
            self.session = None
        self.eapi_url = None
        self.auth = None
    
    def translate_intent(self, intent: ConfigIntent) -> List[str]:
        """
        Translate intent to Arista EOS commands.
        
        Arista EOS is similar to Cisco IOS but with some differences.
        """
        
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
        """Translate VLAN creation (similar to Cisco)"""
        commands = [
            f"vlan {params['vlan_id']}",
            f"name {params['name']}"
        ]
        
        if params.get('description'):
            # Arista uses 'name' for description
            commands[1] = f"name {params['name']} {params['description']}"
        
        if params.get('state'):
            commands.append(f"state {params['state']}")  # active or suspend
        
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
                
                if params.get('native_vlan'):
                    commands.append(f"switchport trunk native vlan {params['native_vlan']}")
        
        # Layer 3 config
        if params.get('ip_address') and params.get('subnet_mask'):
            commands.append("no switchport")
            commands.append(f"ip address {params['ip_address']}/{self._netmask_to_prefix(params['subnet_mask'])}")
        
        # Admin status
        if params.get('enabled', True):
            commands.append("no shutdown")
        else:
            commands.append("shutdown")
        
        # Speed (Arista supports more options)
        if params.get('speed'):
            speed_map = {
                '100': '100full',
                '1000': '1000full',
                '10000': '10gfull',
                '25000': '25gfull',
                '40000': '40gfull',
                '100000': '100gfull'
            }
            speed = speed_map.get(str(params['speed']), f"{params['speed']}full")
            commands.append(f"speed forced {speed}")
        
        commands.append("exit")
        
        return commands
    
    def _translate_ip_address(self, params: Dict) -> List[str]:
        """Translate IP address configuration"""
        prefix = self._netmask_to_prefix(params['mask'])
        
        return [
            f"interface {params['interface']}",
            "no switchport",
            f"ip address {params['ip']}/{prefix}",
            "no shutdown",
            "exit"
        ]
    
    def _translate_routing(self, params: Dict) -> List[str]:
        """Translate routing protocol configuration"""
        protocol = params['protocol'].lower()
        commands = []
        
        if protocol == 'ospf':
            process_id = params.get('process_id', 1)
            commands = [
                f"router ospf {process_id}"
            ]
            
            if params.get('router_id'):
                commands.append(f"router-id {params['router_id']}")
            
            for network in params.get('networks', []):
                commands.append(
                    f"network {network['network']} {network['wildcard']} area {network['area']}"
                )
            
            commands.append("exit")
        
        elif protocol == 'bgp':
            as_number = params['as_number']
            commands = [
                f"router bgp {as_number}"
            ]
            
            if params.get('router_id'):
                commands.append(f"router-id {params['router_id']}")
            
            for neighbor in params.get('neighbors', []):
                commands.append(
                    f"neighbor {neighbor['ip']} remote-as {neighbor['as']}"
                )
            
            commands.append("exit")
        
        elif protocol == 'static':
            prefix = self._netmask_to_prefix(params['mask'])
            commands = [
                f"ip route {params['network']}/{prefix} {params['next_hop']}"
            ]
        
        return commands
    
    def _translate_acl(self, params: Dict) -> List[str]:
        """Translate ACL configuration"""
        acl_name = params['name']
        commands = [f"ip access-list {acl_name}"]
        
        seq_num = 10
        for rule in params.get('rules', []):
            action = rule['action']  # permit/deny
            protocol = rule['protocol']
            source = rule['source']
            dest = rule['destination']
            
            cmd = f"{seq_num} {action} {protocol} {source} {dest}"
            
            if rule.get('port'):
                cmd += f" eq {rule['port']}"
            
            commands.append(cmd)
            seq_num += 10
        
        commands.append("exit")
        
        return commands
    
    def _netmask_to_prefix(self, netmask: str) -> int:
        """Convert netmask to prefix length"""
        octets = netmask.split('.')
        binary = ''.join([bin(int(octet))[2:].zfill(8) for octet in octets])
        return binary.count('1')
    
    def _execute_commands(
        self,
        commands: List[str],
        format: str = 'json'
    ) -> Dict:
        """
        Execute commands via eAPI.
        
        Args:
            commands: List of CLI commands
            format: Response format (json or text)
        
        Returns:
            API response
        """
        if not self.session:
            raise ConnectionError("Not connected to device")
        
        payload = {
            "jsonrpc": "2.0",
            "method": "runCmds",
            "params": {
                "version": 1,
                "cmds": commands,
                "format": format
            },
            "id": "1"
        }
        
        try:
            response = self.session.post(
                self.eapi_url,
                auth=self.auth,
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            self.logger.error(f"eAPI request failed: {e}")
            return None
    
    def apply_config(self, commands: List[str]) -> Dict:
        """Apply configuration via eAPI"""
        if not self.is_connected():
            return {
                'success': False,
                'error': 'Not connected to device'
            }
        
        try:
            # Enter config mode and apply commands
            config_commands = ['enable', 'configure'] + commands + ['end']
            
            result = self._execute_commands(config_commands, format='text')
            
            if result and 'result' in result:
                # Save configuration
                self._execute_commands(['enable', 'write memory'])
                
                return {
                    'success': True,
                    'output': result['result'],
                    'commands': commands
                }
            else:
                return {
                    'success': False,
                    'error': 'No result from device',
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
        """Get running configuration via eAPI"""
        if not self.is_connected():
            raise ConnectionError("Not connected to device")
        
        result = self._execute_commands(
            ['enable', 'show running-config'],
            format='text'
        )
        
        if result and 'result' in result:
            # Extract text from result
            return result['result'][1]['output']
        
        return ""
    
    def verify_config(self, intent: ConfigIntent) -> bool:
        """Verify configuration was applied"""
        try:
            if intent.intent_type == IntentType.CREATE_VLAN:
                vlan_id = intent.parameters['vlan_id']
                result = self._execute_commands(['show vlan id ' + str(vlan_id)])
                return result and 'result' in result
            
            elif intent.intent_type == IntentType.CONFIGURE_INTERFACE:
                iface = intent.parameters['interface_name']
                result = self._execute_commands([f'show running-config interfaces {iface}'])
                return result and 'result' in result
            
            return True
        
        except Exception as e:
            self.logger.error(f"Verification failed: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if connected to device"""
        return self.session is not None and self.eapi_url is not None