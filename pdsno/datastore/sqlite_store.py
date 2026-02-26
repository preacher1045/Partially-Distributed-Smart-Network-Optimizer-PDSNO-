"""
NIBStore — Network Information Base Storage Interface

SQLite-backed implementation of the NIB as specified in docs/nib_spec.md
Provides optimistic locking for conflict detection and thread-safe access.
"""

import sqlite3
import json
import hmac
import hashlib
import uuid
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List
from contextlib import contextmanager

from .models import (
    Device, Config, Event, Lock, Controller, NIBResult, DeviceStatus,
    ConfigStatus, LockType
)


class NIBStore:
    """
    Network Information Base storage layer.
    
    Provides thread-safe access to network state with optimistic locking
    for write conflict detection.
    """
    
    def __init__(self, db_path: str = "config/pdsno.db", secret_key: Optional[bytes] = None):
        """
        Initialize NIB store.
        
        Args:
            db_path: Path to SQLite database file
            secret_key: Secret key for HMAC signatures (event log integrity)
        """
        self.logger = logging.getLogger(__name__)
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Secret key for event log signatures
        self.secret_key = secret_key or b"pdsno-dev-secret-change-in-production"
        
        # Initialize schema
        self._initialize_schema()
        
        # Enable foreign keys by default for all connections
        with self._get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.commit()
            
        self.logger.debug("Foreign keys enabled for database")
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Access columns by name
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _initialize_schema(self):
        """Create NIB tables if they don't exist"""
        schema = """
        -- Device Table
        CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY,
            temp_scan_id TEXT,
            ip_address TEXT NOT NULL,
            mac_address TEXT UNIQUE NOT NULL,
            hostname TEXT,
            vendor TEXT,
            device_type TEXT,
            status TEXT NOT NULL DEFAULT 'discovered',
            first_seen TEXT,
            last_seen TEXT,
            managed_by_lc TEXT,
            region TEXT,
            version INTEGER NOT NULL DEFAULT 0,
            metadata TEXT DEFAULT '{}'
        );
        
        -- Config Table
        CREATE TABLE IF NOT EXISTS configs (
            config_id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            config_data TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'proposed',
            proposed_by TEXT,
            approved_by TEXT,
            proposed_at TEXT,
            approved_at TEXT,
            applied_at TEXT,
            reason TEXT,
            version INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (device_id) REFERENCES devices(device_id)
        );
        
        -- Policy Table
        CREATE TABLE IF NOT EXISTS policies (
            policy_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            rule_set TEXT NOT NULL,
            scope TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_by TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT,
            version INTEGER NOT NULL DEFAULT 0
        );
        
        -- Event Log Table (Immutable)
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            controller_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            details TEXT NOT NULL,
            signature TEXT NOT NULL
        );
        
        -- Prevent modifications to event log
        CREATE TRIGGER IF NOT EXISTS prevent_event_update
        BEFORE UPDATE ON events
        BEGIN
            SELECT RAISE(FAIL, 'Event log is immutable - updates not allowed');
        END;
        
        CREATE TRIGGER IF NOT EXISTS prevent_event_delete
        BEFORE DELETE ON events
        BEGIN
            SELECT RAISE(FAIL, 'Event log is immutable - deletions not allowed');
        END;
        
        -- Controller Sync Table (Locks)
        CREATE TABLE IF NOT EXISTS locks (
            lock_id TEXT PRIMARY KEY,
            subject_id TEXT NOT NULL,
            lock_type TEXT NOT NULL,
            held_by TEXT NOT NULL,
            acquired_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );
        
        -- Controller Identity Table
        CREATE TABLE IF NOT EXISTS controllers (
            controller_id TEXT PRIMARY KEY,
            role TEXT NOT NULL,
            region TEXT,
            status TEXT NOT NULL DEFAULT 'validating',
            validated_by TEXT,
            validated_at TEXT,
            public_key TEXT,
            certificate TEXT,
            capabilities TEXT DEFAULT '[]',
            metadata TEXT DEFAULT '{}',
            version INTEGER NOT NULL DEFAULT 0
        );
        
        -- Indexes for common queries
        CREATE INDEX IF NOT EXISTS idx_devices_mac ON devices(mac_address);
        CREATE INDEX IF NOT EXISTS idx_devices_region ON devices(region);
        CREATE INDEX IF NOT EXISTS idx_configs_device ON configs(device_id);
        CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
        CREATE INDEX IF NOT EXISTS idx_events_controller ON events(controller_id);
        CREATE INDEX IF NOT EXISTS idx_locks_subject ON locks(subject_id, lock_type);
        """
        
        with self._get_connection() as conn:
            conn.executescript(schema)
    
    # ===== Device Operations =====
    
    def get_device(self, device_id: str) -> Optional[Device]:
        """Get device by NIB ID"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM devices WHERE device_id = ?",
                (device_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_device(row)
            return None
    
    def get_device_by_mac(self, mac_address: str) -> Optional[Device]:
        """Get device by MAC address"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM devices WHERE mac_address = ?",
                (mac_address,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_device(row)
            return None
    
    def upsert_device(self, device: Device) -> NIBResult:
        """
        Insert or update device with optimistic locking.
        
        Returns:
            NIBResult with success=False and conflict=True on version mismatch
        """
        with self._get_connection() as conn:
            # Check if device exists
            existing = self.get_device_by_mac(device.mac_address)
            
            if existing:
                # Update with version check
                cursor = conn.execute(
                    """
                    UPDATE devices SET
                        ip_address = ?, hostname = ?, vendor = ?, device_type = ?,
                        status = ?, last_seen = ?, managed_by_lc = ?, region = ?,
                        metadata = ?, version = version + 1
                    WHERE mac_address = ? AND version = ?
                    """,
                    (
                        device.ip_address, device.hostname, device.vendor, device.device_type,
                        device.status.value, device.last_seen.isoformat() if device.last_seen else None,
                        device.managed_by_lc, device.region,
                        json.dumps(device.metadata), device.mac_address, device.version
                    )
                )
                
                if cursor.rowcount == 0:
                    return NIBResult(
                        success=False,
                        error="CONFLICT: Version mismatch - device was modified by another process",
                        conflict=True
                    )
                
                return NIBResult(success=True, data=existing.device_id)
            else:
                # Insert new device
                device.device_id = device.device_id or f"nib-dev-{uuid.uuid4().hex[:8]}"
                device.first_seen = device.first_seen or datetime.now(timezone.utc)
                device.last_seen = device.last_seen or datetime.now(timezone.utc)
                
                conn.execute(
                    """
                    INSERT INTO devices (
                        device_id, temp_scan_id, ip_address, mac_address, hostname,
                        vendor, device_type, status, first_seen, last_seen,
                        managed_by_lc, region, version, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        device.device_id, device.temp_scan_id, device.ip_address,
                        device.mac_address, device.hostname, device.vendor, device.device_type,
                        device.status.value, device.first_seen.isoformat(), device.last_seen.isoformat(),
                        device.managed_by_lc, device.region, 0, json.dumps(device.metadata)
                    )
                )
                
                return NIBResult(success=True, data=device.device_id)

    # ===== Controller Operations =====

    def get_controller(self, controller_id: str) -> Optional[Controller]:
        """Get controller by ID"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM controllers WHERE controller_id = ?",
                (controller_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_controller(row)
            return None

    def get_controllers_by_region(self, region: str) -> List[Controller]:
        """Get all controllers in a specific region"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM controllers WHERE region = ? AND status = 'active'",
                (region,)
            )
            return [self._row_to_controller(row) for row in cursor.fetchall()]

    def upsert_controller(self, controller: Controller) -> NIBResult:
        """
        Insert or update controller with optimistic locking.
        
        Returns:
            NIBResult with success=False and conflict=True on version mismatch
        """
        with self._get_connection() as conn:
            # Check if controller exists
            existing = self.get_controller(controller.controller_id)
            
            if existing:
                # Update with version check
                cursor = conn.execute(
                    """
                    UPDATE controllers SET
                        role = ?, region = ?, status = ?, validated_by = ?,
                        validated_at = ?, public_key = ?, certificate = ?,
                        capabilities = ?, metadata = ?, version = version + 1
                    WHERE controller_id = ? AND version = ?
                    """,
                    (
                        controller.role, controller.region, controller.status,
                        controller.validated_by,
                        controller.validated_at.isoformat() if controller.validated_at else None,
                        controller.public_key, controller.certificate,
                        json.dumps(controller.capabilities) if isinstance(controller.capabilities, list) else controller.capabilities,
                        json.dumps(controller.metadata) if isinstance(controller.metadata, dict) else controller.metadata,
                        controller.controller_id, controller.version
                    )
                )
                
                if cursor.rowcount == 0:
                    return NIBResult(
                        success=False,
                        error="CONFLICT: Version mismatch - controller was modified by another process",
                        conflict=True
                    )
                
                return NIBResult(success=True, data=controller.controller_id)
            else:
                # Insert new controller
                controller.validated_at = controller.validated_at or datetime.now(timezone.utc)
                
                conn.execute(
                    """
                    INSERT INTO controllers (
                        controller_id, role, region, status, validated_by,
                        validated_at, public_key, certificate, capabilities,
                        metadata, version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        controller.controller_id, controller.role, controller.region,
                        controller.status, controller.validated_by,
                        controller.validated_at.isoformat(),
                        controller.public_key, controller.certificate,
                        json.dumps(controller.capabilities) if isinstance(controller.capabilities, list) else controller.capabilities,
                        json.dumps(controller.metadata) if isinstance(controller.metadata, dict) else controller.metadata,
                        controller.version
                    )
                )
                
                return NIBResult(success=True, data=controller.controller_id)
            
    # Add these methods to the NIBStore class in sqlite_store.py

            
    # ===== Config Operations =====

    def upsert_config(self, config: Config) -> NIBResult:
        """
        Insert or update configuration record with optimistic locking.
        
        Args:
            config: Config object to store
        
        Returns:
            NIBResult with success status
        """
        with self._get_connection() as conn:
            # Check if config exists
            existing = self.get_config(config.config_id)
            
            if existing:
                # Update with version check
                cursor = conn.execute(
                    """
                    UPDATE configs SET
                        device_id = ?, config_data = ?, status = ?,
                        proposed_by = ?, approved_by = ?,
                        proposed_at = ?, approved_at = ?, applied_at = ?,
                        reason = ?, version = version + 1
                    WHERE config_id = ? AND version = ?
                    """,
                    (
                        config.device_id, config.config_data, config.status.value,
                        config.proposed_by, config.approved_by,
                        config.proposed_at.isoformat() if config.proposed_at else None,
                        config.approved_at.isoformat() if config.approved_at else None,
                        config.applied_at.isoformat() if config.applied_at else None,
                        config.reason, config.config_id, config.version
                    )
                )
                
                if cursor.rowcount == 0:
                    return NIBResult(
                        success=False,
                        error="CONFLICT: Version mismatch - config was modified by another process",
                        conflict=True
                    )
                
                return NIBResult(success=True, data=config.config_id)
            else:
                # Insert new config
                config.proposed_at = config.proposed_at or datetime.now(timezone.utc)
                
                conn.execute(
                    """
                    INSERT INTO configs (
                        config_id, device_id, config_data, status,
                        proposed_by, approved_by, proposed_at, approved_at,
                        applied_at, reason, version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        config.config_id, config.device_id, config.config_data,
                        config.status.value, config.proposed_by, config.approved_by,
                        config.proposed_at.isoformat() if config.proposed_at else None,
                        config.approved_at.isoformat() if config.approved_at else None,
                        config.applied_at.isoformat() if config.applied_at else None,
                        config.reason, 0
                    )
                )
                
                return NIBResult(success=True, data=config.config_id)


    def get_config(self, config_id: str) -> Optional[Config]:
        """
        Get configuration record by ID.
        
        Args:
            config_id: Configuration ID
        
        Returns:
            Config object or None
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM configs WHERE config_id = ?",
                (config_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return Config(
                    config_id=row['config_id'],
                    device_id=row['device_id'],
                    config_data=row['config_data'],
                    status=ConfigStatus(row['status']),
                    proposed_by=row['proposed_by'],
                    approved_by=row['approved_by'],
                    proposed_at=datetime.fromisoformat(row['proposed_at']) if row['proposed_at'] else None,
                    approved_at=datetime.fromisoformat(row['approved_at']) if row['approved_at'] else None,
                    applied_at=datetime.fromisoformat(row['applied_at']) if row['applied_at'] else None,
                    reason=row['reason'],
                    version=row['version']
                )
            
            return None

    def _row_to_controller(self, row: sqlite3.Row) -> Controller:
        """Convert database row to Controller object"""
        return Controller(
            controller_id=row['controller_id'],
            role=row['role'],
            region=row['region'],
            status=row['status'],
            validated_by=row['validated_by'],
            validated_at=datetime.fromisoformat(row['validated_at']) if row['validated_at'] else None,
            public_key=row['public_key'],
            certificate=row['certificate'],
            capabilities=json.loads(row['capabilities']) if row['capabilities'] else [],
            metadata=json.loads(row['metadata']) if row['metadata'] else {},
            version=row['version']
        )

    
    # ===== Event Log Operations =====
    
    def write_event(self, event: Event) -> NIBResult:
        """
        Write an immutable event to the audit log.
        
        Automatically signs the event with HMAC for tamper-evidence.
        """
        # Generate signature
        event_content = f"{event.event_type}{event.controller_id}{event.timestamp.isoformat()}{json.dumps(event.details)}"
        signature = hmac.new(
            self.secret_key,
            event_content.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        event.event_id = event.event_id or f"evt-{uuid.uuid4().hex[:12]}"
        event.signature = signature
        
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO events (event_id, event_type, controller_id, timestamp, details, signature)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id, event.event_type, event.controller_id,
                    event.timestamp.isoformat(), json.dumps(event.details), signature
                )
            )
        
        return NIBResult(success=True, data=event.event_id)
    
    # ===== Lock Operations =====
    
    def acquire_lock(
        self,
        subject_id: str,
        lock_type: LockType,
        held_by: str,
        ttl_seconds: int = 300
    ) -> NIBResult:
        """
        Acquire a coordination lock.
        
        Fails if an unexpired lock already exists for the same subject+type.
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)
        
        with self._get_connection() as conn:
            # Clean up expired locks first
            conn.execute(
                "DELETE FROM locks WHERE expires_at < ?",
                (now.isoformat(),)
            )
            
            # Check for existing lock
            existing = conn.execute(
                "SELECT * FROM locks WHERE subject_id = ? AND lock_type = ?",
                (subject_id, lock_type.value)
            ).fetchone()
            
            if existing:
                return NIBResult(
                    success=False,
                    error=f"Lock already held by {existing['held_by']}"
                )
            
            # Acquire lock
            lock_id = f"lock-{uuid.uuid4().hex[:12]}"
            conn.execute(
                """
                INSERT INTO locks (lock_id, subject_id, lock_type, held_by, acquired_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (lock_id, subject_id, lock_type.value, held_by, now.isoformat(), expires_at.isoformat())
            )
            
            return NIBResult(success=True, data=lock_id)
    
    def release_lock(self, lock_id: str, held_by: str) -> NIBResult:
        """Release a lock (only by the holder)"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM locks WHERE lock_id = ? AND held_by = ?",
                (lock_id, held_by)
            )
            
            if cursor.rowcount == 0:
                return NIBResult(success=False, error="Lock not found or not held by you")
            
            return NIBResult(success=True)
    
    def check_lock(self, subject_id: str, lock_type: LockType) -> Optional[Lock]:
        """Check if a lock exists and is not expired"""
        now = datetime.now(timezone.utc)
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM locks WHERE subject_id = ? AND lock_type = ? AND expires_at > ?",
                (subject_id, lock_type.value, now.isoformat())
            )
            row = cursor.fetchone()
            if row:
                return Lock(
                    lock_id=row['lock_id'],
                    subject_id=row['subject_id'],
                    lock_type=LockType(row['lock_type']),
                    held_by=row['held_by'],
                    acquired_at=datetime.fromisoformat(row['acquired_at']),
                    expires_at=datetime.fromisoformat(row['expires_at'])
                )
            return None
    
    # ===== Helper Methods =====
    
    def _row_to_device(self, row: sqlite3.Row) -> Device:
        """Convert database row to Device object"""
        return Device(
            device_id=row['device_id'],
            temp_scan_id=row['temp_scan_id'],
            ip_address=row['ip_address'],
            mac_address=row['mac_address'],
            hostname=row['hostname'],
            vendor=row['vendor'],
            device_type=row['device_type'],
            status=DeviceStatus(row['status']),
            first_seen=datetime.fromisoformat(row['first_seen']) if row['first_seen'] else None,
            last_seen=datetime.fromisoformat(row['last_seen']) if row['last_seen'] else None,
            managed_by_lc=row['managed_by_lc'],
            region=row['region'],
            version=row['version'],
            metadata=json.loads(row['metadata'])
        )

    def _row_to_controller(self, row: sqlite3.Row) -> Controller:
        """Convert database row to Controller object"""
        return Controller(
            controller_id=row['controller_id'],
            role=row['role'],
            region=row['region'],
            status=row['status'],
            validated_by=row['validated_by'],
            validated_at=datetime.fromisoformat(row['validated_at']) if row['validated_at'] else None,
            public_key=row['public_key'],
            certificate=row['certificate'],
            capabilities=json.loads(row['capabilities']),
            metadata=json.loads(row['metadata']),
            version=row['version'],
        )
