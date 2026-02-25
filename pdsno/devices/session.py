"""
Device Session

Represents a persistent connection to a network device.
"""

from enum import Enum
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import logging


class SessionState(Enum):
    """Session states"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    IDLE = "idle"
    ERROR = "error"
    CLOSED = "closed"


class DeviceSession:
    """
    Persistent session to a network device.
    
    Tracks connection state, activity, and provides command execution.
    """
    
    def __init__(
        self,
        device_id: str,
        adapter,
        timeout: timedelta = timedelta(minutes=30)
    ):
        """
        Initialize device session.
        
        Args:
            device_id: Device identifier
            adapter: VendorAdapter instance
            timeout: Session timeout
        """
        self.device_id = device_id
        self.adapter = adapter
        self.timeout = timeout
        
        self.state = SessionState.CONNECTED
        self.created_at = datetime.now(timezone.utc)
        self.last_activity = self.created_at
        self.command_count = 0
        self.error_count = 0
        
        self.logger = logging.getLogger(f"{__name__}.{device_id}")
    
    def execute(self, commands: list) -> Dict:
        """
        Execute commands on device.
        
        Args:
            commands: List of commands
        
        Returns:
            Execution result
        """
        if self.state == SessionState.CLOSED:
            raise RuntimeError("Session is closed")
        
        try:
            result = self.adapter.apply_config(commands)
            
            self.command_count += 1
            self.update_last_activity()
            
            if not result['success']:
                self.error_count += 1
            
            return result
        
        except Exception as e:
            self.error_count += 1
            self.state = SessionState.ERROR
            self.logger.error(f"Command execution failed: {e}")
            raise
    
    def get_config(self) -> str:
        """Get device configuration"""
        if self.state == SessionState.CLOSED:
            raise RuntimeError("Session is closed")
        
        self.update_last_activity()
        return self.adapter.get_running_config()
    
    def update_last_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now(timezone.utc)
        if self.state == SessionState.IDLE:
            self.state = SessionState.CONNECTED
    
    def is_healthy(self) -> bool:
        """Check if session is healthy"""
        return (
            self.state in [SessionState.CONNECTED, SessionState.IDLE] and
            self.adapter.is_connected() and
            not self.is_idle()
        )
    
    def is_idle(self, now: Optional[datetime] = None) -> bool:
        """Check if session is idle"""
        if now is None:
            now = datetime.now(timezone.utc)
        
        idle_time = now - self.last_activity
        
        if idle_time > self.timeout:
            self.state = SessionState.IDLE
            return True
        
        return False
    
    def get_stats(self) -> Dict:
        """Get session statistics"""
        return {
            'device_id': self.device_id,
            'state': self.state.value,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'uptime_seconds': (datetime.now(timezone.utc) - self.created_at).total_seconds(),
            'command_count': self.command_count,
            'error_count': self.error_count
        }
    
    def close(self):
        """Close session"""
        if self.state != SessionState.CLOSED:
            self.adapter.disconnect()
            self.state = SessionState.CLOSED
            self.logger.info(f"Session closed for {self.device_id}")