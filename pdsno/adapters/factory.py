"""
Vendor Adapter Factory

Creates appropriate adapter instance based on device vendor/platform.
"""

from typing import Dict
from .base_adapter import VendorAdapter
from .cisco_ios_adapter import CiscoIOSAdapter
from .juniper_adapter import JuniperAdapter
from .arista_adapter import AristaAdapter
from .netconf_adapter import NETCONFAdapter
import logging


class VendorAdapterFactory:
    """Factory for creating vendor-specific adapters"""
    
    # Registry: (vendor, platform) -> Adapter class
    ADAPTERS = {
        ('cisco', 'ios'): CiscoIOSAdapter,
        ('cisco', 'ios-xe'): CiscoIOSAdapter,
        ('cisco', 'nxos'): CiscoIOSAdapter,  # Can create separate adapter
        ('juniper', 'junos'): JuniperAdapter,
        ('arista', 'eos'): AristaAdapter,
        ('netconf', 'generic'): NETCONFAdapter,
    }
    
    @classmethod
    def create_adapter(cls, device: Dict) -> VendorAdapter:
        """
        Create appropriate adapter for device.
        
        Args:
            device: Device info with 'vendor' and 'platform' keys
        
        Returns:
            Vendor-specific adapter instance
        
        Raises:
            ValueError: If no adapter available for vendor/platform
        """
        vendor = device.get('vendor', '').lower()
        platform = device.get('platform', '').lower()
        
        # Try exact match
        adapter_class = cls.ADAPTERS.get((vendor, platform))
        
        # Try vendor-only match (default platform)
        if not adapter_class:
            adapter_class = cls._find_default_adapter(vendor)
        
        # Fall back to NETCONF if device supports it
        if not adapter_class and device.get('supports_netconf'):
            adapter_class = NETCONFAdapter
        
        if not adapter_class:
            available = ', '.join([f"{v}/{p}" for v, p in cls.ADAPTERS.keys()])
            raise ValueError(
                f"No adapter found for {vendor}/{platform}. "
                f"Available: {available}"
            )
        
        return adapter_class(device)
    
    @classmethod
    def _find_default_adapter(cls, vendor: str):
        """Find default adapter for vendor"""
        for (v, p), adapter in cls.ADAPTERS.items():
            if v == vendor:
                return adapter
        return None
    
    @classmethod
    def register_adapter(
        cls,
        vendor: str,
        platform: str,
        adapter_class: type
    ):
        """
        Register custom adapter.
        
        Allows users to add support for new vendors.
        """
        cls.ADAPTERS[(vendor.lower(), platform.lower())] = adapter_class
    
    @classmethod
    def list_supported_vendors(cls) -> list:
        """List all supported vendor/platform combinations"""
        return [f"{v}/{p}" for v, p in cls.ADAPTERS.keys()]