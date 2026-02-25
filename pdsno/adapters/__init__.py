"""
PDSNO Vendor Adapters Module

Provides vendor-specific adapters for network device configuration.

Supported Vendors:
- Cisco IOS/IOS-XE
- Juniper JunOS
- Arista EOS
- Generic NETCONF

Usage:
    from pdsno.adapters import VendorAdapterFactory, CiscoIOSAdapter
    
    # Create adapter for device
    device = {'vendor': 'cisco', 'platform': 'ios', ...}
    adapter = VendorAdapterFactory.create_adapter(device)
    
    # Connect and apply config
    adapter.connect(device)
    commands = adapter.translate_intent(vlan_intent)
    result = adapter.apply_config(commands)
"""

from .base_adapter import VendorAdapter, ConfigIntent, IntentType
from .factory import VendorAdapterFactory
from .cisco_ios_adapter import CiscoIOSAdapter
from .juniper_adapter import JuniperAdapter
from .arista_adapter import AristaAdapter
from .netconf_adapter import NETCONFAdapter

__all__ = [
    'VendorAdapter',
    'ConfigIntent',
    'IntentType',
    'VendorAdapterFactory',
    'CiscoIOSAdapter',
    'JuniperAdapter',
    'AristaAdapter',
    'NETCONFAdapter'
]