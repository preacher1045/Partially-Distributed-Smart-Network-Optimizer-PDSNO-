# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""
NIB Data Models

Dataclasses representing entities stored in the Network Information Base.
These models map exactly to the NIB schema defined in docs/nib_spec.md.

Schema alignment history:
    2026-03-22 — Option B alignment: implementation brought in line with spec.
        Renamed: managed_by_lc → local_controller
        Renamed: rule_set → content, created_by → distributed_by,
                created_at → distributed_at, active → is_active
        Added:   discovery_method, firmware_version on Device
                actor, subject, action, decision, payload_ref, notes on Event
                policy_version, content, distributed_by, distributed_at,
                valid_from, valid_until, is_active, target_region on Policy
                config_hash, category, rollback_payload, policy_version,
                expiry, execution_token on Config
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from enum import Enum


class DeviceStatus(Enum):
    """Device operational status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNREACHABLE = "unreachable"
    QUARANTINED = "quarantined"


class ConfigStatus(Enum):
    """Configuration approval status"""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXECUTING = "EXECUTING"
    EXECUTED = "EXECUTED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"


class ConfigCategory(Enum):
    """Configuration sensitivity levels as defined in nib_spec.md"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EMERGENCY = "EMERGENCY"


class LockType(Enum):
    """NIB lock types for coordination"""
    DEVICE_LOCK = "DEVICE_LOCK"
    CONFIG_LOCK = "CONFIG_LOCK"
    VALIDATION_LOCK = "VALIDATION_LOCK"


@dataclass
class Device:
    """
    Network device record.

    Maps to the Device Table in docs/nib_spec.md.
    MAC address is the canonical deduplication key across the system.
    """
    device_id: str                          # NIB-assigned: "nib-dev-<uuid8>"
    ip_address: str
    mac_address: str                        # UNIQUE — hardware address
    status: DeviceStatus = DeviceStatus.QUARANTINED
    hostname: Optional[str] = None
    temp_scan_id: Optional[str] = None      # Temporary ID from discovery scan
    vendor: Optional[str] = None
    device_type: Optional[str] = None      # router | switch | server | endpoint | unknown
    firmware_version: Optional[str] = None
    region: Optional[str] = None
    local_controller: Optional[str] = None  # LC ID that manages this device
    discovery_method: Optional[str] = None  # arp | snmp | icmp | fingerprint
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    version: int = 0                        # Optimistic locking counter
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        for attr in ('first_seen', 'last_seen', 'last_updated'):
            val = getattr(self, attr)
            if val and val.tzinfo is None:
                setattr(self, attr, val.replace(tzinfo=timezone.utc))
        if isinstance(self.status, str):
            self.status = DeviceStatus(self.status)


@dataclass
class Config:
    """
    Configuration proposal and approval record.

    Maps to the Config Table in docs/nib_spec.md.
    A Config record exists for the full lifecycle of a change:
    proposal → approval → execution → result.
    """
    config_id: str                          # UUID
    device_id: str
    config_hash: str = ""                   # SHA-256 of normalized config payload
    category: ConfigCategory = ConfigCategory.LOW
    status: ConfigStatus = ConfigStatus.PENDING
    proposed_by: Optional[str] = None      # LC controller ID
    approved_by: Optional[str] = None      # RC or GC controller ID
    execution_token: Optional[str] = None  # Short-lived token on approval
    proposed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    expiry: Optional[datetime] = None      # Token expiry
    policy_version: Optional[str] = None   # Policy version at proposal time
    rollback_payload: Optional[str] = None # JSON instructions to undo this config
    config_data: Optional[str] = None      # Full config payload (JSON/YAML)
    reason: Optional[str] = None           # Rejection reason if applicable
    version: int = 0

    def __post_init__(self):
        for attr in ('proposed_at', 'approved_at', 'executed_at', 'expiry'):
            val = getattr(self, attr)
            if val and val.tzinfo is None:
                setattr(self, attr, val.replace(tzinfo=timezone.utc))
        if isinstance(self.status, str):
            self.status = ConfigStatus(self.status)
        if isinstance(self.category, str):
            self.category = ConfigCategory(self.category)


@dataclass
class Policy:
    """
    Network policy record.

    Maps to the Policy Table in docs/nib_spec.md.
    Policy is always written by GC and distributed downward.
    Regional controllers never write policy directly.
    """
    policy_id: str
    policy_version: str                         # e.g., "region1-v3.2"
    scope: str                                  # global | regional | local
    content: str                                # JSON policy rules
    distributed_by: str                         # Controller that pushed this
    is_active: bool = True
    target_region: Optional[str] = None         # None for global scope
    distributed_at: Optional[datetime] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None      # None = indefinite
    version: int = 0

    def __post_init__(self):
        for attr in ('distributed_at', 'valid_from', 'valid_until'):
            val = getattr(self, attr)
            if val and val.tzinfo is None:
                setattr(self, attr, val.replace(tzinfo=timezone.utc))


@dataclass
class Event:
    """
    Immutable audit log entry.

    Maps to the Event Log in docs/nib_spec.md.
    Append-only — database triggers prevent UPDATE and DELETE.
    Every significant action in PDSNO produces at least one Event.
    """
    event_id: str
    event_type: str     # DISCOVERY | VALIDATION | CONFIG_PROPOSAL | APPROVAL | EXECUTION | etc.
    actor: str          # Controller ID that triggered the event
    timestamp: datetime
    action: str         # Human-readable description of what happened
    subject: Optional[str] = None       # Device ID, controller ID, or proposal ID
    decision: Optional[str] = None      # APPROVED | DENIED | FLAGGED | N/A
    payload_ref: Optional[str] = None   # Reference to full payload if large
    notes: Optional[str] = None         # Optional operator or system notes
    signature: Optional[str] = None     # HMAC signature for tamper-evidence
    details: Dict[str, Any] = field(default_factory=dict)  # Structured payload

    def __post_init__(self):
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)


@dataclass
class Lock:
    """
    Coordination lock for distributed operations.

    Maps to the Controller Sync Table in docs/nib_spec.md.
    Locks are always time-bounded — they expire automatically.
    """
    lock_id: str
    subject_id: str         # Resource being locked (device_id, config_id, etc.)
    lock_type: LockType
    held_by: str            # Controller ID holding the lock
    acquired_at: datetime
    expires_at: datetime
    associated_request: Optional[str] = None  # Proposal ID or validation request ID

    def __post_init__(self):
        for attr in ('acquired_at', 'expires_at'):
            val = getattr(self, attr)
            if val and val.tzinfo is None:
                setattr(self, attr, val.replace(tzinfo=timezone.utc))
        if isinstance(self.lock_type, str):
            self.lock_type = LockType(self.lock_type)

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at


@dataclass
class Controller:
    """
    Controller identity record.

    Maps to the Controller Sync Table in docs/nib_spec.md.
    Every validated controller has exactly one record here.
    """
    controller_id: str
    role: str                               # global | regional | local
    region: Optional[str] = None
    status: str = "active"                  # active | inactive | validating
    validated_by: Optional[str] = None      # Parent controller that validated this
    validated_at: Optional[datetime] = None
    public_key: Optional[str] = None
    certificate: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: int = 0

    def __post_init__(self):
        if self.validated_at and self.validated_at.tzinfo is None:
            self.validated_at = self.validated_at.replace(tzinfo=timezone.utc)


@dataclass
class NIBResult:
    """
    Result of a NIB write operation.

    Every NIBStore method that modifies state returns a NIBResult.
    Callers MUST check result.success before proceeding.

    Example:
        result = nib.upsert_device(device)
        if not result.success:
            raise SomeAppropriateError(result.error)
    """
    success: bool
    error: Optional[str] = None
    data: Optional[Any] = None
    conflict: bool = False