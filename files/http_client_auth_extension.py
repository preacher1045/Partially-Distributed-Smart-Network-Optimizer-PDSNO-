"""
HTTP Client with Message Authentication

Extension to add HMAC signature support to ControllerHTTPClient.
Add these methods to your existing pdsno/communication/http_client.py
"""

# ADD TO IMPORTS:
"""
from typing import Optional
from pdsno.security.message_auth import MessageAuthenticator
"""

# MODIFY ControllerHTTPClient.__init__():
"""
    def __init__(
        self,
        controller_registry: Optional[Dict[str, str]] = None,
        authenticator: Optional[MessageAuthenticator] = None  # NEW
    ):
        '''
        Initialize HTTP client.
        
        Args:
            controller_registry: Dict mapping controller_id -> base_url
            authenticator: Optional MessageAuthenticator for signing messages
        '''
        self.controller_registry = controller_registry or {}
        self.authenticator = authenticator  # NEW
        self.logger = logging.getLogger(__name__)
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'PDSNO-Controller-Client/1.0'
        })
"""

# MODIFY send() method to sign messages:
"""
    def send(
        self,
        sender_id: str,
        recipient_id: str,
        message_type: MessageType,
        payload: Dict,
        correlation_id: Optional[str] = None,
        timeout: int = 30,
        sign: bool = True  # NEW: Control whether to sign
    ) -> Optional[MessageEnvelope]:
        '''
        Send a message to a controller via HTTP POST.
        
        Args:
            sender_id: ID of sending controller
            recipient_id: ID of receiving controller
            message_type: Type of message
            payload: Message payload
            correlation_id: Optional correlation ID for request-response pairing
            timeout: Request timeout in seconds
            sign: Whether to sign the message (default: True if authenticator available)
        
        Returns:
            Response envelope if server returns one, None otherwise
        
        Raises:
            ValueError: If recipient not registered
            requests.exceptions.RequestException: If HTTP request fails
        '''
        # Check if recipient is registered
        if recipient_id not in self.controller_registry:
            raise ValueError(
                f"Recipient '{recipient_id}' not in controller registry. "
                f"Known controllers: {list(self.controller_registry.keys())}"
            )
        
        # Create message envelope
        envelope = MessageEnvelope(
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=message_type,
            payload=payload,
            correlation_id=correlation_id,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Convert to dict
        message_dict = envelope.to_dict()
        
        # Sign message if authenticator available and signing enabled
        if self.authenticator and sign:
            try:
                message_dict = self.authenticator.sign_message(message_dict)
                self.logger.debug(f"Signed message {envelope.message_id}")
            except Exception as e:
                self.logger.error(f"Failed to sign message: {e}")
                raise
        
        # Get recipient's endpoint URL
        base_url = self.controller_registry[recipient_id]
        endpoint_url = f"{base_url}/message/{message_type.value.lower()}"
        
        # Log the send
        self.logger.debug(
            f"HTTP POST: {sender_id} → {recipient_id} "
            f"[{message_type.value}] msg_id={envelope.message_id} "
            f"signed={self.authenticator is not None and sign} "
            f"URL={endpoint_url}"
        )
        
        # Send HTTP request
        try:
            response = self.session.post(
                endpoint_url,
                json=message_dict,  # Now includes signature if signed
                timeout=timeout
            )
            
            # Check HTTP status
            response.raise_for_status()
            
            # Parse response
            response_data = response.json()
            
            # Verify response signature if authenticator available
            if self.authenticator and 'signature' in response_data:
                valid, error = self.authenticator.verify_message(
                    response_data,
                    expected_sender=recipient_id
                )
                
                if not valid:
                    self.logger.error(f"Response signature verification failed: {error}")
                    raise ValueError(f"Invalid response signature: {error}")
                
                self.logger.debug(f"Verified response signature from {recipient_id}")
            
            # Check if response contains a message envelope
            if 'message_id' in response_data:
                # Full envelope response
                response_envelope = MessageEnvelope.from_dict(response_data)
                self.logger.debug(
                    f"HTTP response: {recipient_id} → {sender_id} "
                    f"msg_id={response_envelope.message_id}"
                )
                return response_envelope
            else:
                # Acknowledgment only (no envelope)
                self.logger.debug(f"HTTP response: {response_data.get('status', 'ok')}")
                return None
            
        except requests.exceptions.Timeout:
            self.logger.error(
                f"Request to {recipient_id} timed out after {timeout}s"
            )
            raise
        
        except requests.exceptions.ConnectionError as e:
            self.logger.error(
                f"Connection error to {recipient_id} at {endpoint_url}: {e}"
            )
            raise
        
        except requests.exceptions.HTTPError as e:
            self.logger.error(
                f"HTTP error from {recipient_id}: {e.response.status_code} - {e.response.text}"
            )
            raise
        
        except Exception as e:
            self.logger.error(
                f"Unexpected error sending to {recipient_id}: {e}",
                exc_info=True
            )
            raise
"""

# USAGE EXAMPLE:
"""
from pdsno.security.message_auth import MessageAuthenticator, KeyManager

# Setup key management
key_manager = KeyManager()
shared_secret = key_manager.generate_key("key_rc_gc")

# Create authenticator
auth = MessageAuthenticator(shared_secret, "regional_cntl_zone-A_1")

# Create HTTP client with authentication
http_client = ControllerHTTPClient(authenticator=auth)
http_client.register_controller("global_cntl_1", "http://localhost:8001")

# All messages now automatically signed
response = http_client.send(
    sender_id="regional_cntl_zone-A_1",
    recipient_id="global_cntl_1",
    message_type=MessageType.VALIDATION_REQUEST,
    payload={...}
)
# Message is signed, response signature is verified
"""
