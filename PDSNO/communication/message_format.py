"""
PDSNO Message Format

Defines the standard message envelope for all inter-controller communication.
Based on docs/communication_model.md and docs/api_reference.md
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from enum import Enum
import uuid


class MessageType(Enum):
    """Standard PDSNO message types"""
    # Controller Validation
    VALIDATION_REQUEST = "VALIDATION_REQUEST"
    CHALLENGE = "CHALLENGE"
    CHALLENGE_RESPONSE = "CHALLENGE_RESPONSE"
    VALIDATION_RESULT = "VALIDATION_RESULT"
    
    # Discovery
    DISCOVERY_REQUEST = "DISCOVERY_REQUEST"
    DISCOVERY_REPORT = "DISCOVERY_REPORT"
    DISCOVERY_SUMMARY = "DISCOVERY_SUMMARY"
    
    # Config Approval
    CONFIG_PROPOSAL = "CONFIG_PROPOSAL"
    CONFIG_APPROVAL = "CONFIG_APPROVAL"
    CONFIG_REJECTION = "CONFIG_REJECTION"
    
    # Policy Distribution
    POLICY_UPDATE = "POLICY_UPDATE"
    POLICY_ACK = "POLICY_ACK"
    
    # Sync & Heartbeat
    HEARTBEAT = "HEARTBEAT"
    SYNC_REQUEST = "SYNC_REQUEST"
    SYNC_RESPONSE = "SYNC_RESPONSE"


@dataclass
class MessageEnvelope:
    """
    Standard message envelope for all PDSNO inter-controller messages.
    
    Every message includes this envelope for routing, authentication,
    and debugging purposes.
    """
    message_id: str = field(default_factory=lambda: f"msg-{uuid.uuid4().hex[:12]}")
    message_type: MessageType = MessageType.HEARTBEAT
    sender_id: str = ""
    recipient_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payload: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None  # For request-response pairing
    
    def __post_init__(self):
        """Ensure timestamp is timezone-aware"""
        if isinstance(self.timestamp, str):
            self.timestamp = datetime.fromisoformat(self.timestamp)
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)
        
        # Convert string to enum if needed
        if isinstance(self.message_type, str):
            self.message_type = MessageType(self.message_type)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize message to dictionary"""
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "correlation_id": self.correlation_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageEnvelope':
        """Deserialize message from dictionary"""
        return cls(
            message_id=data["message_id"],
            message_type=MessageType(data["message_type"]),
            sender_id=data["sender_id"],
            recipient_id=data["recipient_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            payload=data.get("payload", {}),
            correlation_id=data.get("correlation_id")
        )


@dataclass
class ValidationRequest:
    """Request for controller validation"""
    temp_id: str
    controller_type: str  # "regional" or "local"
    region: str
    public_key: str  # Base64 encoded Ed25519 public key
    bootstrap_token: str  # HMAC-SHA256 of temp_id with shared secret
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "temp_id": self.temp_id,
            "controller_type": self.controller_type,
            "region": self.region,
            "public_key": self.public_key,
            "bootstrap_token": self.bootstrap_token,
            "metadata": self.metadata
        }


@dataclass
class Challenge:
    """Challenge for controller validation"""
    challenge_id: str
    temp_id: str
    nonce: str  # Base64 encoded 32-byte random
    issued_at: datetime
    expires_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "challenge_id": self.challenge_id,
            "temp_id": self.temp_id,
            "nonce": self.nonce,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat()
        }


@dataclass
class ChallengeResponse:
    """Response to validation challenge"""
    challenge_id: str
    temp_id: str
    signed_nonce: str  # Base64 encoded Ed25519 signature
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "challenge_id": self.challenge_id,
            "temp_id": self.temp_id,
            "signed_nonce": self.signed_nonce
        }


@dataclass
class ValidationResult:
    """Result of validation process"""
    status: str  # "APPROVED", "REJECTED", "ERROR"
    assigned_id: Optional[str] = None
    certificate: Optional[Dict[str, Any]] = None
    role: Optional[str] = None
    region: Optional[str] = None
    reason: Optional[str] = None  # For REJECTED/ERROR
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "assigned_id": self.assigned_id,
            "certificate": self.certificate,
            "role": self.role,
            "region": self.region,
            "reason": self.reason
        }
