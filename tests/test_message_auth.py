"""
Tests for Message Authentication (Phase 6C)

Tests HMAC signing, signature verification, and replay attack prevention.
"""

import pytest
import time
import secrets
from datetime import datetime, timezone, timedelta

from pdsno.security.message_auth import MessageAuthenticator, KeyManager


@pytest.fixture
def shared_secret():
    """Generate a test shared secret"""
    return secrets.token_bytes(32)


@pytest.fixture
def authenticator(shared_secret):
    """Create a test authenticator"""
    return MessageAuthenticator(shared_secret, "test_controller_1")


@pytest.fixture
def sample_message():
    """Create a sample message"""
    return {
        "message_id": "msg-001",
        "sender_id": "test_controller_1",
        "recipient_id": "test_controller_2",
        "message_type": "TEST_MESSAGE",
        "payload": {"data": "test"}
    }


class TestMessageAuthenticator:
    """Test message signing and verification"""
    
    def test_initialization(self, shared_secret):
        """Test authenticator initialization"""
        auth = MessageAuthenticator(shared_secret, "test_controller")
        
        assert auth.shared_secret == shared_secret
        assert auth.controller_id == "test_controller"
        assert len(auth._seen_nonces) == 0
    
    def test_initialization_short_key(self):
        """Test that short keys are rejected"""
        with pytest.raises(ValueError, match="at least 32 bytes"):
            MessageAuthenticator(b"short", "test_controller")
    
    def test_sign_message(self, authenticator, sample_message):
        """Test message signing"""
        signed = authenticator.sign_message(sample_message.copy())
        
        # Check signature fields added
        assert 'signature' in signed
        assert 'nonce' in signed
        assert 'signed_at' in signed
        assert 'signature_algorithm' in signed
        
        # Check signature format
        assert len(signed['signature']) == 64  # SHA256 hex = 64 chars
        assert len(signed['nonce']) == 64  # 32 bytes hex = 64 chars
        assert signed['signature_algorithm'] == "HMAC-SHA256"
        
        # Check timestamp is recent
        signed_at = datetime.fromisoformat(signed['signed_at'])
        now = datetime.now(timezone.utc)
        assert (now - signed_at).total_seconds() < 1
    
    def test_verify_valid_message(self, authenticator, sample_message):
        """Test verification of valid signed message"""
        signed = authenticator.sign_message(sample_message.copy())
        
        valid, error = authenticator.verify_message(signed)
        
        assert valid is True
        assert error is None
    
    def test_verify_missing_signature(self, authenticator, sample_message):
        """Test that unsigned messages are rejected"""
        valid, error = authenticator.verify_message(sample_message)
        
        assert valid is False
        assert "Missing required field: signature" in error
    
    def test_verify_tampered_payload(self, authenticator, sample_message):
        """Test that tampering is detected"""
        signed = authenticator.sign_message(sample_message.copy())
        
        # Tamper with payload
        signed['payload']['data'] = "TAMPERED"
        
        valid, error = authenticator.verify_message(signed)
        
        assert valid is False
        assert "Invalid signature" in error
    
    def test_verify_tampered_sender(self, authenticator, sample_message):
        """Test that sender modification is detected"""
        signed = authenticator.sign_message(sample_message.copy())
        
        # Change sender
        signed['sender_id'] = "evil_controller"
        
        valid, error = authenticator.verify_message(signed)
        
        assert valid is False
        assert "Invalid signature" in error
    
    def test_replay_attack_prevention(self, authenticator, sample_message):
        """Test that replay attacks are prevented"""
        signed = authenticator.sign_message(sample_message.copy())
        
        # First verification succeeds
        valid1, error1 = authenticator.verify_message(signed.copy())
        assert valid1 is True
        
        # Second verification with same nonce fails
        valid2, error2 = authenticator.verify_message(signed.copy())
        assert valid2 is False
        assert "Replay attack detected" in error2
    
    def test_timestamp_too_old(self, authenticator, sample_message):
        """Test that old messages are rejected"""
        signed = authenticator.sign_message(sample_message.copy())
        
        # Set timestamp to 10 minutes ago
        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        signed['signed_at'] = old_time.isoformat()
        
        # Re-sign with old timestamp (for testing purposes)
        nonce = signed['nonce']
        message_copy = signed.copy()
        del message_copy['signature']
        del message_copy['signature_algorithm']
        
        canonical = authenticator._canonicalize_message(message_copy)
        signature = authenticator._compute_hmac(canonical)
        signed['signature'] = signature
        
        valid, error = authenticator.verify_message(signed)
        
        assert valid is False
        assert "too old or future-dated" in error
    
    def test_timestamp_future_dated(self, authenticator, sample_message):
        """Test that future-dated messages are rejected"""
        signed = authenticator.sign_message(sample_message.copy())
        
        # Set timestamp to 10 minutes in future
        future_time = datetime.now(timezone.utc) + timedelta(minutes=10)
        signed['signed_at'] = future_time.isoformat()
        
        # Re-sign with future timestamp
        message_copy = signed.copy()
        del message_copy['signature']
        del message_copy['signature_algorithm']
        
        canonical = authenticator._canonicalize_message(message_copy)
        signature = authenticator._compute_hmac(canonical)
        signed['signature'] = signature
        
        valid, error = authenticator.verify_message(signed)
        
        assert valid is False
        assert "too old or future-dated" in error
    
    def test_sender_validation(self, authenticator, sample_message):
        """Test optional sender validation"""
        signed = authenticator.sign_message(sample_message.copy())
        
        # Verify with correct sender
        valid1, error1 = authenticator.verify_message(
            signed.copy(),
            expected_sender="test_controller_1"
        )
        assert valid1 is True
        
        # Verify with wrong sender
        valid2, error2 = authenticator.verify_message(
            signed.copy(),
            expected_sender="wrong_controller"
        )
        assert valid2 is False
        assert "Sender mismatch" in error2
    
    def test_different_keys_fail(self, sample_message):
        """Test that different keys produce different signatures"""
        key1 = secrets.token_bytes(32)
        key2 = secrets.token_bytes(32)
        
        auth1 = MessageAuthenticator(key1, "controller_1")
        auth2 = MessageAuthenticator(key2, "controller_2")
        
        # Sign with key1
        signed = auth1.sign_message(sample_message.copy())
        
        # Verify with key2 fails
        valid, error = auth2.verify_message(signed)
        
        assert valid is False
        assert "Invalid signature" in error
    
    def test_key_rotation(self, authenticator, sample_message):
        """Test key rotation"""
        # Sign with original key
        signed1 = authenticator.sign_message(sample_message.copy())
        valid1, _ = authenticator.verify_message(signed1.copy())
        assert valid1 is True
        
        # Rotate key
        new_key = secrets.token_bytes(32)
        authenticator.rotate_key(new_key)
        
        # Old signature no longer verifies
        valid2, error2 = authenticator.verify_message(signed1.copy())
        assert valid2 is False
        
        # New signatures work
        signed2 = authenticator.sign_message(sample_message.copy())
        valid3, _ = authenticator.verify_message(signed2.copy())
        assert valid3 is True


class TestKeyManager:
    """Test key management"""
    
    def test_initialization(self):
        """Test key manager initialization"""
        km = KeyManager()
        assert len(km.keys) == 0
    
    def test_generate_key(self):
        """Test key generation"""
        km = KeyManager()
        key = km.generate_key("test_key")
        
        assert len(key) == 32
        assert km.get_key("test_key") == key
    
    def test_set_get_key(self):
        """Test manual key storage"""
        km = KeyManager()
        key = secrets.token_bytes(32)
        
        km.set_key("my_key", key)
        retrieved = km.get_key("my_key")
        
        assert retrieved == key
    
    def test_set_short_key_fails(self):
        """Test that short keys are rejected"""
        km = KeyManager()
        
        with pytest.raises(ValueError, match="at least 32 bytes"):
            km.set_key("short_key", b"short")
    
    def test_delete_key(self):
        """Test key deletion"""
        km = KeyManager()
        km.generate_key("test_key")
        
        assert km.get_key("test_key") is not None
        
        km.delete_key("test_key")
        
        assert km.get_key("test_key") is None
    
    def test_list_keys(self):
        """Test listing all keys"""
        km = KeyManager()
        km.generate_key("key1")
        km.generate_key("key2")
        km.generate_key("key3")
        
        keys = km.list_keys()
        
        assert len(keys) == 3
        assert "key1" in keys
        assert "key2" in keys
        assert "key3" in keys
    
    def test_derive_key_id(self):
        """Test deterministic key ID derivation"""
        # Should be same regardless of order
        key_id_1 = KeyManager.derive_key_id("controller_a", "controller_b")
        key_id_2 = KeyManager.derive_key_id("controller_b", "controller_a")
        
        assert key_id_1 == key_id_2
        assert "controller_a" in key_id_1
        assert "controller_b" in key_id_1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
