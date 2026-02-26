"""
Connection Manager

Manages persistent connections to network devices with pooling and health checks.
"""

from typing import Dict
from datetime import datetime, timezone, timedelta
import logging

from pdsno.adapters import VendorAdapterFactory
from .session import DeviceSession


class ConnectionManager:
    """
    Manage device connections with pooling and health monitoring.
    
    Features:
    - Connection pooling
    - Automatic reconnection
    - Health checks
    - Session timeout
    - Resource cleanup
    """
    
    def __init__(
        self,
        secret_manager,
        max_connections: int = 50,
        session_timeout_minutes: int = 30,
        health_check_interval: int = 60
    ):
        """
        Initialize connection manager.
        
        Args:
            secret_manager: SecretManager for credentials
            max_connections: Maximum concurrent connections
            session_timeout_minutes: Session idle timeout
            health_check_interval: Health check interval in seconds
        """
        self.secret_manager = secret_manager
        self.max_connections = max_connections
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        self.health_check_interval = health_check_interval
        
        self.logger = logging.getLogger(__name__)
        
        # Active sessions: device_id -> DeviceSession
        self.sessions: Dict[str, DeviceSession] = {}
        
        # Connection stats
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'failed_connections': 0,
            'reconnections': 0
        }
    
    def get_or_create_session(
        self,
        device_id: str,
        device_info: Dict
    ) -> DeviceSession:
        """
        Get existing session or create new one.
        
        Args:
            device_id: Device identifier
            device_info: Device connection info
        
        Returns:
            Active DeviceSession
        """
        # Check if session exists
        if device_id in self.sessions:
            session = self.sessions[device_id]
            
            # Check if session still valid
            if session.is_healthy():
                session.update_last_activity()
                return session
            else:
                self.logger.warning(f"Session {device_id} unhealthy, reconnecting")
                self.close_session(device_id)
        
        # Check connection limit
        if len(self.sessions) >= self.max_connections:
            self._cleanup_idle_sessions()
            
            if len(self.sessions) >= self.max_connections:
                raise RuntimeError(
                    f"Max connections ({self.max_connections}) reached"
                )
        
        # Create new session
        session = self._create_session(device_id, device_info)
        self.sessions[device_id] = session
        
        self.stats['total_connections'] += 1
        self.stats['active_connections'] = len(self.sessions)
        
        return session
    
    def _create_session(
        self,
        device_id: str,
        device_info: Dict
    ) -> DeviceSession:
        """Create new device session"""
        self.logger.info(f"Creating session for {device_id}")
        
        # Get credentials from secret manager
        creds = self.secret_manager.retrieve_secret(
            f"device_{device_id}_password"
        )
        
        if creds:
            device_info['password'] = creds.decode()
        
        # Create adapter
        try:
            adapter = VendorAdapterFactory.create_adapter(device_info)
            
            # Connect
            if not adapter.connect(device_info):
                self.stats['failed_connections'] += 1
                raise ConnectionError(f"Failed to connect to {device_id}")
            
            # Create session
            session = DeviceSession(
                device_id=device_id,
                adapter=adapter,
                timeout=self.session_timeout
            )
            
            self.logger.info(f"✓ Session created for {device_id}")
            
            return session
        
        except Exception as e:
            self.stats['failed_connections'] += 1
            self.logger.error(f"Session creation failed: {e}")
            raise
    
    def close_session(self, device_id: str):
        """Close and remove session"""
        if device_id in self.sessions:
            session = self.sessions[device_id]
            session.close()
            del self.sessions[device_id]
            
            self.stats['active_connections'] = len(self.sessions)
            
            self.logger.info(f"Session closed: {device_id}")
    
    def _cleanup_idle_sessions(self):
        """Remove idle sessions"""
        now = datetime.now(timezone.utc)
        to_remove = []
        
        for device_id, session in self.sessions.items():
            if session.is_idle(now):
                to_remove.append(device_id)
        
        for device_id in to_remove:
            self.logger.info(f"Cleaning up idle session: {device_id}")
            self.close_session(device_id)
    
    def execute_on_device(
        self,
        device_id: str,
        device_info: Dict,
        commands: list
    ) -> Dict:
        """
        Execute commands on device.
        
        Args:
            device_id: Device identifier
            device_info: Device connection info
            commands: Commands to execute
        
        Returns:
            Execution result
        """
        try:
            session = self.get_or_create_session(device_id, device_info)
            result = session.execute(commands)
            
            return {
                'success': True,
                'device_id': device_id,
                'result': result
            }
        
        except Exception as e:
            self.logger.error(f"Execution failed on {device_id}: {e}")
            return {
                'success': False,
                'device_id': device_id,
                'error': str(e)
            }
    
    def health_check_all(self) -> Dict:
        """Check health of all sessions"""
        healthy = []
        unhealthy = []
        
        for device_id, session in self.sessions.items():
            if session.is_healthy():
                healthy.append(device_id)
            else:
                unhealthy.append(device_id)
        
        return {
            'total': len(self.sessions),
            'healthy': len(healthy),
            'unhealthy': len(unhealthy),
            'unhealthy_devices': unhealthy
        }
    
    def get_stats(self) -> Dict:
        """Get connection statistics"""
        return {
            **self.stats,
            'active_sessions': len(self.sessions)
        }
    
    def shutdown(self):
        """Close all sessions"""
        self.logger.info("Shutting down connection manager...")
        
        for device_id in list(self.sessions.keys()):
            self.close_session(device_id)
        
        self.logger.info("All sessions closed")