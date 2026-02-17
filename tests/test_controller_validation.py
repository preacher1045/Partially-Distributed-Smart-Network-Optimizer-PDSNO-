"""
Tests for Controller Validation (Phase 4)

Tests the message bus, validation flow, and rejection paths.
"""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile

from pdsno.controllers.global_controller import GlobalController
from pdsno.controllers.regional_controller import RegionalController
from pdsno.controllers.context_manager import ContextManager
from pdsno.datastore import NIBStore
from pdsno.communication.message_bus import MessageBus
from pdsno.communication.message_format import MessageEnvelope, MessageType


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def message_bus():
    """Create message bus instance"""
    return MessageBus()


@pytest.fixture
def nib_store(temp_dir):
    """Create NIB store instance"""
    return NIBStore(str(temp_dir / "test.db"))


@pytest.fixture
def gc(temp_dir, nib_store):
    """Create Global Controller"""
    context_mgr = ContextManager(str(temp_dir / "gc_context.yaml"))
    return GlobalController(
        controller_id="global_cntl_1",
        context_manager=context_mgr,
        nib_store=nib_store
    )


@pytest.fixture
def rc(temp_dir, nib_store, message_bus):
    """Create Regional Controller"""
    context_mgr = ContextManager(str(temp_dir / "rc_context.yaml"))
    controller = RegionalController(
        temp_id="temp-rc-test-001",
        region="zone-A",
        context_manager=context_mgr,
        nib_store=nib_store,
        message_bus=message_bus
    )
    return controller


class TestMessageBus:
    """Test the in-process message bus"""
    
    def test_register_controller(self, message_bus):
        """Test controller registration"""
        def handler(env):
            return None
        
        handlers = {MessageType.HEARTBEAT: handler}
        message_bus.register_controller("test_ctrl_1", handlers)
        
        assert message_bus.is_registered("test_ctrl_1")
        assert "test_ctrl_1" in message_bus.get_registered_controllers()
    
    def test_send_message(self, message_bus):
        """Test message sending"""
        received_envelope = None
        
        def handler(env):
            nonlocal received_envelope
            received_envelope = env
            return MessageEnvelope(
                sender_id="receiver",
                recipient_id="sender",
                message_type=MessageType.HEARTBEAT,
                payload={"status": "ok"}
            )
        
        message_bus.register_controller(
            "receiver",
            {MessageType.HEARTBEAT: handler}
        )
        
        response = message_bus.send(
            sender_id="sender",
            recipient_id="receiver",
            message_type=MessageType.HEARTBEAT,
            payload={"ping": True}
        )
        
        assert received_envelope is not None
        assert received_envelope.sender_id == "sender"
        assert received_envelope.payload["ping"] is True
        assert response.payload["status"] == "ok"
    
    def test_unregistered_recipient(self, message_bus):
        """Test sending to unregistered controller raises error"""
        with pytest.raises(ValueError, match="not registered"):
            message_bus.send(
                sender_id="sender",
                recipient_id="nonexistent",
                message_type=MessageType.HEARTBEAT,
                payload={}
            )
    
    def test_missing_handler(self, message_bus):
        """Test sending message type with no handler raises error"""
        message_bus.register_controller("receiver", {})
        
        with pytest.raises(ValueError, match="no handler"):
            message_bus.send(
                sender_id="sender",
                recipient_id="receiver",
                message_type=MessageType.HEARTBEAT,
                payload={}
            )


class TestValidationFlow:
    """Test the complete validation flow"""
    
    def test_successful_validation(self, gc, rc, message_bus, nib_store):
        """Test successful end-to-end validation"""
        # Register GC
        gc_handlers = {
            MessageType.VALIDATION_REQUEST: gc.handle_validation_request,
            MessageType.CHALLENGE_RESPONSE: gc.handle_challenge_response
        }
        message_bus.register_controller("global_cntl_1", gc_handlers)
        
        # Register RC
        rc_handlers = {}
        message_bus.register_controller(rc.temp_id, rc_handlers)
        
        # Request validation
        rc.request_validation("global_cntl_1")
        
        # Verify RC is validated
        assert rc.validated is True
        assert rc.assigned_id is not None
        assert rc.assigned_id.startswith("regional_cntl_zone-A_")
        assert rc.certificate is not None
        assert rc.delegation_credential is not None
    
    def test_stale_timestamp_rejection(self, gc, nib_store):
        """Test rejection of requests with stale timestamps"""
        old_timestamp = datetime.now(timezone.utc) - timedelta(minutes=10)
        
        envelope = MessageEnvelope(
            sender_id="temp-test",
            recipient_id="global_cntl_1",
            message_type=MessageType.VALIDATION_REQUEST,
            timestamp=old_timestamp,
            payload={
                "temp_id": "temp-test",
                "controller_type": "regional",
                "region": "zone-A",
                "public_key": "test-key",
                "bootstrap_token": "test-token",
                "metadata": {}
            }
        )
        
        response = gc.handle_validation_request(envelope)
        
        assert response.payload["status"] == "REJECTED"
        assert response.payload["reason"] == "STALE_TIMESTAMP"
    
    def test_invalid_bootstrap_token(self, gc):
        """Test rejection of invalid bootstrap token"""
        envelope = MessageEnvelope(
            sender_id="temp-test",
            recipient_id="global_cntl_1",
            message_type=MessageType.VALIDATION_REQUEST,
            payload={
                "temp_id": "temp-test",
                "controller_type": "regional",
                "region": "zone-A",
                "public_key": "test-key",
                "bootstrap_token": "invalid-token-here",
                "metadata": {}
            }
        )
        
        response = gc.handle_validation_request(envelope)
        
        assert response.payload["status"] == "REJECTED"
        assert response.payload["reason"] == "INVALID_BOOTSTRAP_TOKEN"


class TestGlobalController:
    """Test Global Controller specific functionality"""
    
    def test_controller_sequence_increments(self, gc, nib_store):
        """Test that controller IDs increment properly"""
        initial_seq = gc.controller_sequence["regional"]
        
        # Create mock request
        request = {
            "controller_type": "regional",
            "region": "zone-A",
            "public_key": "test-key"
        }
        
        result = gc.assign_identity(request)
        
        assert result["error"] is False
        assert gc.controller_sequence["regional"] == initial_seq + 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
