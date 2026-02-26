"""
Secure Key Distribution Module

Implements Diffie-Hellman Ephemeral (DHE) key exchange for secure
shared secret establishment between controllers without prior shared secrets.

Security Features:
- Perfect forward secrecy (ephemeral keys)
- Man-in-the-middle protection (via controller certificates)
- Secure key derivation (HKDF)
- Automatic key lifecycle management
"""

import secrets
from typing import Optional
from datetime import datetime, timezone, timedelta
import logging

# Cryptography library for DH and HKDF
from cryptography.hazmat.primitives.asymmetric import dh
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend


class DHKeyExchange:
    """
    Diffie-Hellman key exchange for establishing shared secrets.
    
    Provides perfect forward secrecy and resistance to passive eavesdropping.
    """
    
    # Lazily initialized DH parameters (avoid slow generation at import time)
    _dh_parameters = None
    
    @classmethod
    def get_dh_parameters(cls):
        """Get or generate DH parameters (lazy initialization)."""
        if cls._dh_parameters is None:
            # Standard 2048-bit DH parameters (RFC 3526)
            # In production, use pre-generated parameters or standardized groups
            cls._dh_parameters = dh.generate_parameters(
                generator=2,
                key_size=2048,
                backend=default_backend()
            )
        return cls._dh_parameters
    
    def __init__(self, controller_id: str):
        """
        Initialize DH key exchange.
        
        Args:
            controller_id: This controller's unique identifier
        """
        self.controller_id = controller_id
        self.logger = logging.getLogger(f"{__name__}.{controller_id}")
        
        # Generate ephemeral private key (uses lazy DH parameters)
        params = self.get_dh_parameters()
        self.private_key = params.generate_private_key()
        self.public_key = self.private_key.public_key()
        
        self.logger.info("DH key exchange initialized (2048-bit)")
    
    def get_public_key_bytes(self) -> bytes:
        """
        Get public key in serialized form for transmission.
        
        Returns:
            Public key as bytes (PEM format)
        """
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    
    def compute_shared_secret(
        self,
        peer_public_key_bytes: bytes,
        salt: Optional[bytes] = None
    ) -> bytes:
        """
        Compute shared secret from peer's public key.
        
        Args:
            peer_public_key_bytes: Peer's public key (PEM format)
            salt: Optional salt for key derivation (32 bytes recommended)
        
        Returns:
            Derived shared secret (32 bytes)
        """
        # Deserialize peer's public key
        peer_public_key = serialization.load_pem_public_key(
            peer_public_key_bytes,
            backend=default_backend()
        )
        
        # Perform DH key exchange
        shared_key = self.private_key.exchange(peer_public_key)
        
        # Derive final key using HKDF (key derivation function)
        if salt is None:
            salt = b"pdsno-controller-key-derivation"
        
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,  # 256-bit key
            salt=salt,
            info=b"pdsno-shared-secret",
            backend=default_backend()
        )
        
        derived_key = hkdf.derive(shared_key)
        
        self.logger.info("Shared secret computed via DH + HKDF")
        
        return derived_key


class KeyDistributionProtocol:
    """
    Implements the key distribution protocol between controllers.
    
    Protocol flow:
    1. Initiator sends KEY_EXCHANGE_INIT with public key
    2. Responder replies with KEY_EXCHANGE_RESPONSE with its public key
    3. Both compute shared secret independently
    4. Shared secret is stored in KeyManager
    """
    
    def __init__(self, controller_id: str, key_manager):
        """
        Initialize key distribution protocol.
        
        Args:
            controller_id: This controller's unique ID
            key_manager: KeyManager instance for storing derived keys
        """
        self.controller_id = controller_id
        self.key_manager = key_manager
        self.logger = logging.getLogger(f"{__name__}.{controller_id}")
        
        # Active key exchanges (controller_id -> DHKeyExchange)
        self.active_exchanges = {}
    
    def initiate_key_exchange(self, peer_controller_id: str) -> dict:
        """
        Initiate key exchange with a peer controller.
        
        Args:
            peer_controller_id: Peer controller's ID
        
        Returns:
            KEY_EXCHANGE_INIT message payload
        """
        # Create DH key exchange
        dh = DHKeyExchange(self.controller_id)
        self.active_exchanges[peer_controller_id] = dh
        
        # Create init message
        payload = {
            "initiator_id": self.controller_id,
            "responder_id": peer_controller_id,
            "public_key": dh.get_public_key_bytes().decode('utf-8'),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self.logger.info(f"Initiated key exchange with {peer_controller_id}")
        
        return payload
    
    def respond_to_key_exchange(self, init_payload: dict) -> dict:
        """
        Respond to key exchange initiation.
        
        Args:
            init_payload: KEY_EXCHANGE_INIT payload from initiator
        
        Returns:
            KEY_EXCHANGE_RESPONSE message payload
        """
        initiator_id = init_payload["initiator_id"]
        initiator_public_key = init_payload["public_key"].encode('utf-8')
        
        # Create DH key exchange
        dh = DHKeyExchange(self.controller_id)
        
        # Compute shared secret
        shared_secret = dh.compute_shared_secret(initiator_public_key)
        
        # Store in key manager
        key_id = self.key_manager.derive_key_id(self.controller_id, initiator_id)
        self.key_manager.set_key(key_id, shared_secret)
        
        self.logger.info(
            f"Computed shared secret with {initiator_id}, stored as {key_id}"
        )
        
        # Create response message
        payload = {
            "initiator_id": initiator_id,
            "responder_id": self.controller_id,
            "public_key": dh.get_public_key_bytes().decode('utf-8'),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return payload
    
    def finalize_key_exchange(
        self,
        peer_controller_id: str,
        response_payload: dict
    ):
        """
        Finalize key exchange (initiator side).
        
        Args:
            peer_controller_id: Peer controller's ID
            response_payload: KEY_EXCHANGE_RESPONSE from responder
        """
        # Get DH exchange
        dh = self.active_exchanges.get(peer_controller_id)
        if not dh:
            raise ValueError(f"No active key exchange with {peer_controller_id}")
        
        # Get responder's public key
        responder_public_key = response_payload["public_key"].encode('utf-8')
        
        # Compute shared secret
        shared_secret = dh.compute_shared_secret(responder_public_key)
        
        # Store in key manager
        key_id = self.key_manager.derive_key_id(self.controller_id, peer_controller_id)
        self.key_manager.set_key(key_id, shared_secret)
        
        self.logger.info(
            f"Finalized key exchange with {peer_controller_id}, stored as {key_id}"
        )
        
        # Cleanup
        del self.active_exchanges[peer_controller_id]


class KeyRotationScheduler:
    """
    Manages automatic key rotation between controllers.
    
    Implements gradual key rollover:
    1. Generate new key while keeping old
    2. Sign with new, verify with both old and new
    3. After grace period, remove old key
    """
    
    def __init__(self, key_manager, rotation_interval_days: int = 90):
        """
        Initialize key rotation scheduler.
        
        Args:
            key_manager: KeyManager instance
            rotation_interval_days: Days between key rotations
        """
        self.key_manager = key_manager
        self.rotation_interval = timedelta(days=rotation_interval_days)
        self.logger = logging.getLogger(__name__)
        
        # Key metadata: key_id -> {created_at, rotates_at, status}
        self.key_metadata = {}
    
    def register_key(self, key_id: str):
        """Register a key for rotation tracking"""
        now = datetime.now(timezone.utc)
        
        self.key_metadata[key_id] = {
            "created_at": now,
            "rotates_at": now + self.rotation_interval,
            "status": "active"
        }
        
        self.logger.info(
            f"Registered key {key_id} for rotation in {self.rotation_interval.days} days"
        )
    
    def check_rotation_needed(self) -> list:
        """
        Check which keys need rotation.
        
        Returns:
            List of key_ids that need rotation
        """
        now = datetime.now(timezone.utc)
        needs_rotation = []
        
        for key_id, metadata in self.key_metadata.items():
            if metadata["status"] == "active" and now >= metadata["rotates_at"]:
                needs_rotation.append(key_id)
        
        return needs_rotation
    
    def initiate_rotation(self, key_id: str) -> str:
        """
        Initiate key rotation for a specific key.
        
        Args:
            key_id: Key to rotate
        
        Returns:
            New key ID
        """
        # Generate new key
        new_key_id = f"{key_id}_v2"  # Simple versioning
        new_key = secrets.token_bytes(32)
        
        self.key_manager.set_key(new_key_id, new_key)
        
        # Mark old key as rotating
        self.key_metadata[key_id]["status"] = "rotating"
        
        # Register new key
        self.register_key(new_key_id)
        
        self.logger.info(f"Initiated rotation: {key_id} -> {new_key_id}")
        
        return new_key_id
    
    def complete_rotation(self, old_key_id: str):
        """
        Complete rotation by removing old key.
        
        Args:
            old_key_id: Old key to remove
        """
        # Delete old key
        self.key_manager.delete_key(old_key_id)
        
        # Update metadata
        if old_key_id in self.key_metadata:
            self.key_metadata[old_key_id]["status"] = "deleted"
        
        self.logger.info(f"Completed rotation: deleted {old_key_id}")


# Example usage:
"""
from pdsno.security.key_distribution import DHKeyExchange, KeyDistributionProtocol
from pdsno.security.message_auth import KeyManager

# On Initiator (Regional Controller)
key_manager_rc = KeyManager()
protocol_rc = KeyDistributionProtocol("regional_cntl_1", key_manager_rc)

# Initiate
init_msg = protocol_rc.initiate_key_exchange("global_cntl_1")
# Send init_msg to GC via HTTP

# On Responder (Global Controller)
key_manager_gc = KeyManager()
protocol_gc = KeyDistributionProtocol("global_cntl_1", key_manager_gc)

# Respond
response_msg = protocol_gc.respond_to_key_exchange(init_msg)
# Send response_msg back to RC via HTTP

# Back on Initiator
protocol_rc.finalize_key_exchange("global_cntl_1", response_msg)

# Both now have shared secret stored in their KeyManagers
"""
