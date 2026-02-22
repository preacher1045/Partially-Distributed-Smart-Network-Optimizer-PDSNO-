"""
Base REST Server for Controllers

Provides FastAPI server infrastructure that all controllers can use.
Each controller gets its own server instance running on a different port.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
import logging
from typing import Callable, Dict, Optional
from datetime import datetime, timezone
import asyncio
import threading
import time

from pdsno.communication.message_format import MessageEnvelope, MessageType


class ControllerRESTServer:
    """
    FastAPI server for controller-to-controller communication.
    
    Each controller runs its own server instance on a unique port.
    Provides automatic endpoint registration for message handlers.
    """
    
    def __init__(
        self,
        controller_id: str,
        host: str = "127.0.0.1",
        port: int = 8000,
        title: Optional[str] = None
    ):
        """
        Initialize REST server for a controller.
        
        Args:
            controller_id: Unique identifier for this controller
            host: Host to bind to (default: localhost)
            port: Port to bind to
            title: Optional API title (defaults to controller_id)
        """
        self.controller_id = controller_id
        self.host = host
        self.port = port
        self.logger = logging.getLogger(f"{__name__}.{controller_id}")
        
        # Message handlers registry: MessageType -> handler function
        self.handlers: Dict[MessageType, Callable] = {}
        
        # Create FastAPI app
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup
            self.logger.info(f"Controller REST server starting on {host}:{port}")
            yield
            # Shutdown
            self.logger.info(f"Controller REST server shutting down")
        
        self.app = FastAPI(
            title=title or f"{controller_id} API",
            description=f"REST API for {controller_id}",
            version="1.0.0",
            lifespan=lifespan
        )
        
        # Register core routes
        self._register_core_routes()
        
        # Server task handle
        self._server_task = None
    
    def register_handler(self, message_type: MessageType, handler: Callable):
        """
        Register a message handler for a specific message type.
        
        Args:
            message_type: Type of message this handler processes
            handler: Function that handles the message
                    Signature: handler(envelope: MessageEnvelope) -> Optional[MessageEnvelope]
        """
        self.handlers[message_type] = handler
        
        # Create endpoint path
        endpoint_path = f"/message/{message_type.value.lower()}"
        
        # Register FastAPI route
        @self.app.post(endpoint_path, response_model=dict)
        async def handle_message(request: Request):
            """Auto-generated endpoint for {message_type.value}"""
            try:
                # Parse request body
                body = await request.json()
                
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
                    f"[msg_id: {envelope.message_id}]"
                )
                
                # Call handler
                response_envelope = handler(envelope)
                
                # Return response
                if response_envelope:
                    return response_envelope.to_dict()
                else:
                    return {"status": "accepted"}
                    
            except Exception as e:
                self.logger.error(f"Error handling {message_type.value}: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))
        
        self.logger.info(f"Registered handler for {message_type.value} at {endpoint_path}")
    
    def _register_core_routes(self):
        """Register core routes available on all controllers"""
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {
                "status": "healthy",
                "controller_id": self.controller_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        @self.app.get("/info")
        async def controller_info():
            """Controller information endpoint"""
            return {
                "controller_id": self.controller_id,
                "registered_handlers": [mt.value for mt in self.handlers.keys()],
                "host": self.host,
                "port": self.port
            }
    
    async def start(self):
        """Start the FastAPI server (async)"""
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            access_log=True
        )
        server = uvicorn.Server(config)
        
        self.logger.info(f"Starting REST server on http://{self.host}:{self.port}")
        await server.serve()
    
    def start_background(self):
        """Start the server in a background thread"""
        def run_server():
            asyncio.run(self.start())
        
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        
        self.logger.info(f"REST server started in background on port {self.port}")
        
        # Give server time to start
        time.sleep(1)
    
    def get_base_url(self) -> str:
        """Get the base URL for this controller's API"""
        return f"http://{self.host}:{self.port}"
    
    def get_endpoint_url(self, message_type: MessageType) -> str:
        """Get the full URL for a specific message type endpoint"""
        return f"{self.get_base_url()}/message/{message_type.value.lower()}"
