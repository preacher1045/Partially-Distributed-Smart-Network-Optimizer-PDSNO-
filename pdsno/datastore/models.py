"""
NIB Data Models

Dataclasses representing entities stored in the Network Information Base.
These models map to the NIB schema defined in docs/nib_spec.md
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from enum import Enum


class DeviceStatus(Enum):
    """Device operational status"""
    DISCOVERED = "discovered"
    VALIDATING = "validating"
    ACTIVE = "active"
    QUARANTINED = "quarantined"
    INACTIVE = "inactive"
    FAILED = "failed"


class ConfigStatus(Enum):
    """Configuration approval status"""
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    FAILED = "failed"


class LockType(Enum):
    """NIB lock types for coordination"""
    CONFIG_APPROVAL = "config_approval"
    DEVICE_ASSIGNMENT = "device_assignment"
    POLICY_UPDATE = "policy_update"


@dataclass
class Device:
    """Network device record"""
    device_id: str  # NIB-assigned unique ID (e.g., nib-dev-001)
    ip_address: str
    mac_address: str  # Unique hardware address
    status: DeviceStatus = DeviceStatus.DISCOVERED
    hostname: Optional[str] = None
    temp_scan_id: Optional[str] = None  # Temporary ID from discovery scan
    vendor: Optional[str] = None
    device_type: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    managed_by_lc: Optional[str] = None  # Local Controller ID
    region: Optional[str] = None
    version: int = 0  # For optimistic locking
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Ensure datetime fields are timezone-aware"""
        if self.first_seen and self.first_seen.tzinfo is None:
            self.first_seen = self.first_seen.replace(tzinfo=timezone.utc)
        if self.last_seen and self.last_seen.tzinfo is None:
            self.last_seen = self.last_seen.replace(tzinfo=timezone.utc)
        
        # Convert string status to enum if needed
        if isinstance(self.status, str):
            self.status = DeviceStatus(self.status)


@dataclass
class Config:
    """Configuration record for a device"""
    config_id: str
    device_id: str
    config_data: str  # JSON or YAML serialized config
    status: ConfigStatus = ConfigStatus.PROPOSED
    proposed_by: Optional[str] = None  # Controller ID
    approved_by: Optional[str] = None  # Controller ID
    proposed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    version: int = 0  # For optimistic locking
    reason: Optional[str] = None  # Rejection reason if applicable
    
    def __post_init__(self):
        """Ensure datetime fields are timezone-aware"""
        for field_name in ['proposed_at', 'approved_at', 'applied_at']:
            value = getattr(self, field_name)
            if value and value.tzinfo is None:
                setattr(self, field_name, value.replace(tzinfo=timezone.utc))
        
        if isinstance(self.status, str):
            self.status = ConfigStatus(self.status)


@dataclass
class Policy:
    """Network policy record"""
    policy_id: str
    name: str
    rule_set: str  # JSON serialized rules
    scope: str  # "global", "regional", or specific region ID
    active: bool = True
    created_by: str = "system"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    version: int = 0
    
    def __post_init__(self):
        """Ensure datetime fields are timezone-aware"""
        if self.created_at and self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)
        if self.updated_at and self.updated_at.tzinfo is None:
            self.updated_at = self.updated_at.replace(tzinfo=timezone.utc)


@dataclass
class Event:
    """Immutable audit log entry"""
    event_id: str
    event_type: str  # e.g., "device_discovered", "config_approved"
    controller_id: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    signature: Optional[str] = None  # HMAC signature for tamper-evidence
    
    def __post_init__(self):
        """Ensure timestamp is timezone-aware"""
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)


@dataclass
class Lock:
    """Coordination lock for distributed operations"""
    lock_id: str
    subject_id: str  # The resource being locked (device_id, etc.)
    lock_type: LockType
    held_by: str  # Controller ID holding the lock
    acquired_at: datetime
    expires_at: datetime
    
    def __post_init__(self):
        """Ensure datetime fields are timezone-aware"""
        if self.acquired_at.tzinfo is None:
            self.acquired_at = self.acquired_at.replace(tzinfo=timezone.utc)
        if self.expires_at.tzinfo is None:
            self.expires_at = self.expires_at.replace(tzinfo=timezone.utc)
        
        if isinstance(self.lock_type, str):
            self.lock_type = LockType(self.lock_type)
    
    def is_expired(self) -> bool:
        """Check if lock has expired"""
        return datetime.now(timezone.utc) > self.expires_at


@dataclass
class Controller:
    """Controller identity record"""
    controller_id: str
    role: str  # "global", "regional", "local"
    region: Optional[str] = None
    status: str = "active"  # "active", "inactive", "validating"
    validated_by: Optional[str] = None  # Parent controller that validated this one
    validated_at: Optional[datetime] = None
    public_key: Optional[str] = None
    certificate: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: int = 0
    
    def __post_init__(self):
        """Ensure datetime fields are timezone-aware"""
        if self.validated_at and self.validated_at.tzinfo is None:
            self.validated_at = self.validated_at.replace(tzinfo=timezone.utc)


@dataclass
class NIBResult:
    """Result of a NIB operation"""
    success: bool
    error: Optional[str] = None
    data: Optional[Any] = None
    conflict: bool = False
