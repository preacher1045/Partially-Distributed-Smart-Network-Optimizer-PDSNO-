"""
Base Adapter Interface

Defines the contract that all vendor adapters must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum
import logging


class IntentType(Enum):
    """Types of configuration intents"""
    CREATE_VLAN = "create_vlan"
    DELETE_VLAN = "delete_vlan"
    CONFIGURE_INTERFACE = "configure_interface"
    SET_IP_ADDRESS = "set_ip_address"
    ENABLE_ROUTING = "enable_routing"
    CREATE_ACL = "create_acl"
    CONFIGURE_QOS = "configure_qos"


@dataclass
class ConfigIntent:
    """
    Generic configuration intent.
    
    This is vendor-agnostic - adapters translate to vendor-specific commands.
    """
    intent_type: IntentType
    parameters: Dict[str, Any]
    
    def __post_init__(self):
        """Validate intent parameters"""
        if not isinstance(self.intent_type, IntentType):
            raise ValueError(f"Invalid intent type: {self.intent_type}")


class VendorAdapter(ABC):
    """
    Base class for all vendor adapters.
    
    Each vendor (Cisco, Juniper, Arista, etc.) implements this interface
    to translate generic intents into vendor-specific commands.
    """
    
    VENDOR: str = "generic"
    PLATFORM: str = "generic"
    
    def __init__(self, device_info: Dict):
        """
        Initialize adapter.
        
        Args:
            device_info: Device information including credentials
        """
        self.device_info = device_info
        self.connection = None
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def connect(self, device_info: Dict) -> bool:
        """
        Establish connection to device.
        
        Args:
            device_info: Device IP, credentials, protocol
        
        Returns:
            True if connected successfully
        """
    
    @abstractmethod
    def disconnect(self):
        """Close connection to device"""
    
    @abstractmethod
    def translate_intent(self, intent: ConfigIntent) -> List[str]:
        """
        Translate generic intent to vendor-specific commands.
        
        Args:
            intent: Generic configuration intent
        
        Returns:
            List of vendor-specific CLI commands
        """
    
    @abstractmethod
    def apply_config(self, commands: List[str]) -> Dict:
        """
        Apply configuration commands to device.
        
        Args:
            commands: Vendor-specific commands
        
        Returns:
            Result dictionary with success/failure and output
        """
    
    @abstractmethod
    def get_running_config(self) -> str:
        """
        Retrieve current device configuration.
        
        Returns:
            Running configuration as string
        """
    
    @abstractmethod
    def verify_config(self, intent: ConfigIntent) -> bool:
        """
        Verify that configuration was applied successfully.
        
        Args:
            intent: Original intent to verify
        
        Returns:
            True if configuration matches intent
        """
    
    def is_connected(self) -> bool:
        """Check if currently connected to device"""
        return self.connection is not None
    
    def get_vendor_info(self) -> Dict:
        """Get vendor and platform information"""
        return {
            'vendor': self.VENDOR,
            'platform': self.PLATFORM
        }