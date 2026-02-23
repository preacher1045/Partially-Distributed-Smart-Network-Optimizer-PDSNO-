"""
REST Server with Message Authentication

Extension to add signature verification to ControllerRESTServer.
Add these methods to your existing pdsno/communication/rest_server.py
"""

# ADD TO IMPORTS:
"""
from typing import Optional
from pdsno.security.message_auth import MessageAuthenticator
"""

# MODIFY ControllerRESTServer.__init__():
"""
    def __init__(
        self,
        controller_id: str,
        host: str = "127.0.0.1",
        port: int = 8000,
        title: Optional[str] = None,
        authenticator: Optional[MessageAuthenticator] = None  # NEW
    ):
        '''
        Initialize REST server for a controller.
        
        Args:
            controller_id: Unique identifier for this controller
            host: Host to bind to (default: localhost)
            port: Port to bind to
            title: Optional API title (defaults to controller_id)
            authenticator: Optional MessageAuthenticator for verifying signatures
        '''
        self.controller_id = controller_id
        self.host = host
        self.port = port
        self.authenticator = authenticator  # NEW
        self.logger = logging.getLogger(f"{__name__}.{controller_id}")
        
        # Message handlers registry: MessageType -> handler function
        self.handlers: Dict[MessageType, Callable] = {}
        
        # ... rest of initialization ...
"""

# MODIFY the endpoint handler in register_handler() to verify signatures:
"""
    def register_handler(self, message_type: MessageType, handler: Callable):
        '''
        Register a message handler for a specific message type.
        
        Args:
            message_type: Type of message this handler processes
            handler: Function that handles the message
                    Signature: handler(envelope: MessageEnvelope) -> Optional[MessageEnvelope]
        '''
        self.handlers[message_type] = handler
        
        # Create endpoint path
        endpoint_path = f"/message/{message_type.value.lower()}"
        
        # Register FastAPI route with signature verification
        @self.app.post(endpoint_path, response_model=dict)
        async def handle_message(request: Request):
            '''Auto-generated endpoint for {message_type.value}'''
            try:
                # Parse request body
                body = await request.json()
                
                # Verify signature if authenticator available
                if self.authenticator:
                    if 'signature' not in body:
                        raise HTTPException(
                            status_code=401,
                            detail="Message signature required but not present"
                        )
                    
                    valid, error = self.authenticator.verify_message(body)
                    
                    if not valid:
                        self.logger.warning(f"Signature verification failed: {error}")
                        raise HTTPException(
                            status_code=401,
                            detail=f"Invalid message signature: {error}"
                        )
                    
                    self.logger.debug(f"Verified signature from {body.get('sender_id')}")
                
                # Deserialize to MessageEnvelope
                envelope = MessageEnvelope.from_dict(body)
                
                # Validate recipient
                if envelope.recipient_id != self.controller_id:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Message recipient '{envelope.recipient_id}' does not match controller '{self.controller_id}'"
                    )
                
                # Log receipt
                self.logger.info(
                    f"Received {envelope.message_type.value} from {envelope.sender_id} "
                    f"[msg_id: {envelope.message_id}] "
                    f"[signed: {self.authenticator is not None}]"
                )
                
                # Call handler
                response_envelope = handler(envelope)
                
                # Sign response if authenticator available
                if response_envelope and self.authenticator:
                    response_dict = response_envelope.to_dict()
                    response_dict = self.authenticator.sign_message(response_dict)
                    return response_dict
                elif response_envelope:
                    return response_envelope.to_dict()
                else:
                    return {"status": "accepted"}
                    
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error handling {message_type.value}: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))
        
        self.logger.info(
            f"Registered handler for {message_type.value} at {endpoint_path} "
            f"[signature verification: {self.authenticator is not None}]"
        )
"""

# USAGE EXAMPLE:
"""
from pdsno.security.message_auth import MessageAuthenticator, KeyManager

# Setup key management
key_manager = KeyManager()
shared_secret = key_manager.generate_key("key_gc_rc")

# Create authenticator
auth = MessageAuthenticator(shared_secret, "global_cntl_1")

# Create REST server with authentication
rest_server = ControllerRESTServer(
    controller_id="global_cntl_1",
    port=8001,
    authenticator=auth  # Enable signature verification
)

# Register handlers
rest_server.register_handler(
    MessageType.VALIDATION_REQUEST,
    handle_validation_request
)

# Start server
rest_server.start_background()

# Now all incoming messages must have valid signatures
# All outgoing responses are automatically signed
"""
