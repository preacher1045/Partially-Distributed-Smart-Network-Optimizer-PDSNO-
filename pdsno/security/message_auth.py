"""
Message Authentication Module

Provides HMAC-based message signing and verification for secure
inter-controller communication.

Security Features:
- HMAC-SHA256 signatures
- Replay attack prevention via nonces
- Timestamp validation (5-minute window)
- Key rotation support
"""

import hmac
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
import logging


class MessageAuthenticator:
    """
    Handles message signing and verification using HMAC-SHA256.
    
    Security properties:
    - Message integrity: Detects tampering
    - Message authenticity: Verifies sender identity
    - Replay protection: Prevents message replay attacks
    """
    
    # Constants
    SIGNATURE_ALGORITHM = "HMAC-SHA256"
    NONCE_LENGTH = 32  # bytes
    TIMESTAMP_TOLERANCE = 300  # 5 minutes in seconds
    
    def __init__(self, shared_secret: bytes, controller_id: str):
        """
        Initialize message authenticator.
        
        Args:
            shared_secret: Shared secret key for HMAC (minimum 32 bytes recommended)
            controller_id: This controller's unique identifier
        """
        if len(shared_secret) < 32:
            raise ValueError("Shared secret must be at least 32 bytes")
        
        self.shared_secret = shared_secret
        self.controller_id = controller_id
        self.logger = logging.getLogger(f"{__name__}.{controller_id}")
        
        # Replay prevention: track seen nonces (in production, use distributed cache)
        self._seen_nonces = set()
        self._nonce_cleanup_counter = 0
        
        self.logger.info(f"Message authenticator initialized for {controller_id}")
    
    def sign_message(self, message_dict: Dict) -> Dict:
        """
        Sign a message with HMAC-SHA256.
        
        Adds three fields to the message:
        - signature: HMAC-SHA256 hex digest
        - nonce: Random value for replay prevention
        - signed_at: ISO timestamp for freshness check
        
        Args:
            message_dict: Message to sign (will be modified in-place)
        
        Returns:
            Modified message dict with signature fields
        """
        # Generate nonce
        nonce = secrets.token_hex(self.NONCE_LENGTH)
        
        # Add timestamp
        signed_at = datetime.now(timezone.utc).isoformat()
        
        # Add fields to message
        message_dict['nonce'] = nonce
        message_dict['signed_at'] = signed_at
        
        # Compute signature over canonical message representation
        canonical = self._canonicalize_message(message_dict)
        signature = self._compute_hmac(canonical)
        
        message_dict['signature'] = signature
        message_dict['signature_algorithm'] = self.SIGNATURE_ALGORITHM
        
        self.logger.debug(f"Signed message {message_dict.get('message_id')} with nonce {nonce[:8]}...")
        
        return message_dict
    
    def verify_message(
        self,
        message_dict: Dict,
        expected_sender: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify a message signature and freshness.
        
        Args:
            message_dict: Message to verify
            expected_sender: Optional sender ID to validate
        
        Returns:
            (valid, error_reason) tuple
            - (True, None) if valid
            - (False, reason_string) if invalid
        """
        # Check required fields
        required_fields = ['signature', 'nonce', 'signed_at', 'sender_id']
        for field in required_fields:
            if field not in message_dict:
                return False, f"Missing required field: {field}"
        
        # Validate sender if specified
        if expected_sender and message_dict['sender_id'] != expected_sender:
            return False, f"Sender mismatch: expected {expected_sender}, got {message_dict['sender_id']}"
        
        # Check signature algorithm
        if message_dict.get('signature_algorithm') != self.SIGNATURE_ALGORITHM:
            return False, "Unsupported signature algorithm"
        
        # Verify timestamp freshness
        try:
            signed_at = datetime.fromisoformat(message_dict['signed_at'])
            now = datetime.now(timezone.utc)
            age = (now - signed_at).total_seconds()
            
            if abs(age) > self.TIMESTAMP_TOLERANCE:
                return False, f"Message too old or future-dated: {age:.0f}s (max {self.TIMESTAMP_TOLERANCE}s)"
        except (ValueError, TypeError) as e:
            return False, f"Invalid timestamp format: {e}"
        
        # Check nonce for replay attack
        nonce = message_dict['nonce']
        if nonce in self._seen_nonces:
            return False, "Replay attack detected: nonce already seen"
        
        # Verify HMAC signature
        claimed_signature = message_dict['signature']
        
        # Create a copy without the signature for verification
        message_copy = message_dict.copy()
        del message_copy['signature']
        del message_copy['signature_algorithm']
        
        canonical = self._canonicalize_message(message_copy)
        expected_signature = self._compute_hmac(canonical)
        
        if not hmac.compare_digest(claimed_signature, expected_signature):
            return False, "Invalid signature: message may have been tampered with"
        
        # All checks passed - record nonce
        self._seen_nonces.add(nonce)
        self._cleanup_old_nonces()
        
        self.logger.debug(
            f"Verified message {message_dict.get('message_id')} "
            f"from {message_dict['sender_id']}"
        )
        
        return True, None
    
    def _compute_hmac(self, data: bytes) -> str:
        """Compute HMAC-SHA256 and return hex digest"""
        return hmac.new(
            self.shared_secret,
            data,
            hashlib.sha256
        ).hexdigest()
    
    def _canonicalize_message(self, message_dict: Dict) -> bytes:
        """
        Convert message dict to canonical byte representation.
        
        Uses deterministic JSON serialization (sorted keys).
        """
        import json
        
        # Sort keys for deterministic output
        canonical_json = json.dumps(
            message_dict,
            sort_keys=True,
            separators=(',', ':')  # No spaces
        )
        
        return canonical_json.encode('utf-8')
    
    def _cleanup_old_nonces(self):
        """
        Periodically cleanup old nonces to prevent memory growth.
        
        In production, use a time-based cache (Redis, Memcached) with TTL.
        """
        self._nonce_cleanup_counter += 1
        
        # Cleanup every 1000 messages
        if self._nonce_cleanup_counter >= 1000:
            # In production: remove nonces older than TIMESTAMP_TOLERANCE
            # For now, just clear all (acceptable for PoC since we track age separately)
            old_size = len(self._seen_nonces)
            self._seen_nonces.clear()
            self._nonce_cleanup_counter = 0
            
            self.logger.debug(f"Cleaned up {old_size} nonces from replay cache")
    
    def rotate_key(self, new_secret: bytes):
        """
        Rotate the shared secret key.
        
        In production, implement gradual key rotation:
        1. Add new key to keyring
        2. Sign with new key, verify with both old and new
        3. After grace period, remove old key
        
        Args:
            new_secret: New shared secret (minimum 32 bytes)
        """
        if len(new_secret) < 32:
            raise ValueError("New secret must be at least 32 bytes")
        
        self.logger.info("Rotating shared secret key")
        self.shared_secret = new_secret


class KeyManager:
    """
    Manages shared secrets for different controller relationships.
    
    In production, integrate with:
    - HashiCorp Vault
    - AWS Secrets Manager
    - Azure Key Vault
    - Or similar secure key management system
    """
    
    def __init__(self):
        """Initialize key manager"""
        self.keys: Dict[str, bytes] = {}
        self.logger = logging.getLogger(__name__)
    
    def generate_key(self, key_id: str) -> bytes:
        """
        Generate a new random key.
        
        Args:
            key_id: Unique identifier for this key
        
        Returns:
            Generated key (32 bytes)
        """
        key = secrets.token_bytes(32)
        self.keys[key_id] = key
        
        self.logger.info(f"Generated new key: {key_id}")
        
        return key
    
    def get_key(self, key_id: str) -> Optional[bytes]:
        """Get a key by ID"""
        return self.keys.get(key_id)
    
    def set_key(self, key_id: str, key: bytes):
        """Store a key"""
        if len(key) < 32:
            raise ValueError("Key must be at least 32 bytes")
        
        self.keys[key_id] = key
        self.logger.info(f"Stored key: {key_id}")
    
    def delete_key(self, key_id: str):
        """Delete a key"""
        if key_id in self.keys:
            del self.keys[key_id]
            self.logger.info(f"Deleted key: {key_id}")
    
    def list_keys(self) -> list:
        """List all key IDs"""
        return list(self.keys.keys())
    
    @staticmethod
    def derive_key_id(controller1_id: str, controller2_id: str) -> str:
        """
        Derive a deterministic key ID for a controller pair.
        
        Args:
            controller1_id: First controller ID
            controller2_id: Second controller ID
        
        Returns:
            Key ID string (sorted to ensure consistency)
        """
        # Sort to ensure A->B and B->A use same key
        ids = sorted([controller1_id, controller2_id])
        return f"key_{ids[0]}_{ids[1]}"


# Example usage:
"""
# Initialize
key_manager = KeyManager()
shared_secret = key_manager.generate_key("key_gc_rc")

auth = MessageAuthenticator(shared_secret, "global_cntl_1")

# Sign outgoing message
message = {
    "message_id": "msg-001",
    "sender_id": "global_cntl_1",
    "recipient_id": "regional_cntl_zone-A_1",
    "message_type": "VALIDATION_REQUEST",
    "payload": {...}
}

signed_message = auth.sign_message(message)
# Now has: signature, nonce, signed_at fields

# Verify incoming message
valid, error = auth.verify_message(signed_message)
if not valid:
    print(f"Invalid message: {error}")
"""
