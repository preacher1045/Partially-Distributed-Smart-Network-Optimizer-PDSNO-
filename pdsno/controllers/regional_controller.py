"""
Regional Controller

Governs a geographic region. Validates Local Controllers (delegated authority)
and approves MEDIUM/LOW config changes.
"""

import hmac
import hashlib
from typing import Optional, Callable
import uuid
from datetime import datetime, timezone

from pdsno.controllers.base_controller import BaseController
from pdsno.communication.message_format import MessageEnvelope, MessageType
from pdsno.datastore import NIBStore
from pdsno.controllers.context_manager import ContextManager
from pdsno.logging.logger import get_logger
from pdsno.communication.rest_server import ControllerRESTServer
from pdsno.communication.http_client import ControllerHTTPClient
from pdsno.communication.mqtt_client import ControllerMQTTClient


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
        message_bus=None,  # Injected after creation (backwards compatibility)
        http_client: Optional[ControllerHTTPClient] = None,
        enable_rest: bool = False,
        rest_port: int = 8002,
        mqtt_broker: Optional[str] = None,
        mqtt_port: int = 1883,
        key_manager=None  # Key distribution
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
        self.http_client = http_client  # HTTP client for GC communication
        self.validated = False
        self.assigned_id = None
        self.certificate = None
        self.delegation_credential = None
        
        # Store for challenge-response flow
        self.pending_validation = None
        
        # REST server setup
        self.rest_server = None
        if enable_rest:
            self.rest_server = ControllerRESTServer(
                controller_id=self.temp_id,
                port=rest_port,
                title="PDSNO Regional Controller API"
            )
            
            # Register handlers
            self.rest_server.register_handler(
                MessageType.DISCOVERY_REPORT,
                self.handle_discovery_report
            )
            
            self.logger.info(f"REST server configured on port {rest_port}")
        
        # MQTT client setup
        self.mqtt_client = None
        if mqtt_broker:
            self.mqtt_client = ControllerMQTTClient(
                controller_id=self.temp_id,
                broker_host=mqtt_broker,
                broker_port=mqtt_port
            )
            self.logger.info(f"MQTT client configured for broker {mqtt_broker}:{mqtt_port}")
        
        # Phase 6D: Key distribution (optional)
        self.key_manager = key_manager
        self.key_protocol = None
        self.authenticator = None
        if key_manager:
            from pdsno.security.key_distribution import KeyDistributionProtocol
            self.key_protocol = KeyDistributionProtocol(self.temp_id, key_manager)
            self.logger.info("Key distribution protocol initialized")
        
        self.logger.info(f"Regional Controller {temp_id} initialized for region {region}")
    
    def perform_key_exchange(
        self,
        global_controller_id: str,
        global_controller_url: str
    ) -> bool:
        """
        Perform key exchange with Global Controller (Phase 6D).
        
        This must be done BEFORE requesting validation since
        validation messages will be signed after key exchange.
        
        Args:
            global_controller_id: Global Controller's ID
            global_controller_url: URL to Global Controller's REST server
        
        Returns:
            True if key exchange successful, False otherwise
        """
        if not self.key_protocol:
            self.logger.error("Key distribution not configured")
            return False
        
        if not self.http_client:
            self.logger.error("HTTP client not configured")
            return False
        
        self.logger.info(f"Initiating key exchange with {global_controller_id}")
        
        # Step 1: Initiate key exchange
        init_payload = self.key_protocol.initiate_key_exchange(global_controller_id)
        
        # Step 2: Send KEY_EXCHANGE_INIT (unsigned, no shared secret yet)
        try:
            self.http_client.register_controller(global_controller_id, global_controller_url)
            
            response = self.http_client.send(
                sender_id=self.temp_id,
                recipient_id=global_controller_id,
                message_type=MessageType.KEY_EXCHANGE_INIT,
                payload=init_payload,
                sign=False  # IMPORTANT: Can't sign before key exchange
            )
            
            if not response:
                self.logger.error("No response to key exchange init")
                return False
            
            # Step 3: Finalize key exchange
            self.key_protocol.finalize_key_exchange(
                global_controller_id,
                response.payload
            )
            
            self.logger.info("Key exchange completed successfully")
            
            # Step 4: Create authenticator with new shared secret
            key_id = self.key_protocol.key_manager.derive_key_id(
                self.temp_id,
                global_controller_id
            )
            shared_secret = self.key_protocol.key_manager.get_key(key_id)
            
            from pdsno.security.message_auth import MessageAuthenticator
            self.authenticator = MessageAuthenticator(
                shared_secret,
                self.temp_id
            )
            
            # Update HTTP client authenticator for future signed messages
            if self.http_client:
                self.http_client.authenticator = self.authenticator
            
            self.logger.info("Message authenticator configured")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Key exchange failed: {e}", exc_info=True)
            return False
    
    def request_validation(self, global_controller_id: str, global_controller_url: Optional[str] = None):
        """Request validation from the Global Controller via HTTP or message bus."""
        if self.validated:
            self.logger.warning(f"Controller {self.controller_id} already validated")
            return
        
        # Determine communication method
        use_http = self.http_client is not None and global_controller_url is not None
        
        if not use_http and not self.message_bus:
            raise RuntimeError("Neither HTTP client nor message bus configured")
        
        # Generate bootstrap token and keys
        bootstrap_token = self._generate_bootstrap_token()
        public_key = "ed25519-pubkey-placeholder"
        self.private_key = "ed25519-privkey-placeholder"
        
        # Create validation request payload
        payload = {
            "temp_id": self.temp_id,
            "controller_type": "regional",
            "region": self.region,
            "public_key": public_key,
            "bootstrap_token": bootstrap_token,
            "metadata": {
                "hostname": "rc-" + self.region,
                "ip_address": "10.0.0.1",
                "software_version": "0.1.0",
                "capabilities": ["discovery", "approval", "policy_enforcement"]
            }
        }
        
        self.logger.info(f"Requesting validation from {global_controller_id}")
        
        if use_http:
            # Register GC in HTTP client if URL provided
            self.http_client.register_controller(global_controller_id, global_controller_url)
            
            # Send via HTTP
            response = self.http_client.send(
                sender_id=self.temp_id,
                recipient_id=global_controller_id,
                message_type=MessageType.VALIDATION_REQUEST,
                payload=payload
            )
        else:
            # Use message bus (backwards compatible)
            response = self.message_bus.send(
                sender_id=self.temp_id,
                recipient_id=global_controller_id,
                message_type=MessageType.VALIDATION_REQUEST,
                payload=payload
            )
        
        # Handle response (same logic for both HTTP and message bus)
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
        
        # Send via HTTP or message bus
        if self.http_client:
            result = self.http_client.send(
                sender_id=self.temp_id,
                recipient_id=global_controller_id,
                message_type=MessageType.CHALLENGE_RESPONSE,
                payload=response_payload,
                correlation_id=envelope.message_id
            )
        else:
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
    
    def handle_discovery_report(self, envelope: MessageEnvelope) -> Optional[MessageEnvelope]:
        """Handle discovery reports from Local Controllers."""
        payload = envelope.payload
        lc_id = payload.get("lc_id")
        subnet = payload.get("subnet")
        new_devices = payload.get("new_devices", [])
        updated_devices = payload.get("updated_devices", [])
        inactive_devices = payload.get("inactive_devices", [])
        
        # Validate report FIRST
        if not lc_id or not subnet:
            self.logger.warning(f"Invalid discovery report from {envelope.sender_id}: missing lc_id or subnet")
            return None
        
        # NOW log with actual counts
        self.logger.info(
            f"Discovery report from {lc_id} (subnet {subnet}): "
            f"{len(new_devices)} new, {len(updated_devices)} updated, "
            f"{len(inactive_devices)} inactive"
        )
        
        # Combine all discovered devices for collision checking
        all_devices = new_devices + updated_devices
        
        # Check for MAC address collisions across LCs
        collisions = self._check_mac_collisions(all_devices, lc_id)
        
        if collisions:
            self.logger.warning(
                f"MAC collision detected: {len(collisions)} conflicts",
                extra={"collisions": collisions}
            )
        
        # Acknowledge receipt
        return MessageEnvelope(
            sender_id=self.controller_id,
            recipient_id=envelope.sender_id,
            message_type=MessageType.DISCOVERY_REPORT_ACK,
            payload={
                "status": "received",
                "devices_processed": len(all_devices),
                "collisions_detected": len(collisions) if collisions else 0
            }
        )
    
    def _check_mac_collisions(self, devices: list, reporting_lc_id: str) -> dict:
        """
        Check if any MAC addresses in the report conflict with devices
        managed by other LCs.
        
        Returns:
            Dict of {mac_address: existing_lc_id} for collisions
        """
        collisions = {}
        
        for device in devices:
            mac = device.get("mac")
            if not mac:
                continue
            
            # Query NIB for existing device with this MAC
            existing_device = self.nib_store.get_device_by_mac(mac)
            
            if existing_device and existing_device.managed_by_lc != reporting_lc_id:
                collisions[mac] = existing_device.managed_by_lc
                self.logger.warning(
                    f"MAC collision: {mac} reported by {reporting_lc_id} "
                    f"but already managed by {existing_device.managed_by_lc}"
                )
        
        return collisions

    def start_rest_server_background(self):
        """Start the REST server in a background thread"""
        if not self.rest_server:
            raise RuntimeError("REST server not configured")
        
        self.rest_server.start_background()
        self.logger.info(f"REST API available at {self.rest_server.get_base_url()}")
    
    def update_rest_server_id(self):
        """Update REST server's controller ID after validation"""
        if self.rest_server and self.validated:
            self.rest_server.controller_id = self.assigned_id
            self.logger.info(f"REST server ID updated to {self.assigned_id}")
    
    def get_rest_url(self) -> str:
        """Get the base URL for this controller's REST API"""
        if not self.rest_server:
            raise RuntimeError("REST server not configured")
        
        return self.rest_server.get_base_url()
    
    def connect_mqtt(self) -> bool:
        """Connect to MQTT broker"""
        if not self.mqtt_client:
            raise RuntimeError("MQTT client not configured")
        
        return self.mqtt_client.connect()
    
    def disconnect_mqtt(self):
        """Disconnect from MQTT broker"""
        if self.mqtt_client:
            self.mqtt_client.disconnect()
    
    def subscribe_to_discovery_reports(self):
        """
        Subscribe to discovery reports from all LCs in this region.
        """
        if not self.mqtt_client:
            raise RuntimeError("MQTT client not configured")
        
        # Subscribe to all discovery reports in this region
        # Topic pattern: pdsno/discovery/{region}/+
        # + wildcard matches any LC ID
        topic = f"pdsno/discovery/{self.region}/+"
        
        self.mqtt_client.subscribe(
            topic,
            self._handle_mqtt_discovery_report,
            qos=1
        )
        
        self.logger.info(f"Subscribed to discovery reports on {topic}")
    
    def _handle_mqtt_discovery_report(self, envelope: MessageEnvelope):
        """
        Handle discovery report received via MQTT.
        
        This is called by MQTT client when a message arrives.
        """
        self.logger.info(
            f"MQTT discovery report from {envelope.sender_id}"
        )
        
        # Reuse existing discovery report handler
        self.handle_discovery_report(envelope)
    
    def publish_policy_update(self, policy: dict):
        """
        Publish policy update to all LCs in this region.
        
        Args:
            policy: Policy dictionary to publish
        """
        if not self.mqtt_client:
            raise RuntimeError("MQTT client not configured")
        
        # Publish to region-specific policy topic
        topic = f"pdsno/policy/{self.region}"
        
        success = self.mqtt_client.publish(
            topic=topic,
            message_type=MessageType.POLICY_UPDATE,
            payload=policy,
            qos=1,
            retain=True
        )
        
        if success:
            self.logger.info(f"Policy update published to {topic}")
        else:
            self.logger.error("Failed to publish policy update")
        
        return success
    
    def subscribe_to_global_policies(self, handler: Optional[Callable] = None):
        """
        Subscribe to global policy updates from GC.
        
        Args:
            handler: Optional custom handler. If not provided, uses default.
        """
        if not self.mqtt_client:
            raise RuntimeError("MQTT client not configured")
        
        topic = "pdsno/policy/global"
        
        handler_func = handler or self._handle_global_policy_update
        
        self.mqtt_client.subscribe(topic, handler_func, qos=1)
        self.logger.info(f"Subscribed to global policy updates on {topic}")
    
    def _handle_global_policy_update(self, envelope: MessageEnvelope):
        """Handle global policy update from GC"""
        self.logger.info("Global policy update received from GC")
        
        policy = envelope.payload
        
        # Store policy in context
        self.update_context({'global_policy': policy})
        
        # Optionally re-publish to regional topic for LCs
        if self.mqtt_client:
            self.publish_policy_update(policy)
    
    def update_mqtt_client_id(self):
        """Update MQTT client ID after validation (from temp_id to assigned_id)"""
        if self.mqtt_client and self.validated:
            # Disconnect with old ID
            self.mqtt_client.disconnect()
            
            # Update client ID
            self.mqtt_client.controller_id = self.assigned_id
            
            # Reconnect with new ID
            self.mqtt_client.connect()
            
            self.logger.info(f"MQTT client ID updated to {self.assigned_id}")
