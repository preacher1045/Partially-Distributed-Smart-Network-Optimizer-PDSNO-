"""
Global Controller

The trust anchor for the PDSNO network. Validates Regional Controllers
and maintains global state.
"""

import hmac
import hashlib
import json
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from pdsno.controllers.base_controller import BaseController
from pdsno.communication.message_format import MessageEnvelope, MessageType
from pdsno.datastore import NIBStore
from pdsno.datastore.models import Controller, Event
from pdsno.controllers.context_manager import ContextManager
from pdsno.logging.logger import get_logger
from pdsno.communication.rest_server import ControllerRESTServer


class GlobalController(BaseController):
    """
    Global Controller - Root of trust for the PDSNO hierarchy.
    
    Responsibilities:
    - Validate Regional Controllers
    - Maintain global policy
    - Approve HIGH-sensitivity config changes
    - Detect cross-region anomalies
    """
    
    # Configuration constants
    FRESHNESS_WINDOW_MINUTES = 5
    CHALLENGE_TIMEOUT_SECONDS = 30
    BOOTSTRAP_SECRET = b"pdsno-bootstrap-secret-change-in-production"
    
    def __init__(
        self,
        controller_id: str,
        context_manager: ContextManager,
        nib_store: NIBStore,
        enable_rest: bool = False,
        rest_port: int = 8001
    ):
        super().__init__(
            controller_id=controller_id,
            role="global",
            context_manager=context_manager,
            region=None,  # Global controllers have no specific region
            nib_store=nib_store
        )
        
        # In-memory challenge store (short-lived)
        self.pending_challenges: Dict[str, Dict] = {}
        
        # Validated controllers counter (for ID assignment)
        self.controller_sequence = {"regional": 0, "local": 0}
        
        # REST server setup (optional for backwards compatibility)
        self.rest_server = None
        if enable_rest:
            self.rest_server = ControllerRESTServer(
                controller_id=self.controller_id,
                port=rest_port,
                title="PDSNO Global Controller API"
            )
            
            # Register message handlers
            self.rest_server.register_handler(
                MessageType.VALIDATION_REQUEST,
                self.handle_validation_request
            )
            self.rest_server.register_handler(
                MessageType.CHALLENGE_RESPONSE,
                self.handle_challenge_response
            )
            
            self.logger.info(f"REST server configured on port {rest_port}")
        
        self.logger.info(f"Global Controller {controller_id} initialized")
    
    def handle_validation_request(self, envelope: MessageEnvelope) -> MessageEnvelope:
        """
        Main validation handler - implements the 6-step validation flow
        from docs/architecture/verification/controller_validation_sequence.md
        """
        payload = envelope.payload
        temp_id = payload.get("temp_id")
        
        self.logger.info(f"Validation request from {temp_id}")
        
        # Step 1: Check timestamp freshness
        result = self.check_timestamp(envelope)
        if result.get("reject"):
            return self._create_rejection(envelope, result["reason"])
        
        # Step 2: Check blocklist & verify bootstrap token
        result = self.verify_bootstrap_token(payload)
        if result.get("reject"):
            return self._create_rejection(envelope, result["reason"])
        
        # Step 3: Issue challenge
        challenge_envelope = self.issue_challenge(envelope, payload)
        
        return challenge_envelope
    
    def handle_challenge_response(self, envelope: MessageEnvelope) -> MessageEnvelope:
        """
        Handle the response to a challenge.
        Completes Steps 4-6 of the validation flow.
        """
        payload = envelope.payload
        challenge_id = payload.get("challenge_id")
        temp_id = payload.get("temp_id")
        signed_nonce = payload.get("signed_nonce")
        
        self.logger.info(f"Challenge response from {temp_id}")
        
        # Step 4: Verify challenge response
        result = self.verify_challenge_response(
            challenge_id, temp_id, signed_nonce
        )
        if result.get("reject"):
            return self._create_rejection(envelope, result["reason"])
        
        # Get original request data from challenge
        original_request = result["original_request"]
        
        # Step 5: Policy and metadata verification
        result = self.policy_checks(original_request)
        if result.get("reject"):
            return self._create_rejection(envelope, result["reason"])
        
        # Step 6: Assign identity atomically
        result = self.assign_identity(original_request)
        if result.get("error"):
            return self._create_error_response(envelope, result["reason"])
        
        # Success - return validation result
        return MessageEnvelope(
            sender_id=self.controller_id,
            recipient_id=temp_id,
            message_type=MessageType.VALIDATION_RESULT,
            correlation_id=envelope.message_id,
            payload={
                "status": "APPROVED",
                "assigned_id": result["assigned_id"],
                "certificate": result["certificate"],
                "delegation_credential": result.get("delegation_credential"),
                "role": original_request["controller_type"],
                "region": original_request["region"]
            }
        )
    
    # ===== Step 1: Timestamp Freshness =====
    
    def check_timestamp(self, envelope: MessageEnvelope) -> Dict:
        """Check if request timestamp is within freshness window"""
        now = datetime.now(timezone.utc)
        message_time = envelope.timestamp
        
        age = (now - message_time).total_seconds()
        
        if age < 0:
            # Future timestamp - clock skew or replay attempt
            self.logger.warning(f"Future timestamp detected: {envelope.sender_id}")
            return {"reject": True, "reason": "FUTURE_TIMESTAMP"}
        
        if age > (self.FRESHNESS_WINDOW_MINUTES * 60):
            self.logger.warning(f"Stale timestamp detected: {envelope.sender_id} (age: {age}s)")
            return {"reject": True, "reason": "STALE_TIMESTAMP"}
        
        return {"reject": False}
    
    # ===== Step 2: Bootstrap Token Verification =====
    
    def verify_bootstrap_token(self, payload: Dict) -> Dict:
        """Verify bootstrap token using HMAC-SHA256"""
        temp_id = payload.get("temp_id")
        controller_type = payload.get("controller_type")
        region = payload.get("region")
        submitted_token = payload.get("bootstrap_token")
        
        # Check blocklist (would load from context in production)
        blocklist = []  # Placeholder
        if temp_id in blocklist:
            self.logger.warning(f"Blocklisted controller attempted validation: {temp_id}")
            return {"reject": True, "reason": "BLOCKLISTED"}
        
        # Compute expected token
        token_input = f"{temp_id}|{region}|{controller_type}".encode()
        expected_token = hmac.new(
            self.BOOTSTRAP_SECRET,
            token_input,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(submitted_token, expected_token):
            self.logger.warning(f"Invalid bootstrap token from {temp_id}")
            return {"reject": True, "reason": "INVALID_BOOTSTRAP_TOKEN"}
        
        # Token consumed (would mark in persistent store in production)
        return {"reject": False}
    
    # ===== Step 3: Issue Challenge =====
    
    def issue_challenge(self, envelope: MessageEnvelope, payload: Dict) -> MessageEnvelope:
        """Generate and issue a cryptographic challenge"""
        challenge_id = f"challenge-{uuid.uuid4().hex[:12]}"
        nonce = secrets.token_bytes(32)  # 256-bit nonce
        
        # Store challenge (short-lived, 30s expiry)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.CHALLENGE_TIMEOUT_SECONDS)
        self.pending_challenges[challenge_id] = {
            "temp_id": payload["temp_id"],
            "nonce": nonce,
            "public_key": payload["public_key"],
            "expires_at": expires_at,
            "original_request": payload  # Store for Step 6
        }
        
        self.logger.info(f"Issued challenge {challenge_id} to {payload['temp_id']}")
        
        return MessageEnvelope(
            sender_id=self.controller_id,
            recipient_id=payload["temp_id"],
            message_type=MessageType.CHALLENGE,
            correlation_id=envelope.message_id,
            payload={
                "challenge_id": challenge_id,
                "nonce": nonce.hex(),  # Send as hex string
                "expires_at": expires_at.isoformat()
            }
        )
    
    # ===== Step 4: Verify Challenge Response =====
    
    def verify_challenge_response(
        self, challenge_id: str, temp_id: str, signed_nonce: str
    ) -> Dict:
        """Verify the signed challenge response"""
        
        # Check if challenge exists
        if challenge_id not in self.pending_challenges:
            self.logger.warning(f"Unknown challenge ID: {challenge_id}")
            return {"reject": True, "reason": "UNKNOWN_CHALLENGE"}
        
        pending = self.pending_challenges[challenge_id]
        
        # Check expiry
        if datetime.now(timezone.utc) > pending["expires_at"]:
            del self.pending_challenges[challenge_id]
            self.logger.warning(f"Challenge expired: {challenge_id}")
            return {"reject": True, "reason": "CHALLENGE_EXPIRED"}
        
        # Check temp_id matches
        if temp_id != pending["temp_id"]:
            self.logger.warning(f"temp_id mismatch in challenge response")
            return {"reject": True, "reason": "TEMP_ID_MISMATCH"}
        
        # Verify signature (PoC: simplified HMAC check)
        # Phase 6 will use Ed25519 signature verification
        expected_signature = hmac.new(
            pending["nonce"],
            b"signed_by_controller",  # Placeholder
            hashlib.sha256
        ).hexdigest()
        
        # Consume challenge regardless of outcome
        original_request = pending["original_request"]
        del self.pending_challenges[challenge_id]
        
        if not hmac.compare_digest(signed_nonce, expected_signature):
            self.logger.warning(f"Invalid signature from {temp_id}")
            return {"reject": True, "reason": "INVALID_SIGNATURE"}
        
        self.logger.info(f"Challenge {challenge_id} verified successfully")
        return {"reject": False, "original_request": original_request}
    
    # ===== Step 5: Policy Checks =====
    
    def policy_checks(self, request: Dict) -> Dict:
        """Verify controller is permitted by policy"""
        controller_type = request["controller_type"]
        region = request["region"]
        
        # Check 1: Controller type permitted
        permitted_types = ["regional", "local"]  # Would load from policy
        if controller_type not in permitted_types:
            return {"reject": True, "reason": "TYPE_NOT_PERMITTED"}
        
        # Check 2: Valid region
        valid_regions = ["zone-A", "zone-B", "zone-C"]  # Would load from policy
        if region not in valid_regions:
            return {"reject": True, "reason": "INVALID_REGION"}
        
        # Check 3: Quota check (max controllers per region)
        # Would query NIB in production
        
        return {"reject": False}
    
    # ===== Step 6: Assign Identity =====
    
    def assign_identity(self, request: Dict) -> Dict:
        """Atomically assign permanent identity and write to NIB"""
        controller_type = request["controller_type"]
        region = request["region"]
        
        # Allocate controller ID
        self.controller_sequence[controller_type] += 1
        seq = self.controller_sequence[controller_type]
        assigned_id = f"{controller_type}_cntl_{region}_{seq}"
        
        # Generate certificate (PoC: JSON with HMAC signature)
        issued_at = datetime.now(timezone.utc)
        certificate = {
            "assigned_id": assigned_id,
            "role": controller_type,
            "region": region,
            "public_key": request["public_key"],
            "issued_by": self.controller_id,
            "issued_at": issued_at.isoformat(),
            "signature": "hmac-placeholder"  # Would be actual HMAC
        }
        
        # Generate delegation credential for RCs
        delegation_credential = None
        if controller_type == "regional":
            delegation_credential = {
                "scope": region,
                "permitted_actions": ["validate_local_controllers"],
                "signature": "hmac-placeholder"
            }
        
        # Write to NIB (atomically with audit event)
        try:
            # Create controller record
            controller_record = Controller(
                controller_id=assigned_id,
                role=controller_type,
                region=region,
                status="active",
                validated_by=self.controller_id,
                validated_at=issued_at,
                public_key=request["public_key"],
                certificate=json.dumps(certificate),
                capabilities=request.get("metadata", {}).get("capabilities", []),
                metadata=request.get("metadata", {}),
                version=0
            )
            
            # Write controller to NIB
            result = self.nib_store.upsert_controller(controller_record)
            if not result.success:
                self.logger.error(f"Failed to write controller to NIB: {result.error}")
                return {"error": True, "reason": "NIB_WRITE_FAILED"}
            
            # Write audit event
            event = Event(
                event_id=f"event-{uuid.uuid4().hex[:12]}",
                event_type="CONTROLLER_VALIDATED",
                controller_id=self.controller_id,
                timestamp=issued_at,
                details={
                    "assigned_id": assigned_id,
                    "role": controller_type,
                    "region": region,
                    "validated_at": issued_at.isoformat()
                }
            )
            
            event_result = self.nib_store.write_event(event)
            if not event_result.success:
                self.logger.warning(f"Failed to write audit event: {event_result.error}")
                # Don't fail the validation for audit log failure, but log it
            
            self.logger.info(
                f"✓ Assigned identity: {assigned_id} (type={controller_type}, region={region})"
            )
            
            return {
                "error": False,
                "assigned_id": assigned_id,
                "certificate": certificate,
                "delegation_credential": delegation_credential
            }
            
        except Exception as e:
            self.logger.error(f"Failed to register controller: {e}", exc_info=True)
            return {"error": True, "reason": "REGISTRATION_FAILED"}

    
    # ===== Helper Methods =====
    
    def _create_rejection(self, original_envelope: MessageEnvelope, reason: str) -> MessageEnvelope:
        """Create a validation rejection response"""
        return MessageEnvelope(
            sender_id=self.controller_id,
            recipient_id=original_envelope.sender_id,
            message_type=MessageType.VALIDATION_RESULT,
            correlation_id=original_envelope.message_id,
            payload={
                "status": "REJECTED",
                "reason": reason
            }
        )
    
    def _create_error_response(self, original_envelope: MessageEnvelope, reason: str) -> MessageEnvelope:
        """Create an error response (system failure, not rejection)"""
        return MessageEnvelope(
            sender_id=self.controller_id,
            recipient_id=original_envelope.sender_id,
            message_type=MessageType.VALIDATION_RESULT,
            correlation_id=original_envelope.message_id,
            payload={
                "status": "ERROR",
                "reason": reason
            }
        )

    def start_rest_server_background(self):
        """Start the REST server in a background thread"""
        if not self.rest_server:
            raise RuntimeError("REST server not configured. Set enable_rest=True in __init__")
        
        self.rest_server.start_background()
        self.logger.info(f"REST API available at {self.rest_server.get_base_url()}")
    
    async def start_rest_server_async(self):
        """Start the REST server (async)"""
        if not self.rest_server:
            raise RuntimeError("REST server not configured. Set enable_rest=True in __init__")
        
        await self.rest_server.start()
    
    def get_rest_url(self) -> str:
        """Get the base URL for this controller's REST API"""
        if not self.rest_server:
            raise RuntimeError("REST server not configured")
        
        return self.rest_server.get_base_url()