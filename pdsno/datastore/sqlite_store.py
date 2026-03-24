# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""
NIBStore — Network Information Base Storage Interface

SQLite-backed implementation of the NIB as specified in docs/nib_spec.md.
Provides optimistic locking for conflict detection and thread-safe access.

Schema alignment history:
    2026-03-22 — Option B: schema brought in line with nib_spec.md.
        See migration_001_schema_alignment.py for upgrade path
        from pre-alignment databases.
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
    Device, Config, ConfigCategory, Event, Lock, Controller,
    NIBResult, DeviceStatus, ConfigStatus, LockType, Policy
)


class NIBStore:
    """
    Network Information Base storage layer.

    All NIB access goes through this class — no controller module
    may import sqlite3 directly or instantiate a storage backend.
    Every method that modifies state returns a NIBResult.
    Callers must check result.success before proceeding.
    """

    def __init__(
        self,
        db_path: str = "config/pdsno.db",
        secret_key: Optional[bytes] = None
    ):
        self.logger = logging.getLogger(__name__)
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.secret_key = secret_key or b"pdsno-dev-secret-change-in-production"
        self._initialize_schema()

        with self._get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.commit()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize_schema(self):
        """Create NIB tables if they don't exist. Schema matches nib_spec.md exactly."""
        schema = """
        -- ── Device Table ─────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS devices (
            device_id          TEXT     PRIMARY KEY,
            temp_scan_id       TEXT,
            ip_address         TEXT     NOT NULL,
            mac_address        TEXT     UNIQUE NOT NULL,
            hostname           TEXT,
            vendor             TEXT,
            device_type        TEXT,
            firmware_version   TEXT,
            region             TEXT,
            local_controller   TEXT,
            status             TEXT     NOT NULL DEFAULT 'active',
            discovery_method   TEXT,
            first_seen         TEXT,
            last_seen          TEXT,
            last_updated       TEXT,
            version            INTEGER  NOT NULL DEFAULT 0,
            metadata           TEXT     DEFAULT '{}'
        );

        -- ── Config Table ──────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS configs (
            config_id          TEXT     PRIMARY KEY,
            device_id          TEXT     NOT NULL,
            config_hash        TEXT     NOT NULL DEFAULT '',
            category           TEXT     NOT NULL DEFAULT 'LOW',
            status             TEXT     NOT NULL DEFAULT 'PENDING',
            proposed_by        TEXT,
            approved_by        TEXT,
            execution_token    TEXT,
            proposed_at        TEXT,
            approved_at        TEXT,
            executed_at        TEXT,
            expiry             TEXT,
            policy_version     TEXT,
            rollback_payload   TEXT,
            config_data        TEXT,
            reason             TEXT,
            version            INTEGER  NOT NULL DEFAULT 0,
            FOREIGN KEY (device_id) REFERENCES devices(device_id)
        );

        -- ── Policy Table ──────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS policies (
            policy_id          TEXT     PRIMARY KEY,
            policy_version     TEXT     NOT NULL,
            scope              TEXT     NOT NULL,
            target_region      TEXT,
            content            TEXT     NOT NULL,
            distributed_by     TEXT     NOT NULL,
            distributed_at     TEXT,
            valid_from         TEXT,
            valid_until        TEXT,
            is_active          INTEGER  NOT NULL DEFAULT 1,
            version            INTEGER  NOT NULL DEFAULT 0
        );

        -- ── Event Log (Immutable Audit Trail) ────────────────────────────────
        CREATE TABLE IF NOT EXISTS events (
            event_id           TEXT     PRIMARY KEY,
            event_type         TEXT     NOT NULL,
            actor              TEXT     NOT NULL,
            subject            TEXT,
            action             TEXT     NOT NULL,
            decision           TEXT,
            timestamp          TEXT     NOT NULL,
            payload_ref        TEXT,
            notes              TEXT,
            signature          TEXT     NOT NULL,
            details            TEXT     NOT NULL DEFAULT '{}'
        );

        -- Append-only enforcement
        CREATE TRIGGER IF NOT EXISTS prevent_event_update
        BEFORE UPDATE ON events
        BEGIN
            SELECT RAISE(FAIL, 'Event log is immutable — updates not allowed');
        END;

        CREATE TRIGGER IF NOT EXISTS prevent_event_delete
        BEFORE DELETE ON events
        BEGIN
            SELECT RAISE(FAIL, 'Event log is immutable — deletions not allowed');
        END;

        -- ── Controller Sync Table (Locks) ─────────────────────────────────────
        CREATE TABLE IF NOT EXISTS locks (
            lock_id            TEXT     PRIMARY KEY,
            lock_type          TEXT     NOT NULL,
            subject_id         TEXT     NOT NULL,
            held_by            TEXT     NOT NULL,
            acquired_at        TEXT     NOT NULL,
            expires_at         TEXT     NOT NULL,
            associated_request TEXT,
            status             TEXT     NOT NULL DEFAULT 'ACTIVE'
        );

        -- ── Controller Identity Table ─────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS controllers (
            controller_id      TEXT     PRIMARY KEY,
            role               TEXT     NOT NULL,
            region             TEXT,
            status             TEXT     NOT NULL DEFAULT 'validating',
            validated_by       TEXT,
            validated_at       TEXT,
            public_key         TEXT,
            certificate        TEXT,
            capabilities       TEXT     DEFAULT '[]',
            metadata           TEXT     DEFAULT '{}',
            version            INTEGER  NOT NULL DEFAULT 0
        );

        -- ── Indexes ───────────────────────────────────────────────────────────
        CREATE UNIQUE INDEX IF NOT EXISTS idx_devices_mac
            ON devices(mac_address);
        CREATE INDEX IF NOT EXISTS idx_devices_region
            ON devices(region);
        CREATE INDEX IF NOT EXISTS idx_devices_lc
            ON devices(local_controller);
        CREATE INDEX IF NOT EXISTS idx_configs_device
            ON configs(device_id);
        CREATE INDEX IF NOT EXISTS idx_configs_status
            ON configs(status);
        CREATE INDEX IF NOT EXISTS idx_events_type
            ON events(event_type);
        CREATE INDEX IF NOT EXISTS idx_events_actor
            ON events(actor);
        CREATE INDEX IF NOT EXISTS idx_events_timestamp
            ON events(timestamp);
        CREATE INDEX IF NOT EXISTS idx_locks_subject
            ON locks(subject_id, lock_type);
        CREATE INDEX IF NOT EXISTS idx_policies_scope
            ON policies(scope, is_active);
        """
        with self._get_connection() as conn:
            conn.executescript(schema)

    # ── Device Operations ────────────────────────────────────────────────────

    def get_device(self, device_id: str) -> Optional[Device]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM devices WHERE device_id = ?", (device_id,)
            ).fetchone()
            return self._row_to_device(row) if row else None

    def get_device_by_mac(self, mac_address: str) -> Optional[Device]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM devices WHERE mac_address = ?", (mac_address,)
            ).fetchone()
            return self._row_to_device(row) if row else None

    def get_all_devices(self, region: Optional[str] = None) -> List[Device]:
        with self._get_connection() as conn:
            if region:
                rows = conn.execute(
                    "SELECT * FROM devices WHERE region = ?", (region,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM devices").fetchall()
            return [self._row_to_device(r) for r in rows]

    def upsert_device(self, device: Device) -> NIBResult:
        """
        Insert or update device with optimistic locking.

        If the device's MAC already exists and device.version doesn't match
        the stored version, returns NIBResult(success=False, conflict=True).
        Caller must re-read, re-apply, and retry.
        """
        # Validate required fields before touching the database
        missing = [
            f for f in ("mac_address", "ip_address")
            if not getattr(device, f, None)
        ]
        if missing:
            return NIBResult(
                success=False,
                error=f"Device missing required fields: {', '.join(missing)}"
            )

        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            existing = self.get_device_by_mac(device.mac_address)

            if existing:
                cursor = conn.execute(
                    """
                    UPDATE devices SET
                        ip_address = ?, hostname = ?, vendor = ?, device_type = ?,
                        firmware_version = ?, status = ?, last_seen = ?,
                        last_updated = ?, local_controller = ?, region = ?,
                        discovery_method = ?, metadata = ?, version = version + 1
                    WHERE mac_address = ? AND version = ?
                    """,
                    (
                        device.ip_address, device.hostname, device.vendor,
                        device.device_type, device.firmware_version,
                        device.status.value,
                        device.last_seen.isoformat() if device.last_seen else now,
                        now, device.local_controller, device.region,
                        device.discovery_method,
                        json.dumps(device.metadata),
                        device.mac_address, device.version
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
                device.device_id = device.device_id or f"nib-dev-{uuid.uuid4().hex[:8]}"
                device.first_seen = device.first_seen or datetime.now(timezone.utc)
                device.last_seen = device.last_seen or datetime.now(timezone.utc)

                conn.execute(
                    """
                    INSERT INTO devices (
                        device_id, temp_scan_id, ip_address, mac_address, hostname,
                        vendor, device_type, firmware_version, region, local_controller,
                        status, discovery_method, first_seen, last_seen,
                        last_updated, version, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        device.device_id, device.temp_scan_id, device.ip_address,
                        device.mac_address, device.hostname, device.vendor,
                        device.device_type, device.firmware_version,
                        device.region, device.local_controller,
                        device.status.value, device.discovery_method,
                        device.first_seen.isoformat(), device.last_seen.isoformat(),
                        now, 0, json.dumps(device.metadata)
                    )
                )
                return NIBResult(success=True, data=device.device_id)

    def update_device_status(
        self,
        device_id: str,
        status: DeviceStatus,
        version: int
    ) -> NIBResult:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE devices SET status = ?, last_updated = ?, version = version + 1
                WHERE device_id = ? AND version = ?
                """,
                (status.value, now, device_id, version)
            )
            if cursor.rowcount == 0:
                return NIBResult(
                    success=False,
                    error="CONFLICT: Version mismatch or device not found",
                    conflict=True
                )
            return NIBResult(success=True)

    # ── Config Operations ────────────────────────────────────────────────────

    def create_config_proposal(self, config: Config) -> NIBResult:
        """Write a new config proposal. Fails if config_id already exists."""
        missing = [
            f for f in ("config_id", "device_id", "proposed_by")
            if not getattr(config, f, None)
        ]
        if missing:
            return NIBResult(
                success=False,
                error=f"Config missing required fields: {', '.join(missing)}"
            )

        config.proposed_at = config.proposed_at or datetime.now(timezone.utc)

        with self._get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO configs (
                        config_id, device_id, config_hash, category, status,
                        proposed_by, approved_by, execution_token,
                        proposed_at, approved_at, executed_at, expiry,
                        policy_version, rollback_payload, config_data, reason, version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        config.config_id, config.device_id,
                        config.config_hash, config.category.value,
                        config.status.value, config.proposed_by,
                        config.approved_by, config.execution_token,
                        config.proposed_at.isoformat() if config.proposed_at else None,
                        config.approved_at.isoformat() if config.approved_at else None,
                        config.executed_at.isoformat() if config.executed_at else None,
                        config.expiry.isoformat() if config.expiry else None,
                        config.policy_version, config.rollback_payload,
                        config.config_data, config.reason, 0
                    )
                )
            except sqlite3.IntegrityError:
                return NIBResult(
                    success=False,
                    error=f"Config {config.config_id} already exists"
                )
        return NIBResult(success=True, data=config.config_id)

    def update_config_status(
        self,
        config_id: str,
        status: ConfigStatus,
        version: int,
        approver: Optional[str] = None,
        execution_token: Optional[str] = None,
        expiry: Optional[datetime] = None
    ) -> NIBResult:
        now = datetime.now(timezone.utc)
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE configs SET
                    status = ?,
                    approved_by = COALESCE(?, approved_by),
                    execution_token = COALESCE(?, execution_token),
                    approved_at = CASE WHEN ? = 'APPROVED' THEN ? ELSE approved_at END,
                    executed_at = CASE WHEN ? = 'EXECUTED' THEN ? ELSE executed_at END,
                    expiry = COALESCE(?, expiry),
                    version = version + 1
                WHERE config_id = ? AND version = ?
                """,
                (
                    status.value,
                    approver, execution_token,
                    status.value, now.isoformat(),
                    status.value, now.isoformat(),
                    expiry.isoformat() if expiry else None,
                    config_id, version
                )
            )
            if cursor.rowcount == 0:
                return NIBResult(
                    success=False,
                    error="CONFLICT: Version mismatch or config not found",
                    conflict=True
                )
        return NIBResult(success=True)

    def get_config(self, config_id: str) -> Optional[Config]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM configs WHERE config_id = ?", (config_id,)
            ).fetchone()
            return self._row_to_config(row) if row else None

    def get_active_config(self, device_id: str) -> Optional[Config]:
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM configs
                WHERE device_id = ? AND status NOT IN ('DENIED', 'ROLLED_BACK', 'FAILED')
                ORDER BY proposed_at DESC LIMIT 1
                """,
                (device_id,)
            ).fetchone()
            return self._row_to_config(row) if row else None

    # ── Event Log Operations ─────────────────────────────────────────────────

    def write_event(self, event: Event) -> NIBResult:
        """
        Write an immutable event to the audit log.

        The event_type, actor, and action fields are all required.
        Every significant state change in PDSNO must produce an Event.
        """
        missing = [
            f for f in ("event_type", "actor", "action")
            if not getattr(event, f, None)
        ]
        if missing:
            return NIBResult(
                success=False,
                error=f"Event missing required fields: {', '.join(missing)}"
            )

        event_content = (
            f"{event.event_type}{event.actor}"
            f"{event.timestamp.isoformat()}{event.action}"
            f"{json.dumps(event.details, sort_keys=True)}"
        )
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
                INSERT INTO events (
                    event_id, event_type, actor, subject, action,
                    decision, timestamp, payload_ref, notes, signature, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id, event.event_type, event.actor,
                    event.subject, event.action, event.decision,
                    event.timestamp.isoformat(),
                    event.payload_ref, event.notes, signature,
                    json.dumps(event.details)
                )
            )
        return NIBResult(success=True, data=event.event_id)

    # ── Policy Operations ────────────────────────────────────────────────────

    def get_active_policy(
        self,
        scope: str,
        region: Optional[str] = None
    ) -> Optional[Policy]:
        with self._get_connection() as conn:
            if region:
                row = conn.execute(
                    """
                    SELECT * FROM policies
                    WHERE scope = ? AND target_region = ? AND is_active = 1
                    ORDER BY version DESC LIMIT 1
                    """,
                    (scope, region)
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT * FROM policies
                    WHERE scope = ? AND is_active = 1
                    ORDER BY version DESC LIMIT 1
                    """,
                    (scope,)
                ).fetchone()
            return self._row_to_policy(row) if row else None

    def distribute_policy(self, policy: Policy) -> NIBResult:
        missing = [
            f for f in ("policy_id", "policy_version", "scope", "content", "distributed_by")
            if not getattr(policy, f, None)
        ]
        if missing:
            return NIBResult(
                success=False,
                error=f"Policy missing required fields: {', '.join(missing)}"
            )

        policy.distributed_at = policy.distributed_at or datetime.now(timezone.utc)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO policies (
                    policy_id, policy_version, scope, target_region, content,
                    distributed_by, distributed_at, valid_from, valid_until,
                    is_active, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    policy.policy_id, policy.policy_version, policy.scope,
                    policy.target_region, policy.content, policy.distributed_by,
                    policy.distributed_at.isoformat() if policy.distributed_at else None,
                    policy.valid_from.isoformat() if policy.valid_from else None,
                    policy.valid_until.isoformat() if policy.valid_until else None,
                    1 if policy.is_active else 0, policy.version
                )
            )
        return NIBResult(success=True, data=policy.policy_id)

    # ── Lock Operations ──────────────────────────────────────────────────────

    def acquire_lock(
        self,
        subject_id: str,
        lock_type: LockType,
        held_by: str,
        ttl_seconds: int = 300,
        associated_request: Optional[str] = None
    ) -> NIBResult:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)

        with self._get_connection() as conn:
            # Clean up expired locks
            conn.execute(
                "DELETE FROM locks WHERE expires_at < ?", (now.isoformat(),)
            )

            existing = conn.execute(
                "SELECT * FROM locks WHERE subject_id = ? AND lock_type = ?",
                (subject_id, lock_type.value)
            ).fetchone()

            if existing:
                return NIBResult(
                    success=False,
                    error=f"Lock already held by {existing['held_by']}"
                )

            lock_id = f"lock-{uuid.uuid4().hex[:12]}"
            conn.execute(
                """
                INSERT INTO locks (
                    lock_id, lock_type, subject_id, held_by,
                    acquired_at, expires_at, associated_request, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lock_id, lock_type.value, subject_id, held_by,
                    now.isoformat(), expires_at.isoformat(),
                    associated_request, 'ACTIVE'
                )
            )
            return NIBResult(success=True, data=lock_id)

    def release_lock(self, lock_id: str, held_by: str) -> NIBResult:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM locks WHERE lock_id = ? AND held_by = ?",
                (lock_id, held_by)
            )
            if cursor.rowcount == 0:
                return NIBResult(
                    success=False,
                    error="Lock not found or not held by this controller"
                )
            return NIBResult(success=True)

    def check_lock(
        self,
        subject_id: str,
        lock_type: LockType
    ) -> Optional[Lock]:
        now = datetime.now(timezone.utc)
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM locks
                WHERE subject_id = ? AND lock_type = ? AND expires_at > ?
                """,
                (subject_id, lock_type.value, now.isoformat())
            ).fetchone()
            if row:
                return Lock(
                    lock_id=row['lock_id'],
                    lock_type=LockType(row['lock_type']),
                    subject_id=row['subject_id'],
                    held_by=row['held_by'],
                    acquired_at=datetime.fromisoformat(row['acquired_at']),
                    expires_at=datetime.fromisoformat(row['expires_at']),
                    associated_request=row['associated_request']
                )
            return None

    # ── Controller Operations ────────────────────────────────────────────────

    def get_controller(self, controller_id: str) -> Optional[Controller]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM controllers WHERE controller_id = ?",
                (controller_id,)
            ).fetchone()
            return self._row_to_controller(row) if row else None

    def get_controllers_by_region(self, region: str) -> List[Controller]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM controllers WHERE region = ? AND status = 'active'",
                (region,)
            ).fetchall()
            return [self._row_to_controller(r) for r in rows]

    def upsert_controller(self, controller: Controller) -> NIBResult:
        with self._get_connection() as conn:
            existing = self.get_controller(controller.controller_id)

            if existing:
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
                        json.dumps(controller.capabilities),
                        json.dumps(controller.metadata),
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
                controller.validated_at = (
                    controller.validated_at or datetime.now(timezone.utc)
                )
                conn.execute(
                    """
                    INSERT INTO controllers (
                        controller_id, role, region, status, validated_by,
                        validated_at, public_key, certificate, capabilities,
                        metadata, version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        controller.controller_id, controller.role,
                        controller.region, controller.status,
                        controller.validated_by,
                        controller.validated_at.isoformat(),
                        controller.public_key, controller.certificate,
                        json.dumps(controller.capabilities),
                        json.dumps(controller.metadata),
                        controller.version
                    )
                )
                return NIBResult(success=True, data=controller.controller_id)

    # ── Row Converters ───────────────────────────────────────────────────────

    def _row_to_device(self, row: sqlite3.Row) -> Device:
        return Device(
            device_id=row['device_id'],
            temp_scan_id=row['temp_scan_id'],
            ip_address=row['ip_address'],
            mac_address=row['mac_address'],
            hostname=row['hostname'],
            vendor=row['vendor'],
            device_type=row['device_type'],
            firmware_version=row['firmware_version'],
            region=row['region'],
            local_controller=row['local_controller'],
            status=DeviceStatus(row['status']),
            discovery_method=row['discovery_method'],
            first_seen=datetime.fromisoformat(row['first_seen']) if row['first_seen'] else None,
            last_seen=datetime.fromisoformat(row['last_seen']) if row['last_seen'] else None,
            last_updated=datetime.fromisoformat(row['last_updated']) if row['last_updated'] else None,
            version=row['version'],
            metadata=json.loads(row['metadata']) if row['metadata'] else {}
        )

    def _row_to_config(self, row: sqlite3.Row) -> Config:
        return Config(
            config_id=row['config_id'],
            device_id=row['device_id'],
            config_hash=row['config_hash'],
            category=ConfigCategory(row['category']),
            status=ConfigStatus(row['status']),
            proposed_by=row['proposed_by'],
            approved_by=row['approved_by'],
            execution_token=row['execution_token'],
            proposed_at=datetime.fromisoformat(row['proposed_at']) if row['proposed_at'] else None,
            approved_at=datetime.fromisoformat(row['approved_at']) if row['approved_at'] else None,
            executed_at=datetime.fromisoformat(row['executed_at']) if row['executed_at'] else None,
            expiry=datetime.fromisoformat(row['expiry']) if row['expiry'] else None,
            policy_version=row['policy_version'],
            rollback_payload=row['rollback_payload'],
            config_data=row['config_data'],
            reason=row['reason'],
            version=row['version']
        )

    def _row_to_policy(self, row: sqlite3.Row) -> Policy:
        return Policy(
            policy_id=row['policy_id'],
            policy_version=row['policy_version'],
            scope=row['scope'],
            target_region=row['target_region'],
            content=row['content'],
            distributed_by=row['distributed_by'],
            distributed_at=datetime.fromisoformat(row['distributed_at']) if row['distributed_at'] else None,
            valid_from=datetime.fromisoformat(row['valid_from']) if row['valid_from'] else None,
            valid_until=datetime.fromisoformat(row['valid_until']) if row['valid_until'] else None,
            is_active=bool(row['is_active']),
            version=row['version']
        )

    def _row_to_controller(self, row: sqlite3.Row) -> Controller:
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