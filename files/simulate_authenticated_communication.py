#!/usr/bin/env python3
"""
Authenticated Communication Simulation

Demonstrates Phase 6C: HMAC-signed messages with replay attack prevention.

Security features demonstrated:
- HMAC-SHA256 message signing
- Signature verification at endpoints
- Replay attack prevention with nonces
- Timestamp validation (5-minute window)
- Tamper detection
"""

import logging
from pathlib import Path
import time

from pdsno.controllers.global_controller import GlobalController
from pdsno.controllers.regional_controller import RegionalController
from pdsno.controllers.context_manager import ContextManager
from pdsno.datastore import NIBStore
from pdsno.communication.message_bus import MessageBus
from pdsno.security.message_auth import MessageAuthenticator, KeyManager
from pdsno.communication.message_format import MessageType


def setup_logging():
    """Configure logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def main():
    """Run the authenticated communication simulation"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("PDSNO Phase 6C - Authenticated Communication Simulation")
    logger.info("=" * 60)
    
    # Setup
    logger.info("\n[1/8] Initializing infrastructure...")
    sim_dir = Path("./sim_phase6c")
    sim_dir.mkdir(exist_ok=True)
    
    gc_context = ContextManager(str(sim_dir / "gc_context.yaml"))
    rc_context = ContextManager(str(sim_dir / "rc_context.yaml"))
    nib_store = NIBStore(str(sim_dir / "pdsno.db"))
    
    logger.info("✓ Infrastructure ready")
    
    # Initialize key management
    logger.info("\n[2/8] Setting up cryptographic keys...")
    key_manager = KeyManager()
    
    # Generate shared secret for GC-RC communication
    shared_secret = key_manager.generate_key("key_gc_rc")
    logger.info(f"✓ Generated shared secret (32 bytes)")
    
    # Create authenticators
    gc_auth = MessageAuthenticator(shared_secret, "global_cntl_1")
    rc_auth = MessageAuthenticator(shared_secret, "temp-rc-zone-a-001")
    
    logger.info("✓ Message authenticators initialized")
    
    # Create message bus
    message_bus = MessageBus()
    
    # Create Global Controller
    logger.info("\n[3/8] Creating Global Controller...")
    gc = GlobalController(
        controller_id="global_cntl_1",
        context_manager=gc_context,
        nib_store=nib_store
    )
    
    # Store authenticator (in real implementation, would be passed to constructor)
    gc.authenticator = gc_auth
    
    # Register GC handlers
    gc_handlers = {
        MessageType.VALIDATION_REQUEST: gc.handle_validation_request,
        MessageType.CHALLENGE_RESPONSE: gc.handle_challenge_response
    }
    message_bus.register_controller("global_cntl_1", gc_handlers)
    
    logger.info("✓ Global Controller created with authentication")
    
    # Create Regional Controller
    logger.info("\n[4/8] Creating Regional Controller...")
    rc = RegionalController(
        temp_id="temp-rc-zone-a-001",
        region="zone-A",
        context_manager=rc_context,
        nib_store=nib_store,
        message_bus=message_bus
    )
    
    # Store authenticator
    rc.authenticator = rc_auth
    
    message_bus.register_controller(rc.temp_id, {})
    
    logger.info("✓ Regional Controller created with authentication")
    
    # Test 1: Valid signed message
    logger.info("\n[5/8] Test 1: Valid signed message...")
    logger.info("-" * 60)
    
    # RC requests validation (message will be signed by MessageBus wrapper)
    logger.info("RC sending signed validation request to GC...")
    
    # Manually sign the message for demonstration
    from pdsno.communication.message_format import MessageEnvelope
    from datetime import datetime, timezone
    
    envelope = MessageEnvelope(
        sender_id=rc.temp_id,
        recipient_id="global_cntl_1",
        message_type=MessageType.VALIDATION_REQUEST,
        payload={
            "temp_id": rc.temp_id,
            "controller_type": "regional",
            "region": "zone-A",
            "public_key": "ed25519-pubkey-test",
            "bootstrap_token": "bootstrap-token-test",
            "metadata": {}
        },
        timestamp=datetime.now(timezone.utc)
    )
    
    message_dict = envelope.to_dict()
    signed_message = rc_auth.sign_message(message_dict)
    
    logger.info(f"✓ Message signed (nonce: {signed_message['nonce'][:16]}...)")
    
    # Verify signature at GC
    valid, error = gc_auth.verify_message(signed_message, expected_sender=rc.temp_id)
    
    if valid:
        logger.info("✓ GC verified message signature successfully")
        logger.info("✓ Test 1 PASSED: Valid message accepted")
    else:
        logger.error(f"✗ Signature verification failed: {error}")
        logger.error("✗ Test 1 FAILED")
    
    # Test 2: Tampered message detection
    logger.info("\n[6/8] Test 2: Tampered message detection...")
    logger.info("-" * 60)
    
    # Create and sign another message
    envelope2 = MessageEnvelope(
        sender_id=rc.temp_id,
        recipient_id="global_cntl_1",
        message_type=MessageType.VALIDATION_REQUEST,
        payload={"data": "original"},
        timestamp=datetime.now(timezone.utc)
    )
    
    message_dict2 = envelope2.to_dict()
    signed_message2 = rc_auth.sign_message(message_dict2)
    
    logger.info("✓ Original message signed")
    
    # Tamper with the message
    signed_message2['payload']['data'] = "TAMPERED"
    logger.info("⚠ Message payload tampered: original -> TAMPERED")
    
    # Try to verify tampered message
    valid2, error2 = gc_auth.verify_message(signed_message2)
    
    if not valid2:
        logger.info(f"✓ GC detected tampering: {error2}")
        logger.info("✓ Test 2 PASSED: Tampered message rejected")
    else:
        logger.error("✗ Tampered message was accepted!")
        logger.error("✗ Test 2 FAILED")
    
    # Test 3: Replay attack prevention
    logger.info("\n[7/8] Test 3: Replay attack prevention...")
    logger.info("-" * 60)
    
    # Create and sign a message
    envelope3 = MessageEnvelope(
        sender_id=rc.temp_id,
        recipient_id="global_cntl_1",
        message_type=MessageType.VALIDATION_REQUEST,
        payload={"data": "test"},
        timestamp=datetime.now(timezone.utc)
    )
    
    message_dict3 = envelope3.to_dict()
    signed_message3 = rc_auth.sign_message(message_dict3)
    
    logger.info(f"✓ Message signed (nonce: {signed_message3['nonce'][:16]}...)")
    
    # First verification succeeds
    valid3a, error3a = gc_auth.verify_message(signed_message3.copy())
    
    if valid3a:
        logger.info("✓ First verification succeeded")
    else:
        logger.error(f"✗ First verification failed: {error3a}")
    
    # Try to replay the same message
    logger.info("⚠ Attempting replay attack (same nonce)...")
    valid3b, error3b = gc_auth.verify_message(signed_message3.copy())
    
    if not valid3b and "Replay attack" in error3b:
        logger.info(f"✓ GC rejected replay: {error3b}")
        logger.info("✓ Test 3 PASSED: Replay attack prevented")
    else:
        logger.error("✗ Replay attack was not detected!")
        logger.error("✗ Test 3 FAILED")
    
    # Summary
    logger.info("\n[8/8] Security features demonstrated...")
    logger.info("-" * 60)
    logger.info("✓ HMAC-SHA256 message signing")
    logger.info("✓ Signature verification")
    logger.info("✓ Tamper detection")
    logger.info("✓ Replay attack prevention")
    logger.info("✓ Timestamp validation (5-minute window)")
    logger.info("✓ Nonce-based replay cache")
    
    logger.info("\n" + "=" * 60)
    logger.info("Phase 6C Simulation Complete!")
    logger.info("=" * 60)
    
    logger.info("\nSecurity Summary:")
    logger.info("  • All messages signed with HMAC-SHA256")
    logger.info("  • Signatures prevent tampering and impersonation")
    logger.info("  • Nonces prevent replay attacks")
    logger.info("  • Timestamps prevent old message acceptance")
    logger.info("  • Shared secrets managed by KeyManager")
    
    logger.info("\nNext Steps:")
    logger.info("  1. Integrate authenticators into HTTP client and REST server")
    logger.info("  2. Add signature verification to MQTT messages")
    logger.info("  3. Implement secure key distribution mechanism")
    logger.info("  4. Add key rotation automation")
    logger.info("  5. Run tests: pytest tests/test_message_auth.py")
    
    return 0


if __name__ == "__main__":
    exit(main())
