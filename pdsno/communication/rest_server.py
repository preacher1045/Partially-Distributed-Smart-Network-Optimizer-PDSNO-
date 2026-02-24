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
import ssl

from pdsno.communication.message_format import MessageEnvelope, MessageType
from pdsno.security.message_auth import MessageAuthenticator
from pdsno.security.rate_limiter import RateLimiter
from pdsno.monitoring.metrics import (
    start_metrics_server,
    track_rest_error,
    track_rest_latency,
    track_rest_request
)


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
        title: Optional[str] = None,
        authenticator: Optional[MessageAuthenticator] = None,
        enable_tls: bool = False,
        cert_file: Optional[str] = None,
        key_file: Optional[str] = None,
        ca_file: Optional[str] = None,
        client_cert_required: bool = False,
        enable_rate_limiting: bool = False,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        enable_metrics: bool = False,
        metrics_port: int = 9090
    ):
        """
        Initialize REST server for a controller.
        
        Args:
            controller_id: Unique identifier for this controller
            host: Host to bind to (default: localhost)
            port: Port to bind to
            title: Optional API title (defaults to controller_id)
            authenticator: Optional MessageAuthenticator for verifying signatures
        """
        self.controller_id = controller_id
        self.host = host
        self.port = port
        self.authenticator = authenticator
        self.enable_tls = enable_tls
        self.cert_file = cert_file
        self.key_file = key_file
        self.ca_file = ca_file
        self.client_cert_required = client_cert_required
        self.enable_rate_limiting = enable_rate_limiting
        self.rate_limiter = (
            RateLimiter(requests_per_minute=requests_per_minute, burst_size=burst_size)
            if enable_rate_limiting
            else None
        )
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

        if enable_metrics:
            start_metrics_server(metrics_port)

        # Register middleware
        self._register_middlewares()
        
        # Register core routes
        self._register_core_routes()
        
        # Server task handle
        self._server_task = None

    def _register_middlewares(self):
        """Register HTTP middleware for rate limiting and metrics."""

        @self.app.middleware("http")
        async def rate_limit_middleware(request: Request, call_next):
            start_time = time.monotonic()
            method = request.method
            path = request.url.path
            client_id = self._get_client_id(request)

            try:
                if self.rate_limiter:
                    allowed, reason = self.rate_limiter.allow_request(client_id)
                    if not allowed:
                        track_rest_request(method, path, "429")
                        return JSONResponse(
                            status_code=429,
                            content={"error": reason or "Rate limit exceeded"}
                        )

                response = await call_next(request)
                track_rest_request(method, path, str(response.status_code))
                return response
            except Exception as exc:
                track_rest_error(method, path, type(exc).__name__)
                raise
            finally:
                duration = time.monotonic() - start_time
                track_rest_latency(method, path, duration)

    @staticmethod
    def _get_client_id(request: Request) -> str:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"
    
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
        
        # Register FastAPI route with signature verification
        @self.app.post(endpoint_path, response_model=dict)
        async def handle_message(request: Request):
            """Auto-generated endpoint for {message_type.value}"""
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
        if self.enable_tls and (not self.cert_file or not self.key_file):
            raise ValueError("TLS enabled but cert_file/key_file not provided")

        cert_reqs = ssl.CERT_REQUIRED if self.client_cert_required else ssl.CERT_NONE

        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            access_log=True,
            ssl_keyfile=self.key_file if self.enable_tls else None,
            ssl_certfile=self.cert_file if self.enable_tls else None,
            ssl_ca_certs=self.ca_file if self.enable_tls else None,
            ssl_cert_reqs=cert_reqs if self.enable_tls else ssl.CERT_NONE
        )
        server = uvicorn.Server(config)
        
        scheme = "https" if self.enable_tls else "http"
        self.logger.info(f"Starting REST server on {scheme}://{self.host}:{self.port}")
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
        scheme = "https" if self.enable_tls else "http"
        return f"{scheme}://{self.host}:{self.port}"
    
    def get_endpoint_url(self, message_type: MessageType) -> str:
        """Get the full URL for a specific message type endpoint"""
        return f"{self.get_base_url()}/message/{message_type.value.lower()}"
