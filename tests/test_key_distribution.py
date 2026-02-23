"""
Tests for Key Distribution (Phase 6D)

Tests Diffie-Hellman key exchange, key distribution protocol,
and key rotation mechanisms.
"""

import pytest
import secrets
from datetime import datetime, timezone, timedelta

from pdsno.security.key_distribution import (
    DHKeyExchange,
    KeyDistributionProtocol,
    KeyRotationScheduler
)
from pdsno.security.message_auth import KeyManager


@pytest.fixture
def key_manager():
    """Create a test key manager"""
    return KeyManager()


@pytest.fixture
def controller_a_protocol(key_manager):
    """Create key distribution protocol for controller A"""
    return KeyDistributionProtocol("controller_a", key_manager)


@pytest.fixture
def controller_b_protocol():
    """Create key distribution protocol for controller B"""
    km = KeyManager()
    return KeyDistributionProtocol("controller_b", km)


class TestDHKeyExchange:
    """Test Diffie-Hellman key exchange"""
    
    def test_initialization(self):
        """Test DH key exchange initialization"""
        dh = DHKeyExchange("test_controller")
        
        assert dh.controller_id == "test_controller"
        assert dh.private_key is not None
        assert dh.public_key is not None
    
    def test_get_public_key_bytes(self):
        """Test public key serialization"""
        dh = DHKeyExchange("test_controller")
        
        public_key_bytes = dh.get_public_key_bytes()
        
        assert isinstance(public_key_bytes, bytes)
        assert b"BEGIN PUBLIC KEY" in public_key_bytes
        assert len(public_key_bytes) > 100  # PEM format is verbose
    
    def test_compute_shared_secret(self):
        """Test shared secret computation"""
        # Create two DH exchanges
        alice = DHKeyExchange("alice")
        bob = DHKeyExchange("bob")
        
        # Exchange public keys
        alice_public = alice.get_public_key_bytes()
        bob_public = bob.get_public_key_bytes()
        
        # Compute shared secrets
        alice_shared = alice.compute_shared_secret(bob_public)
        bob_shared = bob.compute_shared_secret(alice_public)
        
        # Both should have same shared secret
        assert alice_shared == bob_shared
        assert len(alice_shared) == 32  # 256 bits
    
    def test_different_salts_different_keys(self):
        """Test that different salts produce different keys"""
        alice = DHKeyExchange("alice")
        bob = DHKeyExchange("bob")
        
        bob_public = bob.get_public_key_bytes()
        
        # Compute with different salts
        secret1 = alice.compute_shared_secret(bob_public, salt=b"salt1")
        secret2 = alice.compute_shared_secret(bob_public, salt=b"salt2")
        
        assert secret1 != secret2
    
    def test_same_salt_same_key(self):
        """Test that same salt produces same key"""
        alice = DHKeyExchange("alice")
        bob = DHKeyExchange("bob")
        
        bob_public = bob.get_public_key_bytes()
        
        # Compute twice with same salt
        secret1 = alice.compute_shared_secret(bob_public, salt=b"salt1")
        secret2 = alice.compute_shared_secret(bob_public, salt=b"salt1")
        
        assert secret1 == secret2


class TestKeyDistributionProtocol:
    """Test key distribution protocol"""
    
    def test_initialization(self, key_manager):
        """Test protocol initialization"""
        protocol = KeyDistributionProtocol("test_controller", key_manager)
        
        assert protocol.controller_id == "test_controller"
        assert protocol.key_manager is key_manager
        assert len(protocol.active_exchanges) == 0
    
    def test_initiate_key_exchange(self, controller_a_protocol):
        """Test key exchange initiation"""
        init_payload = controller_a_protocol.initiate_key_exchange("controller_b")
        
        # Check payload structure
        assert init_payload["initiator_id"] == "controller_a"
        assert init_payload["responder_id"] == "controller_b"
        assert "public_key" in init_payload
        assert "timestamp" in init_payload
        
        # Check active exchanges
        assert "controller_b" in controller_a_protocol.active_exchanges
    
    def test_respond_to_key_exchange(self, controller_b_protocol):
        """Test key exchange response"""
        # Create init message
        init_payload = {
            "initiator_id": "controller_a",
            "responder_id": "controller_b",
            "public_key": DHKeyExchange("controller_a").get_public_key_bytes().decode('utf-8'),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        response_payload = controller_b_protocol.respond_to_key_exchange(init_payload)
        
        # Check response structure
        assert response_payload["initiator_id"] == "controller_a"
        assert response_payload["responder_id"] == "controller_b"
        assert "public_key" in response_payload
        
        # Check key stored
        key_id = controller_b_protocol.key_manager.derive_key_id("controller_b", "controller_a")
        stored_key = controller_b_protocol.key_manager.get_key(key_id)
        assert stored_key is not None
        assert len(stored_key) == 32
    
    def test_finalize_key_exchange(self, controller_a_protocol):
        """Test key exchange finalization"""
        # Initiate
        init_payload = controller_a_protocol.initiate_key_exchange("controller_b")
        
        # Create response
        response_payload = {
            "initiator_id": "controller_a",
            "responder_id": "controller_b",
            "public_key": DHKeyExchange("controller_b").get_public_key_bytes().decode('utf-8'),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Finalize
        controller_a_protocol.finalize_key_exchange("controller_b", response_payload)
        
        # Check key stored
        key_id = controller_a_protocol.key_manager.derive_key_id("controller_a", "controller_b")
        stored_key = controller_a_protocol.key_manager.get_key(key_id)
        assert stored_key is not None
        assert len(stored_key) == 32
        
        # Check exchange cleaned up
        assert "controller_b" not in controller_a_protocol.active_exchanges
    
    def test_full_key_exchange_flow(self):
        """Test complete key exchange between two controllers"""
        # Create both protocols
        km_a = KeyManager()
        km_b = KeyManager()
        
        protocol_a = KeyDistributionProtocol("controller_a", km_a)
        protocol_b = KeyDistributionProtocol("controller_b", km_b)
        
        # Step 1: A initiates
        init_msg = protocol_a.initiate_key_exchange("controller_b")
        
        # Step 2: B responds
        response_msg = protocol_b.respond_to_key_exchange(init_msg)
        
        # Step 3: A finalizes
        protocol_a.finalize_key_exchange("controller_b", response_msg)
        
        # Both should have same shared secret
        key_id_a = km_a.derive_key_id("controller_a", "controller_b")
        key_id_b = km_b.derive_key_id("controller_b", "controller_a")
        
        secret_a = km_a.get_key(key_id_a)
        secret_b = km_b.get_key(key_id_b)
        
        assert secret_a == secret_b
        assert len(secret_a) == 32
    
    def test_finalize_without_initiate_fails(self, controller_a_protocol):
        """Test that finalize fails without prior initiate"""
        response_payload = {
            "initiator_id": "controller_a",
            "responder_id": "controller_b",
            "public_key": DHKeyExchange("controller_b").get_public_key_bytes().decode('utf-8'),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        with pytest.raises(ValueError, match="No active key exchange"):
            controller_a_protocol.finalize_key_exchange("controller_b", response_payload)


class TestKeyRotationScheduler:
    """Test key rotation scheduler"""
    
    def test_initialization(self, key_manager):
        """Test scheduler initialization"""
        scheduler = KeyRotationScheduler(key_manager, rotation_interval_days=90)
        
        assert scheduler.key_manager is key_manager
        assert scheduler.rotation_interval == timedelta(days=90)
        assert len(scheduler.key_metadata) == 0
    
    def test_register_key(self, key_manager):
        """Test key registration"""
        scheduler = KeyRotationScheduler(key_manager, rotation_interval_days=90)
        
        scheduler.register_key("test_key_1")
        
        assert "test_key_1" in scheduler.key_metadata
        metadata = scheduler.key_metadata["test_key_1"]
        assert metadata["status"] == "active"
        assert "created_at" in metadata
        assert "rotates_at" in metadata
    
    def test_check_rotation_needed_not_due(self, key_manager):
        """Test rotation check when not due"""
        scheduler = KeyRotationScheduler(key_manager, rotation_interval_days=90)
        
        scheduler.register_key("test_key_1")
        
        needs_rotation = scheduler.check_rotation_needed()
        
        assert len(needs_rotation) == 0
    
    def test_check_rotation_needed_due(self, key_manager):
        """Test rotation check when due"""
        scheduler = KeyRotationScheduler(key_manager, rotation_interval_days=0)  # Immediate rotation
        
        scheduler.register_key("test_key_1")
        
        # Wait a moment
        import time
        time.sleep(0.1)
        
        needs_rotation = scheduler.check_rotation_needed()
        
        assert "test_key_1" in needs_rotation
    
    def test_initiate_rotation(self, key_manager):
        """Test rotation initiation"""
        scheduler = KeyRotationScheduler(key_manager, rotation_interval_days=90)
        
        # Create and register old key
        old_key = secrets.token_bytes(32)
        key_manager.set_key("old_key", old_key)
        scheduler.register_key("old_key")
        
        # Initiate rotation
        new_key_id = scheduler.initiate_rotation("old_key")
        
        # Check new key created
        assert new_key_id == "old_key_v2"
        assert key_manager.get_key(new_key_id) is not None
        
        # Check old key status
        assert scheduler.key_metadata["old_key"]["status"] == "rotating"
        
        # Check new key registered
        assert new_key_id in scheduler.key_metadata
    
    def test_complete_rotation(self, key_manager):
        """Test rotation completion"""
        scheduler = KeyRotationScheduler(key_manager, rotation_interval_days=90)
        
        # Create and register old key
        old_key = secrets.token_bytes(32)
        key_manager.set_key("old_key", old_key)
        scheduler.register_key("old_key")
        
        # Complete rotation
        scheduler.complete_rotation("old_key")
        
        # Check old key deleted
        assert key_manager.get_key("old_key") is None
        assert scheduler.key_metadata["old_key"]["status"] == "deleted"
    
    def test_full_rotation_cycle(self, key_manager):
        """Test complete rotation cycle"""
        scheduler = KeyRotationScheduler(key_manager, rotation_interval_days=0)
        
        # Register key
        key_manager.set_key("key_v1", secrets.token_bytes(32))
        scheduler.register_key("key_v1")
        
        # Check rotation needed
        import time
        time.sleep(0.1)
        needs_rotation = scheduler.check_rotation_needed()
        assert "key_v1" in needs_rotation
        
        # Initiate rotation
        new_key_id = scheduler.initiate_rotation("key_v1")
        assert new_key_id == "key_v1_v2"
        
        # Both keys exist
        assert key_manager.get_key("key_v1") is not None
        assert key_manager.get_key(new_key_id) is not None
        
        # Complete rotation
        scheduler.complete_rotation("key_v1")
        
        # Only new key exists
        assert key_manager.get_key("key_v1") is None
        assert key_manager.get_key(new_key_id) is not None


class TestKeyDistributionIntegration:
    """Integration tests for key distribution"""
    
    def test_multiple_controller_key_exchange(self):
        """Test key exchange between multiple controllers"""
        # Create 3 controllers
        km_gc = KeyManager()
        km_rc1 = KeyManager()
        km_rc2 = KeyManager()
        
        protocol_gc = KeyDistributionProtocol("global_cntl_1", km_gc)
        protocol_rc1 = KeyDistributionProtocol("regional_cntl_1", km_rc1)
        protocol_rc2 = KeyDistributionProtocol("regional_cntl_2", km_rc2)
        
        # RC1 exchanges with GC
        init1 = protocol_rc1.initiate_key_exchange("global_cntl_1")
        resp1 = protocol_gc.respond_to_key_exchange(init1)
        protocol_rc1.finalize_key_exchange("global_cntl_1", resp1)
        
        # RC2 exchanges with GC
        init2 = protocol_rc2.initiate_key_exchange("global_cntl_1")
        resp2 = protocol_gc.respond_to_key_exchange(init2)
        protocol_rc2.finalize_key_exchange("global_cntl_1", resp2)
        
        # Verify all have keys
        assert km_gc.get_key(km_gc.derive_key_id("global_cntl_1", "regional_cntl_1")) is not None
        assert km_gc.get_key(km_gc.derive_key_id("global_cntl_1", "regional_cntl_2")) is not None
        assert km_rc1.get_key(km_rc1.derive_key_id("regional_cntl_1", "global_cntl_1")) is not None
        assert km_rc2.get_key(km_rc2.derive_key_id("regional_cntl_2", "global_cntl_1")) is not None
        
        # Keys between RC1-GC and RC2-GC should be different
        key_rc1_gc = km_gc.get_key(km_gc.derive_key_id("global_cntl_1", "regional_cntl_1"))
        key_rc2_gc = km_gc.get_key(km_gc.derive_key_id("global_cntl_1", "regional_cntl_2"))
        assert key_rc1_gc != key_rc2_gc


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
