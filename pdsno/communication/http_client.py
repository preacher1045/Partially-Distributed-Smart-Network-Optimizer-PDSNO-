"""
HTTP Client for Controller Communication

Replaces the in-process MessageBus with HTTP POST requests.
Controllers now communicate over the network.
"""

import requests
import logging
from typing import Dict, Optional
from datetime import datetime, timezone
import time

from pdsno.communication.message_format import MessageEnvelope, MessageType


class ControllerHTTPClient:
    """
    HTTP client for sending messages to other controllers.
    
    Replaces MessageBus.send() with actual HTTP POST requests.
    """
    
    def __init__(self, controller_registry: Optional[Dict[str, str]] = None):
        """
        Initialize HTTP client.
        
        Args:
            controller_registry: Dict mapping controller_id -> base_url
                                Example: {"global_cntl_1": "http://localhost:8001"}
        """
        self.controller_registry = controller_registry or {}
        self.logger = logging.getLogger(__name__)
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'PDSNO-Controller-Client/1.0'
        })
    
    def register_controller(self, controller_id: str, base_url: str):
        """
        Register a controller's base URL.
        
        Args:
            controller_id: Controller's unique ID
            base_url: Base URL where controller's REST API is hosted
                     Example: "http://localhost:8001"
        """
        self.controller_registry[controller_id] = base_url
        self.logger.info(f"Registered controller {controller_id} at {base_url}")
    
    def send(
        self,
        sender_id: str,
        recipient_id: str,
        message_type: MessageType,
        payload: Dict,
        correlation_id: Optional[str] = None,
        timeout: int = 30
    ) -> Optional[MessageEnvelope]:
        """
        Send a message to a controller via HTTP POST.
        
        Args:
            sender_id: ID of sending controller
            recipient_id: ID of receiving controller
            message_type: Type of message
            payload: Message payload
            correlation_id: Optional correlation ID for request-response pairing
            timeout: Request timeout in seconds
        
        Returns:
            Response envelope if server returns one, None otherwise
        
        Raises:
            ValueError: If recipient not registered
            requests.exceptions.RequestException: If HTTP request fails
        """
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
        
        # Get recipient's endpoint URL
        base_url = self.controller_registry[recipient_id]
        endpoint_url = f"{base_url}/message/{message_type.value.lower()}"
        
        # Log the send
        self.logger.debug(
            f"HTTP POST: {sender_id} → {recipient_id} "
            f"[{message_type.value}] msg_id={envelope.message_id} "
            f"URL={endpoint_url}"
        )
        
        # Send HTTP request
        try:
            response = self.session.post(
                endpoint_url,
                json=envelope.to_dict(),
                timeout=timeout
            )
            
            # Check HTTP status
            response.raise_for_status()
            
            # Parse response
            response_data = response.json()
            
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
    
    def send_with_retry(
        self,
        sender_id: str,
        recipient_id: str,
        message_type: MessageType,
        payload: Dict,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        **kwargs
    ) -> Optional[MessageEnvelope]:
        """
        Send message with automatic retries on failure.
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds (exponential backoff)
            **kwargs: Additional arguments passed to send()
        
        Returns:
            Response envelope or None
        """
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return self.send(
                    sender_id=sender_id,
                    recipient_id=recipient_id,
                    message_type=message_type,
                    payload=payload,
                    **kwargs
                )
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_exception = e
                
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)  # Exponential backoff
                    self.logger.warning(
                        f"Retry {attempt + 1}/{max_retries} after {delay}s due to: {e}"
                    )
                    time.sleep(delay)
                else:
                    self.logger.error(f"All {max_retries} attempts failed")
        
        # All retries exhausted
        raise last_exception
    
    def health_check(self, controller_id: str, timeout: int = 5) -> bool:
        """
        Check if a controller is reachable.
        
        Args:
            controller_id: Controller to check
            timeout: Request timeout in seconds
        
        Returns:
            True if controller responds to health check, False otherwise
        """
        if controller_id not in self.controller_registry:
            self.logger.warning(f"Controller {controller_id} not registered")
            return False
        
        base_url = self.controller_registry[controller_id]
        health_url = f"{base_url}/health"
        
        try:
            response = self.session.get(health_url, timeout=timeout)
            response.raise_for_status()
            
            data = response.json()
            return data.get('status') == 'healthy'
            
        except Exception as e:
            self.logger.debug(f"Health check failed for {controller_id}: {e}")
            return False
    
    def get_controller_info(self, controller_id: str, timeout: int = 5) -> Optional[Dict]:
        """
        Get information about a controller.
        
        Args:
            controller_id: Controller to query
            timeout: Request timeout in seconds
        
        Returns:
            Controller info dict or None if request fails
        """
        if controller_id not in self.controller_registry:
            return None
        
        base_url = self.controller_registry[controller_id]
        info_url = f"{base_url}/info"
        
        try:
            response = self.session.get(info_url, timeout=timeout)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            self.logger.debug(f"Info request failed for {controller_id}: {e}")
            return None
    
    def close(self):
        """Close the HTTP session"""
        self.session.close()
