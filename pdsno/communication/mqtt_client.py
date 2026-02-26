"""
MQTT Client for Pub/Sub Messaging

Adds publish-subscribe capability to controllers for:
- Discovery reports (LC publishes, RC subscribes)
- Policy updates (GC publishes, RC/LC subscribe)
- System events (broadcast notifications)
"""

import paho.mqtt.client as mqtt
import json
import logging
from typing import Callable, Dict, Optional
from datetime import datetime, timezone
import threading
import time
import ssl

from pdsno.communication.message_format import MessageEnvelope, MessageType


class ControllerMQTTClient:
    """
    MQTT client for pub/sub communication between controllers.
    
    Use cases:
    - Discovery reports: LC publishes to region topic, RC subscribes
    - Policy updates: GC publishes to global topic, all subscribe
    - System events: Broadcast notifications
    """
    
    def __init__(
        self,
        controller_id: str,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = False,
        ca_certs: Optional[str] = None,
        certfile: Optional[str] = None,
        keyfile: Optional[str] = None,
        tls_insecure: bool = False
    ):
        """
        Initialize MQTT client.
        
        Args:
            controller_id: Unique controller identifier
            broker_host: MQTT broker hostname
            broker_port: MQTT broker port (default: 1883)
            username: Optional MQTT username
            password: Optional MQTT password
        """
        self.controller_id = controller_id
        self.broker_host = broker_host
        if use_tls and broker_port == 1883:
            broker_port = 8883

        self.broker_port = broker_port
        self.use_tls = use_tls
        self.ca_certs = ca_certs
        self.certfile = certfile
        self.keyfile = keyfile
        self.tls_insecure = tls_insecure
        self.logger = logging.getLogger(f"{__name__}.{controller_id}")
        
        # Create MQTT client with clean session
        self.client = mqtt.Client(
            client_id=controller_id,
            clean_session=True,
            protocol=mqtt.MQTTv311
        )
        
        # Set authentication if provided
        if username and password:
            self.client.username_pw_set(username, password)

        # Configure TLS if enabled
        if self.use_tls:
            cert_reqs = ssl.CERT_REQUIRED if self.ca_certs else ssl.CERT_NONE
            self.client.tls_set(
                ca_certs=self.ca_certs,
                certfile=self.certfile,
                keyfile=self.keyfile,
                cert_reqs=cert_reqs,
                tls_version=ssl.PROTOCOL_TLS_CLIENT
            )
            self.client.tls_insecure_set(self.tls_insecure)
        
        # Topic handlers: topic_pattern -> handler function
        self.handlers: Dict[str, Callable] = {}
        
        # Connection state
        self.connected = False
        self.connection_lock = threading.Lock()
        
        # Setup callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        self.logger.info(f"MQTT client initialized for {controller_id}")
    
    def connect(self, timeout: int = 10) -> bool:
        """
        Connect to MQTT broker.
        
        Args:
            timeout: Connection timeout in seconds
        
        Returns:
            True if connected successfully, False otherwise
        """
        try:
            self.logger.info(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}")
            
            self.client.connect(
                self.broker_host,
                self.broker_port,
                keepalive=60
            )
            
            # Start network loop in background thread
            self.client.loop_start()
            
            # Wait for connection
            start = time.time()
            while not self.connected and (time.time() - start) < timeout:
                time.sleep(0.1)
            
            if self.connected:
                self.logger.info("✓ Connected to MQTT broker")
                return True
            else:
                self.logger.error("Connection timeout")
                return False
                
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.logger.info("Disconnecting from MQTT broker")
        self.client.loop_stop()
        self.client.disconnect()
        self.connected = False
    
    def publish(
        self,
        topic: str,
        message_type: MessageType,
        payload: Dict,
        qos: int = 1,
        retain: bool = False
    ) -> bool:
        """
        Publish a message to a topic.
        
        Args:
            topic: MQTT topic to publish to
            message_type: Type of message being published
            payload: Message payload
            qos: Quality of Service (0, 1, or 2)
            retain: Whether broker should retain message for future subscribers
        
        Returns:
            True if published successfully, False otherwise
        """
        if not self.connected:
            self.logger.error("Not connected to broker")
            return False
        
        # Create message envelope
        envelope = MessageEnvelope(
            sender_id=self.controller_id,
            recipient_id="broadcast",  # No specific recipient for pub/sub
            message_type=message_type,
            payload=payload,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Serialize to JSON
        message_json = json.dumps(envelope.to_dict())
        
        # Publish
        try:
            result = self.client.publish(
                topic,
                message_json,
                qos=qos,
                retain=retain
            )
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.logger.debug(
                    f"Published {message_type.value} to {topic} "
                    f"[msg_id: {envelope.message_id}, qos: {qos}]"
                )
                return True
            else:
                self.logger.error(f"Publish failed with code {result.rc}")
                return False
                
        except Exception as e:
            self.logger.error(f"Publish error: {e}")
            return False
    
    def subscribe(
        self,
        topic: str,
        handler: Callable[[MessageEnvelope], None],
        qos: int = 1
    ):
        """
        Subscribe to a topic with a handler.
        
        Args:
            topic: MQTT topic to subscribe to (can include wildcards + and #)
            handler: Function to call when message received
                    Signature: handler(envelope: MessageEnvelope) -> None
            qos: Quality of Service (0, 1, or 2)
        """
        if not self.connected:
            self.logger.warning("Not connected, subscription will occur after connection")
        
        # Register handler
        self.handlers[topic] = handler
        
        # Subscribe to topic
        result, mid = self.client.subscribe(topic, qos)
        
        if result == mqtt.MQTT_ERR_SUCCESS:
            self.logger.info(f"Subscribed to {topic} (qos: {qos})")
        else:
            self.logger.error(f"Subscribe failed with code {result}")
    
    def unsubscribe(self, topic: str):
        """Unsubscribe from a topic"""
        self.client.unsubscribe(topic)
        if topic in self.handlers:
            del self.handlers[topic]
        
        self.logger.info(f"Unsubscribed from {topic}")
    
    # MQTT Callbacks
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker"""
        if rc == 0:
            with self.connection_lock:
                self.connected = True
            self.logger.info("MQTT connection established")
            
            # Re-subscribe to all topics
            for topic in self.handlers.keys():
                self.client.subscribe(topic)
                self.logger.info(f"Re-subscribed to {topic}")
        else:
            self.logger.error(f"Connection failed with code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker"""
        with self.connection_lock:
            self.connected = False
        
        if rc == 0:
            self.logger.info("Disconnected from MQTT broker")
        else:
            self.logger.warning(f"Unexpected disconnect (code {rc}), will auto-reconnect")
    
    def _on_message(self, client, userdata, msg):
        """Callback when message received"""
        try:
            # Decode message
            message_json = msg.payload.decode('utf-8')
            message_dict = json.loads(message_json)
            
            # Deserialize to envelope
            envelope = MessageEnvelope.from_dict(message_dict)
            
            # Log receipt
            self.logger.debug(
                f"Received {envelope.message_type.value} on {msg.topic} "
                f"from {envelope.sender_id} [msg_id: {envelope.message_id}]"
            )
            
            # Find matching handler
            handler = self._find_handler(msg.topic)
            
            if handler:
                # Call handler in try-except to prevent one bad handler from breaking others
                try:
                    handler(envelope)
                except Exception as e:
                    self.logger.error(
                        f"Handler error for {msg.topic}: {e}",
                        exc_info=True
                    )
            else:
                self.logger.warning(f"No handler for topic {msg.topic}")
                
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in message: {e}")
        except Exception as e:
            self.logger.error(f"Message processing error: {e}", exc_info=True)
    
    def _find_handler(self, topic: str) -> Optional[Callable]:
        """Find handler for a topic, considering wildcards"""
        # Exact match
        if topic in self.handlers:
            return self.handlers[topic]
        
        # Check wildcard matches
        for pattern, handler in self.handlers.items():
            if self._topic_matches(topic, pattern):
                return handler
        
        return None
    
    @staticmethod
    def _topic_matches(topic: str, pattern: str) -> bool:
        """Check if topic matches pattern with MQTT wildcards"""
        # Split into parts
        topic_parts = topic.split('/')
        pattern_parts = pattern.split('/')
        
        # # wildcard must be last part
        if '#' in pattern_parts:
            if pattern_parts[-1] == '#':
                # Match everything from this level down
                return topic_parts[:len(pattern_parts)-1] == pattern_parts[:-1]
            else:
                return False
        
        # Must have same number of parts if no # wildcard
        if len(topic_parts) != len(pattern_parts):
            return False
        
        # Check each part
        for t, p in zip(topic_parts, pattern_parts):
            if p == '+':
                # Single-level wildcard
                continue
            if t != p:
                return False
        
        return True
