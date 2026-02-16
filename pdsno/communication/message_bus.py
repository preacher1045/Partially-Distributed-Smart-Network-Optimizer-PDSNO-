"""
In-Process Message Bus

Phase 4 implementation: Controllers communicate via direct Python function calls
wrapped in message envelope objects. No network involved.

This same envelope format transitions to REST/MQTT in Phase 6 — only the transport
layer changes, not the message format.
"""

from typing import Dict, Callable, Optional
from datetime import datetime, timezone
import logging

from .message_format import MessageEnvelope, MessageType


class MessageBus:
    """
    In-process message bus for controller communication.
    
    Routes messages between controller instances based on recipient_id.
    Each controller registers a handler function for each message type it handles.
    """
    
    def __init__(self):
        """Initialize message bus with empty handler registry"""
        self.handlers: Dict[str, Dict[MessageType, Callable]] = {}
        self.logger = logging.getLogger(__name__)
    
    def register_controller(
        self,
        controller_id: str,
        handlers: Dict[MessageType, Callable]
    ):
        """
        Register a controller and its message handlers.
        
        Args:
            controller_id: Unique controller identifier
            handlers: Dict mapping MessageType to handler functions
                     Handler signature: def handler(envelope: MessageEnvelope) -> MessageEnvelope | None
        """
        if controller_id in self.handlers:
            self.logger.warning(f"Controller {controller_id} already registered, overwriting")
        
        self.handlers[controller_id] = handlers
        self.logger.info(
            f"Registered controller {controller_id} with {len(handlers)} handlers"
        )
    
    def unregister_controller(self, controller_id: str):
        """Remove a controller from the bus"""
        if controller_id in self.handlers:
            del self.handlers[controller_id]
            self.logger.info(f"Unregistered controller {controller_id}")
    
    def send(
        self,
        sender_id: str,
        recipient_id: str,
        message_type: MessageType,
        payload: Dict,
        correlation_id: Optional[str] = None
    ) -> Optional[MessageEnvelope]:
        """
        Send a message to a registered controller.
        
        Args:
            sender_id: ID of sending controller
            recipient_id: ID of receiving controller
            message_type: Type of message being sent
            payload: Message payload dictionary
            correlation_id: Optional ID for request-response pairing
        
        Returns:
            Response envelope if the handler returns one, None otherwise
        
        Raises:
            ValueError: If recipient is not registered or has no handler for this message type
        """
        # Create message envelope
        envelope = MessageEnvelope(
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=message_type,
            payload=payload,
            correlation_id=correlation_id,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Log the send
        self.logger.debug(
            f"Message bus: {sender_id} → {recipient_id} "
            f"[{message_type.value}] msg_id={envelope.message_id}"
        )
        
        # Check if recipient exists
        if recipient_id not in self.handlers:
            raise ValueError(
                f"Recipient controller '{recipient_id}' not registered with message bus"
            )
        
        # Check if recipient has a handler for this message type
        controller_handlers = self.handlers[recipient_id]
        if message_type not in controller_handlers:
            raise ValueError(
                f"Controller '{recipient_id}' has no handler for {message_type.value}"
            )
        
        # Call the handler
        handler = controller_handlers[message_type]
        try:
            response = handler(envelope)
            
            if response is not None:
                self.logger.debug(
                    f"Message bus: {recipient_id} → {sender_id} "
                    f"[response] msg_id={response.message_id}"
                )
            
            return response
            
        except Exception as e:
            self.logger.error(
                f"Handler error in {recipient_id} for {message_type.value}: {e}",
                exc_info=True
            )
            raise
    
    def is_registered(self, controller_id: str) -> bool:
        """Check if a controller is registered"""
        return controller_id in self.handlers
    
    def get_registered_controllers(self) -> list[str]:
        """Get list of all registered controller IDs"""
        return list(self.handlers.keys())
