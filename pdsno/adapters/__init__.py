"""
PDSNO Vendor Adapters Module

Provides vendor-specific adapters for device configuration:
- Cisco IOS/IOS-XE
- Juniper JunOS
- Arista EOS
- Generic NETCONF

Usage:
    from pdsno.adapters import VendorAdapterFactory, VendorAdapter

    adapter = VendorAdapterFactory.create_adapter(device_info)
    adapter.connect(device_info)
    commands = adapter.translate_intent(intent)
    result = adapter.apply_config(commands)
"""

from .base_adapter import VendorAdapter
from .factory import VendorAdapterFactory

__all__ = [
    "VendorAdapter",
    "VendorAdapterFactory",
]
