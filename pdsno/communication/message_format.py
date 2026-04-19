# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""
PDSNO Message Format

Defines the standard message envelope for all inter-controller communication.
Based on docs/foundations/03_communication_model.md and docs/reference/01_api_reference.md
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from enum import Enum
import uuid


def _parse_iso8601(value: str) -> datetime:
    """Parse ISO-8601 timestamps, including trailing 'Z' UTC form."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


class MessageType(Enum):
    """
    Standard PDSNO message types
    Categorized by communication phase and purpose.
    
    Each message type corresponds to a specific interaction pattern
    between controllers, such as validation, discovery, configuration,
    policy distribution, synchronization, and key management.
    
    This enum serves as a central reference for all message types used in
    the PDSNO communication protocol, ensuring consistency and clarity
    across the codebase and documentation.
        
        message_type values are used in the MessageEnvelope to indicate the purpose
        of the message and to route it to the appropriate handler.
        
        VALIDATION_REQUEST: Sent by a controller seeking validation to the validating authority.
        CHALLENGE: Sent by the validating authority to the controller as part of the validation process.
        CHALLENGE_RESPONSE: Sent by the controller in response to a challenge during validation.
        VALIDATION_RESULT: Sent by the validating authority to indicate the result of the validation process.
        DISCOVERY_REQUEST: Sent by a controller to discover other controllers in the network.
        DISCOVERY_REPORT: Sent by a controller in response to a discovery request, containing its details.
        DISCOVERY_REPORT_ACK: Sent by the requester to acknowledge receipt of a discovery report.
        DISCOVERY_SUMMARY: Sent by a controller to summarize the current state of discovered controllers.
        CONFIG_PROPOSAL: Sent by a controller proposing a configuration change to the validating authority.
        CONFIG_APPROVAL: Sent by the validating authority to approve a proposed configuration change.
        CONFIG_REJECTION: Sent by the validating authority to reject a proposed configuration change.
        EXECUTION_INSTRUCTION: Sent by the validating authority to instruct a controller to execute a configuration change.
        EXECUTION_RESULT: Sent by a controller to report the result of executing a configuration change.
        POLICY_UPDATE: Sent by the validating authority to distribute a new or updated policy to controllers.
        POLICY_ACK: Sent by a controller to acknowledge receipt of a policy update.
        HEARTBEAT: Sent periodically by controllers to indicate they are alive and functioning.
        SYNC_REQUEST: Sent by a controller to request synchronization of state or configuration.
        SYNC_RESPONSE: Sent by a controller in response to a sync request, containing the requested information.
        KEY_EXCHANGE_INIT: Sent by a controller to initiate a key exchange process with another controller.
        KEY_EXCHANGE_RESPONSE: Sent by a controller in response to a key exchange initiation, containing its public key and other necessary information.
        KEY_ROTATION_REQUEST: Sent by a controller to request a key rotation from the validating authority.
        KEY_ROTATION_ACK: Sent by the validating authority to acknowledge a key rotation request and provide necessary information for the rotation process. 
        
    """
    # Controller Validation
    VALIDATION_REQUEST = "VALIDATION_REQUEST"
    CHALLENGE = "CHALLENGE"
    CHALLENGE_RESPONSE = "CHALLENGE_RESPONSE"
    VALIDATION_RESULT = "VALIDATION_RESULT"
    
    # Discovery
    DISCOVERY_REQUEST = "DISCOVERY_REQUEST"
    DISCOVERY_REPORT = "DISCOVERY_REPORT"
    DISCOVERY_REPORT_ACK = "DISCOVERY_REPORT_ACK"
    DISCOVERY_SUMMARY = "DISCOVERY_SUMMARY"
    
    # Config Approval
    CONFIG_PROPOSAL = "CONFIG_PROPOSAL"
    CONFIG_APPROVAL = "CONFIG_APPROVAL"
    CONFIG_REJECTION = "CONFIG_REJECTION"
    EXECUTION_INSTRUCTION = "EXECUTION_INSTRUCTION"
    EXECUTION_RESULT = "EXECUTION_RESULT"
    
    # Policy Distribution
    POLICY_UPDATE = "POLICY_UPDATE"
    POLICY_ACK = "POLICY_ACK"
    
    # Sync & Heartbeat
    HEARTBEAT = "HEARTBEAT"
    SYNC_REQUEST = "SYNC_REQUEST"
    SYNC_RESPONSE = "SYNC_RESPONSE"
    
    # Key Distribution
    KEY_EXCHANGE_INIT = "KEY_EXCHANGE_INIT"
    KEY_EXCHANGE_RESPONSE = "KEY_EXCHANGE_RESPONSE"
    KEY_ROTATION_REQUEST = "KEY_ROTATION_REQUEST"
    KEY_ROTATION_ACK = "KEY_ROTATION_ACK"


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
            self.timestamp = _parse_iso8601(self.timestamp)
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
            timestamp=_parse_iso8601(data["timestamp"]),
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
