# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

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
    REST server wrapper for controller endpoints.

    Uses ControllerRESTServer to expose health and message routes.
    """

    def __init__(
        self,
        controller_id: str,
        host: str = "127.0.0.1",
        port: int = 8000,
        title: Optional[str] = None,
        authenticator=None,
        enable_tls: bool = False,
        cert_file: Optional[str] = None,
        key_file: Optional[str] = None,
        ca_file: Optional[str] = None,
        client_cert_required: bool = False,
        enable_rate_limiting: bool = False,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        enable_metrics: bool = False,
        metrics_port: int = 9090,
    ):
        from pdsno.communication.rest_server import ControllerRESTServer

        self._server = ControllerRESTServer(
            controller_id=controller_id,
            host=host,
            port=port,
            title=title,
            authenticator=authenticator,
            enable_tls=enable_tls,
            cert_file=cert_file,
            key_file=key_file,
            ca_file=ca_file,
            client_cert_required=client_cert_required,
            enable_rate_limiting=enable_rate_limiting,
            requests_per_minute=requests_per_minute,
            burst_size=burst_size,
            enable_metrics=enable_metrics,
            metrics_port=metrics_port,
        )

    def register_handler(self, message_type: MessageType, handler):
        return self._server.register_handler(message_type, handler)

    async def start(self):
        await self._server.start()

    def start_background(self):
        self._server.start_background()

    def get_base_url(self) -> str:
        return self._server.get_base_url()

    def get_endpoint_url(self, message_type: MessageType) -> str:
        return self._server.get_endpoint_url(message_type)
