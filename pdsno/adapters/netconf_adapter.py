"""
Generic NETCONF Adapter

Works with any device that supports NETCONF/YANG.
"""

from typing import Dict, List
from ncclient import manager
from ncclient.transport.errors import AuthenticationError, SSHError
import xml.etree.ElementTree as ET
from .base_adapter import VendorAdapter, ConfigIntent, IntentType


class NETCONFAdapter(VendorAdapter):
    """Generic NETCONF adapter using YANG models"""
    
    VENDOR = "netconf"
    PLATFORM = "generic"
    
    def connect(self, device_info: Dict) -> bool:
        """Connect via NETCONF"""
        try:
            self.connection = manager.connect(
                host=device_info['ip'],
                port=device_info.get('port', 830),
                username=device_info['username'],
                password=device_info['password'],
                hostkey_verify=False,
                device_params={'name': 'default'},
                timeout=device_info.get('timeout', 30)
            )
            
            self.logger.info(f"NETCONF connected to {device_info['ip']}")
            return True
        
        except (AuthenticationError, SSHError) as e:
            self.logger.error(f"NETCONF connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close NETCONF session"""
        if self.connection:
            self.connection.close_session()
            self.connection = None
    
    def translate_intent(self, intent: ConfigIntent) -> List[str]:
        """
        Translate to NETCONF XML.
        
        Returns list with single XML string.
        """
        if intent.intent_type == IntentType.CREATE_VLAN:
            xml = self._create_vlan_xml(intent.parameters)
        
        elif intent.intent_type == IntentType.CONFIGURE_INTERFACE:
            xml = self._create_interface_xml(intent.parameters)
        
        else:
            raise ValueError(f"Unsupported intent: {intent.intent_type}")
        
        return [xml]
    
    def _create_vlan_xml(self, params: Dict) -> str:
        """Create VLAN configuration XML"""
        return f"""
        <config>
          <vlans xmlns="urn:ietf:params:xml:ns:yang:ietf-vlans">
            <vlan>
              <vlan-id>{params['vlan_id']}</vlan-id>
              <name>{params['name']}</name>
            </vlan>
          </vlans>
        </config>
        """
    
    def _create_interface_xml(self, params: Dict) -> str:
        """Create interface configuration XML"""
        iface = params['interface_name']
        
        xml = f"""
        <config>
          <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
            <interface>
              <name>{iface}</name>
              <description>{params.get('description', '')}</description>
              <enabled>{str(params.get('enabled', True)).lower()}</enabled>
        """
        
        if params.get('ip_address'):
            xml += f"""
              <ipv4>
                <address>
                  <ip>{params['ip_address']}</ip>
                  <netmask>{params['subnet_mask']}</netmask>
                </address>
              </ipv4>
            """
        
        xml += """
            </interface>
          </interfaces>
        </config>
        """
        
        return xml
    
    def apply_config(self, commands: List[str]) -> Dict:
        """Apply NETCONF configuration"""
        if not self.is_connected():
            return {'success': False, 'error': 'Not connected'}
        
        try:
            xml_config = commands[0]  # Single XML string
            
            # Edit candidate config
            result = self.connection.edit_config(
                target='candidate',
                config=xml_config
            )
            
            # Commit
            commit_result = self.connection.commit()
            
            return {
                'success': True,
                'edit_result': str(result),
                'commit_result': str(commit_result)
            }
        
        except Exception as e:
            self.logger.error(f"NETCONF config failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_running_config(self) -> str:
        """Get running configuration via NETCONF"""
        if not self.is_connected():
            raise ConnectionError("Not connected")
        
        result = self.connection.get_config(source='running')
        return result.data_xml
    
    def verify_config(self, intent: ConfigIntent) -> bool:
        """Verify configuration via NETCONF"""
        try:
            config = self.get_running_config()
            
            if intent.intent_type == IntentType.CREATE_VLAN:
                return str(intent.parameters['vlan_id']) in config
            
            return True
        
        except:
            return False