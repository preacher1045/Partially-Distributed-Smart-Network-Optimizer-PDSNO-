"""
PDSNO Device Management Module

Provides device connection and session management:
- ConnectionManager: Persistent connection pool
- Session: Device session abstraction

Usage:
    from pdsno.devices import ConnectionManager

    conn_mgr = ConnectionManager(secret_manager)
    conn = conn_mgr.connect(device_id)
    result = conn_mgr.execute(device_id, commands)
"""

from .connection_manager import ConnectionManager
from .session import Session

__all__ = [
    "ConnectionManager",
    "Session",
]
