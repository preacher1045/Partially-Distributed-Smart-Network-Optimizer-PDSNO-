"""
REST API Module

Provides REST-based communication for controller-to-controller messaging.
Implements the synchronous request-response patterns from communication_model.md
"""

import requests
from typing import Dict, Any, Optional

from .message_format import MessageEnvelope, MessageType


class RESTClient:
    """
    REST client for controller-to-controller communication.
    
    Handles synchronous request-response patterns like validation,
    config approval, and discovery coordination.
    """
    
    def __init__(self, controller_id: str, timeout: int = 30):
        """
        Initialize REST client.
        
        Args:
            controller_id: ID of the controller using this client
            timeout: Request timeout in seconds
        """
        self.controller_id = controller_id
        self.timeout = timeout
        self.session = requests.Session()
    
    def send_message(
        self,
        recipient_url: str,
        message_type: MessageType,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a message to another controller via REST.
        
        Args:
            recipient_url: Base URL of recipient controller
            message_type: Type of message to send
            payload: Message payload
            correlation_id: Optional correlation ID for request-response pairing
        
        Returns:
            Response payload as dictionary
        
        Raises:
            requests.RequestException: On network or HTTP errors
        """
        envelope = MessageEnvelope(
            message_type=message_type,
            sender_id=self.controller_id,
            recipient_id="",  # Will be filled by recipient
            payload=payload,
            correlation_id=correlation_id
        )
        
        response = self.session.post(
            f"{recipient_url}/api/messages",
            json=envelope.to_dict(),
            timeout=self.timeout,
            headers={"Content-Type": "application/json"}
        )
        
        response.raise_for_status()
        return response.json()
    
    def close(self):
        """Close the HTTP session"""
        self.session.close()


class RESTServer:
    """
    Placeholder for REST server implementation.
    
    Full implementation requires FastAPI and will be added
    in later phases when controllers need to expose REST endpoints.
    """
