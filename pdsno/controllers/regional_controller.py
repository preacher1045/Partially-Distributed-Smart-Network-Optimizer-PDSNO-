"""
Regional Controller

Governs a geographic region. Validates Local Controllers (delegated authority)
and approves MEDIUM/LOW config changes.
"""

import hmac
import hashlib
import uuid
from datetime import datetime, timezone

from pdsno.controllers.base_controller import BaseController
from pdsno.communication.message_format import MessageEnvelope, MessageType
from pdsno.datastore import NIBStore
from pdsno.controllers.context_manager import ContextManager
from pdsno.logging.logger import get_logger


class RegionalController(BaseController):
    """
    Regional Controller - Zone-level governance.
    
    Responsibilities:
    - Request validation from Global Controller
    - Validate Local Controllers (delegated)
    - Approve MEDIUM/LOW config changes
    - Aggregate discovery reports from LCs
    """
    
    def __init__(
        self,
        temp_id: str,  # Before validation: temporary ID
        region: str,
        context_manager: ContextManager,
        nib_store: NIBStore,
        message_bus=None  # Injected after creation
    ):
        # Start with temp_id, will be updated after validation
        super().__init__(
            controller_id=temp_id,
            role="regional",
            context_manager=context_manager,
            region=region,
            nib_store=nib_store
        )
        
        self.temp_id = temp_id
        self.region = region
        self.message_bus = message_bus
        self.validated = False
        self.assigned_id = None
        self.certificate = None
        self.delegation_credential = None
        
        # Store for challenge-response flow
        self.pending_validation = None
        
        self.logger.info(f"Regional Controller {temp_id} initialized for region {region}")
    
    def request_validation(self, global_controller_id: str):
        """
        Request validation from the Global Controller.
        
        Starts the validation flow by sending a VALIDATION_REQUEST.
        """
        if self.validated:
            self.logger.warning(f"Controller {self.controller_id} already validated")
            return
        
        if not self.message_bus:
            raise RuntimeError("Message bus not set - cannot request validation")
        
        # Generate bootstrap token (in production, this would be provisioned securely)
        bootstrap_token = self._generate_bootstrap_token()
        
        # Generate key pair (PoC: placeholder, Phase 6 will use Ed25519)
        public_key = "ed25519-pubkey-placeholder"
        self.private_key = "ed25519-privkey-placeholder"
        
        # Create validation request
        payload = {
            "temp_id": self.temp_id,
            "controller_type": "regional",
            "region": self.region,
            "public_key": public_key,
            "bootstrap_token": bootstrap_token,
            "metadata": {
                "hostname": "rc-" + self.region,
                "ip_address": "10.0.0.1",  # Placeholder
                "software_version": "0.1.0",
                "capabilities": ["discovery", "approval", "policy_enforcement"]
            }
        }
        
        self.logger.info(f"Requesting validation from {global_controller_id}")
        
        # Send validation request via message bus
        response = self.message_bus.send(
            sender_id=self.temp_id,
            recipient_id=global_controller_id,
            message_type=MessageType.VALIDATION_REQUEST,
            payload=payload
        )
        
        # Response should be a CHALLENGE
        if response.message_type == MessageType.CHALLENGE:
            self._handle_challenge(response, global_controller_id)
        elif response.message_type == MessageType.VALIDATION_RESULT:
            self._handle_validation_result(response)
        else:
            self.logger.error(f"Unexpected response type: {response.message_type}")
    
    def _handle_challenge(self, envelope: MessageEnvelope, global_controller_id: str):
        """Handle the challenge from the Global Controller"""
        payload = envelope.payload
        challenge_id = payload["challenge_id"]
        nonce_hex = payload["nonce"]
        
        self.logger.info(f"Received challenge {challenge_id}")
        
        # Sign the nonce (PoC: simplified HMAC, Phase 6 will use Ed25519)
        nonce = bytes.fromhex(nonce_hex)
        signed_nonce = hmac.new(
            nonce,
            b"signed_by_controller",  # Placeholder
            hashlib.sha256
        ).hexdigest()
        
        # Send challenge response
        response_payload = {
            "challenge_id": challenge_id,
            "temp_id": self.temp_id,
            "signed_nonce": signed_nonce
        }
        
        self.logger.info(f"Sending challenge response for {challenge_id}")
        
        result = self.message_bus.send(
            sender_id=self.temp_id,
            recipient_id=global_controller_id,
            message_type=MessageType.CHALLENGE_RESPONSE,
            payload=response_payload,
            correlation_id=envelope.message_id
        )
        
        # Result should be VALIDATION_RESULT
        if result.message_type == MessageType.VALIDATION_RESULT:
            self._handle_validation_result(result)
        else:
            self.logger.error(f"Unexpected response type: {result.message_type}")
    
    def _handle_validation_result(self, envelope: MessageEnvelope):
        """Handle the final validation result"""
        payload = envelope.payload
        status = payload["status"]
        
        if status == "APPROVED":
            self.assigned_id = payload["assigned_id"]
            self.certificate = payload["certificate"]
            self.delegation_credential = payload.get("delegation_credential")
            self.validated = True
            
            # Update controller_id to assigned_id
            self.controller_id = self.assigned_id
            
            self.logger.info(
                f"✓ Validation successful! Assigned ID: {self.assigned_id}"
            )
            
            # Store certificate in context
            self.update_context({
                "controller_id": self.assigned_id,
                "validated": True,
                "certificate": self.certificate,
                "delegation_credential": self.delegation_credential
            })
            
        elif status == "REJECTED":
            reason = payload.get("reason", "UNKNOWN")
            self.logger.error(f"✗ Validation rejected: {reason}")
            
        else:  # ERROR
            reason = payload.get("reason", "UNKNOWN")
            self.logger.error(f"✗ Validation error: {reason}")
    
    def _generate_bootstrap_token(self) -> str:
        """
        Generate bootstrap token for validation request.
        
        In production, this would be securely provisioned during deployment.
        For PoC, we generate it using the same secret the GC uses.
        """
        BOOTSTRAP_SECRET = b"pdsno-bootstrap-secret-change-in-production"
        token_input = f"{self.temp_id}|{self.region}|regional".encode()
        return hmac.new(BOOTSTRAP_SECRET, token_input, hashlib.sha256).hexdigest()
    
    # Message handlers (to be registered with message bus)
    
    def handle_validation_request(self, envelope: MessageEnvelope) -> MessageEnvelope:
        """
        Handle validation requests from Local Controllers (delegated authority).
        
        This mirrors the GC's validation logic but is scoped to the RC's region.
        Not implemented in Phase 4 - will be added in Phase 5.
        """
        self.logger.info("Received LC validation request (not implemented in Phase 4)")
        return MessageEnvelope(
            sender_id=self.controller_id,
            recipient_id=envelope.sender_id,
            message_type=MessageType.VALIDATION_RESULT,
            payload={"status": "ERROR", "reason": "NOT_IMPLEMENTED_YET"}
        )
