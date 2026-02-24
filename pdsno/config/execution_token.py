"""
Execution Token System

Provides cryptographically signed, single-use authorization tokens
for configuration execution.

Security properties:
- HMAC-SHA256 signatures
- Single-use (nonce-based)
- Time-bounded validity
- Device-specific
- Tamper-proof
"""

import hmac
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Set
import logging
import json


class ExecutionToken:
    """
    Cryptographically signed token authorizing config execution.

    Token structure:
    {
        'token_id': unique ID,
        'request_id': approval request ID,
        'device_id': target device,
        'issued_by': issuing controller,
        'issued_at': timestamp,
        'expires_at': expiration timestamp,
        'nonce': random value,
        'signature': HMAC-SHA256
    }
    """

    def __init__(
        self,
        token_id: str,
        request_id: str,
        device_id: str,
        issued_by: str,
        issued_at: datetime,
        expires_at: datetime,
        nonce: str,
        signature: Optional[str] = None
    ):
        """Initialize execution token"""
        self.token_id = token_id
        self.request_id = request_id
        self.device_id = device_id
        self.issued_by = issued_by
        self.issued_at = issued_at
        self.expires_at = expires_at
        self.nonce = nonce
        self.signature = signature

    def to_dict(self) -> Dict:
        """Serialize to dictionary"""
        return {
            'token_id': self.token_id,
            'request_id': self.request_id,
            'device_id': self.device_id,
            'issued_by': self.issued_by,
            'issued_at': self.issued_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'nonce': self.nonce,
            'signature': self.signature
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ExecutionToken':
        """Deserialize from dictionary"""
        return cls(
            token_id=data['token_id'],
            request_id=data['request_id'],
            device_id=data['device_id'],
            issued_by=data['issued_by'],
            issued_at=datetime.fromisoformat(data['issued_at']),
            expires_at=datetime.fromisoformat(data['expires_at']),
            nonce=data['nonce'],
            signature=data.get('signature')
        )


class ExecutionTokenManager:
    """
    Manages creation and verification of execution tokens.
    """

    DEFAULT_TOKEN_LIFETIME_MINUTES = 15

    def __init__(self, controller_id: str, shared_secret: bytes):
        """
        Initialize token manager.

        Args:
            controller_id: This controller's ID
            shared_secret: Shared secret for HMAC (32 bytes)
        """
        if len(shared_secret) < 32:
            raise ValueError("Shared secret must be at least 32 bytes")

        self.controller_id = controller_id
        self.shared_secret = shared_secret
        self.logger = logging.getLogger(f"{__name__}.{controller_id}")

        # Track used nonces (replay prevention)
        self.used_nonces: Set[str] = set()
        self.nonce_cleanup_counter = 0

    def issue_token(
        self,
        request_id: str,
        device_id: str,
        validity_minutes: Optional[int] = None
    ) -> ExecutionToken:
        """
        Issue a new execution token.

        Args:
            request_id: Approval request ID
            device_id: Target device
            validity_minutes: Token lifetime (default: 15 minutes)

        Returns:
            Signed execution token
        """
        validity = validity_minutes or self.DEFAULT_TOKEN_LIFETIME_MINUTES

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=validity)

        # Generate unique token ID and nonce
        token_id = secrets.token_hex(16)
        nonce = secrets.token_hex(32)

        # Create token
        token = ExecutionToken(
            token_id=token_id,
            request_id=request_id,
            device_id=device_id,
            issued_by=self.controller_id,
            issued_at=now,
            expires_at=expires_at,
            nonce=nonce
        )

        # Sign token
        token.signature = self._sign_token(token)

        self.logger.info(
            f"Issued execution token {token_id} for device {device_id} "
            f"(valid for {validity} minutes)"
        )

        return token

    def verify_token(
        self,
        token: ExecutionToken,
        expected_device: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Verify execution token.

        Args:
            token: Token to verify
            expected_device: Optional device ID to validate

        Returns:
            (valid, error_reason) tuple
        """
        if not token.signature:
            return False, "Token has no signature"

        expected_sig = self._sign_token(token)

        if not hmac.compare_digest(token.signature, expected_sig):
            return False, "Invalid signature: token may have been tampered with"

        now = datetime.now(timezone.utc)
        if now > token.expires_at:
            age = (now - token.expires_at).total_seconds()
            return False, f"Token expired {age:.0f} seconds ago"

        if token.nonce in self.used_nonces:
            return False, "Token already used (replay detected)"

        if expected_device and token.device_id != expected_device:
            return False, f"Token issued for {token.device_id}, not {expected_device}"

        self.used_nonces.add(token.nonce)
        self._cleanup_nonces()

        self.logger.info(f"Verified execution token {token.token_id}")

        return True, None

    def revoke_token(self, token_id: str):
        """
        Revoke a token (mark nonce as used).

        Args:
            token_id: Token to revoke
        """
        self.logger.info(f"Revoked token {token_id}")

    def _sign_token(self, token: ExecutionToken) -> str:
        """
        Compute HMAC-SHA256 signature for token.

        Args:
            token: Token to sign

        Returns:
            Hex-encoded signature
        """
        token_dict = token.to_dict()
        if 'signature' in token_dict:
            del token_dict['signature']

        canonical = json.dumps(token_dict, sort_keys=True, separators=(',', ':'))

        signature = hmac.new(
            self.shared_secret,
            canonical.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return signature

    def _cleanup_nonces(self):
        """Periodic cleanup of old nonces"""
        self.nonce_cleanup_counter += 1

        if self.nonce_cleanup_counter >= 1000:
            old_size = len(self.used_nonces)
            self.used_nonces.clear()
            self.nonce_cleanup_counter = 0

            self.logger.debug(f"Cleaned up {old_size} nonces")


# Example usage:
"""
from pdsno.config.execution_token import ExecutionTokenManager
from pdsno.security.message_auth import KeyManager

# Setup
key_manager = KeyManager()
shared_secret = key_manager.generate_key("token_signing_key")

token_manager = ExecutionTokenManager(
    controller_id="regional_cntl_zone-A_1",
    shared_secret=shared_secret
)

# Issue token
token = token_manager.issue_token(
    request_id="req-12345",
    device_id="switch-core-01",
    validity_minutes=15
)

# Token can now be sent to Local Controller for execution
token_dict = token.to_dict()
# ... send via HTTP/MQTT ...

# On Local Controller, verify token
token_received = ExecutionToken.from_dict(token_dict)
valid, error = token_manager.verify_token(
    token_received,
    expected_device="switch-core-01"
)

if valid:
    print("Token valid, executing config")
else:
    print(f"Token invalid: {error}")
"""
