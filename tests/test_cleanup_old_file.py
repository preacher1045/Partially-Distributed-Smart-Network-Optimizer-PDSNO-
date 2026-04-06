#!/usr/bin/env python3

# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

from __future__ import annotations
 
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
 
import pytest
 
# Make the scripts/ directory importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
 
from cleanup_old_data import ( 
    CleanupConfig,
    CleanupReport,
    TableResult,
    TableSpec,
    _build_where,
    _column_exists,
    _count_stale,
    _delete_stale_batched,
    _process_table,
    _table_exists,
    main,
    run_cleanup,
)
 
 
# ---------------------------------------------------------------------------
# Schema helpers — mirror the real NIB schema exactly
# ---------------------------------------------------------------------------
 
_NIB_SCHEMA = """
PRAGMA foreign_keys = ON;
 
CREATE TABLE IF NOT EXISTS configs (
    config_id       TEXT PRIMARY KEY,
    device_id       TEXT NOT NULL,
    config_hash     TEXT NOT NULL DEFAULT '',
    category        TEXT NOT NULL DEFAULT 'LOW',
    status          TEXT NOT NULL DEFAULT 'PENDING',
    proposed_by     TEXT,
    approved_by     TEXT,
    execution_token TEXT,
    proposed_at     TEXT,
    approved_at     TEXT,
    executed_at     TEXT,
    expiry          TEXT,
    policy_version  TEXT,
    rollback_payload TEXT,
    config_data     TEXT,
    reason          TEXT,
    version         INTEGER NOT NULL DEFAULT 0
);
 
CREATE TABLE IF NOT EXISTS config_records (
    config_id   TEXT PRIMARY KEY,
    device_id   TEXT NOT NULL,
    config_lines TEXT NOT NULL,
    created_by  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    approved_by TEXT,
    approved_at TEXT,
    executed_at TEXT,
    status      TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    version     INTEGER DEFAULT 0
);
 
CREATE TABLE IF NOT EXISTS config_approvals (
    approval_id  TEXT PRIMARY KEY,
    config_id    TEXT NOT NULL,
    approver_id  TEXT NOT NULL,
    approved_at  TEXT NOT NULL,
    decision     TEXT NOT NULL,
    comments     TEXT
);
 
CREATE TABLE IF NOT EXISTS execution_tokens (
    token_id   TEXT PRIMARY KEY,
    config_id  TEXT NOT NULL,
    device_id  TEXT NOT NULL,
    issued_by  TEXT NOT NULL,
    issued_at  TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    signature  TEXT NOT NULL,
    used       INTEGER DEFAULT 0
);
 
CREATE TABLE IF NOT EXISTS backups (
    backup_id       TEXT PRIMARY KEY,
    device_id       TEXT NOT NULL,
    config_id       TEXT,
    config_snapshot TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    created_by      TEXT NOT NULL,
    metadata        TEXT
);
 
CREATE TABLE IF NOT EXISTS events (
    event_id    TEXT PRIMARY KEY,
    event_type  TEXT NOT NULL,
    actor       TEXT NOT NULL,
    subject     TEXT,
    action      TEXT NOT NULL,
    decision    TEXT,
    timestamp   TEXT NOT NULL,
    payload_ref TEXT,
    notes       TEXT,
    signature   TEXT NOT NULL,
    details     TEXT NOT NULL DEFAULT '{}'
);
 
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
 
CREATE TABLE IF NOT EXISTS discovery_reports (
    report_id           TEXT PRIMARY KEY,
    local_controller_id TEXT NOT NULL,
    subnet              TEXT NOT NULL,
    scan_start          TEXT NOT NULL,
    scan_end            TEXT NOT NULL,
    devices_found       INTEGER,
    new_devices         INTEGER,
    metadata            TEXT
);
 
CREATE TABLE IF NOT EXISTS locks (
    lock_id            TEXT PRIMARY KEY,
    lock_type          TEXT NOT NULL,
    subject_id         TEXT NOT NULL,
    held_by            TEXT NOT NULL,
    acquired_at        TEXT NOT NULL,
    expires_at         TEXT NOT NULL,
    associated_request TEXT,
    status             TEXT NOT NULL DEFAULT 'ACTIVE'
);
 
CREATE TABLE IF NOT EXISTS policies (
    policy_id       TEXT PRIMARY KEY,
    policy_version  TEXT NOT NULL,
    scope           TEXT NOT NULL,
    target_region   TEXT,
    content         TEXT NOT NULL,
    distributed_by  TEXT NOT NULL,
    distributed_at  TEXT,
    valid_from      TEXT,
    valid_until     TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    version         INTEGER NOT NULL DEFAULT 0
);
 
CREATE TABLE IF NOT EXISTS devices (
    device_id   TEXT PRIMARY KEY,
    ip_address  TEXT NOT NULL,
    mac_address TEXT UNIQUE NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    first_seen  TEXT,
    last_seen   TEXT
);
 
CREATE TABLE IF NOT EXISTS controllers (
    controller_id TEXT PRIMARY KEY,
    role          TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'validating',
    validated_at  TEXT
);
"""
 
 
def _make_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.executescript(_NIB_SCHEMA)
    conn.commit()
    return conn
 
 
def _ts(age_days: int) -> str:
    """Return an ISO-8601 UTC timestamp for *now - age_days*."""
    return (datetime.now(tz=timezone.utc) - timedelta(days=age_days)).isoformat()
 
 
# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
 
@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "pdsno_test.db"
    conn = _make_db(path)
 
    # configs: 2 stale DENIED (40 days), 1 stale EXECUTED (50 days — must NOT be deleted),
    #          2 recent PENDING (3 days)
    conn.executemany(
        "INSERT INTO configs (config_id, device_id, status, proposed_at) VALUES (?, ?, ?, ?)",
        [
            ("cfg-denied-old-1", "dev-1", "DENIED", _ts(40)),
            ("cfg-denied-old-2", "dev-2", "DENIED", _ts(45)),
            ("cfg-executed-old", "dev-3", "EXECUTED", _ts(50)),  # terminal but not in filter
            ("cfg-pending-new-1", "dev-1", "PENDING", _ts(3)),
            ("cfg-pending-new-2", "dev-2", "PENDING", _ts(1)),
        ],
    )
 
    # config_records: 1 stale FAILED (60 days), 1 recent APPROVED (5 days)
    conn.executemany(
        """INSERT INTO config_records
           (config_id, device_id, config_lines, created_by, created_at, status, sensitivity)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            ("cr-failed-old", "dev-1", "[]", "gc-1", _ts(60), "FAILED", "LOW"),
            ("cr-approved-new", "dev-2", "[]", "gc-1", _ts(5), "APPROVED", "LOW"),
        ],
    )
 
    # execution_tokens: 2 used (old), 1 unused (old — must NOT be deleted), 1 used (recent)
    conn.executemany(
        """INSERT INTO execution_tokens
           (token_id, config_id, device_id, issued_by, issued_at, expires_at, signature, used)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            ("tok-used-old-1", "cfg-denied-old-1", "dev-1", "gc-1", _ts(40), _ts(39), "sig", 1),
            ("tok-used-old-2", "cfg-denied-old-2", "dev-2", "gc-1", _ts(45), _ts(44), "sig", 1),
            ("tok-unused-old", "cfg-pending-new-1", "dev-1", "gc-1", _ts(35), _ts(34), "sig", 0),
            ("tok-used-new", "cfg-pending-new-2", "dev-2", "gc-1", _ts(2), _ts(1), "sig", 1),
        ],
    )
 
    # discovery_reports: 3 old, 1 recent
    conn.executemany(
        """INSERT INTO discovery_reports
           (report_id, local_controller_id, subnet, scan_start, scan_end)
           VALUES (?, ?, ?, ?, ?)""",
        [
            ("rpt-1", "lc-1", "10.0.0.0/24", _ts(35), _ts(35)),
            ("rpt-2", "lc-1", "10.0.1.0/24", _ts(40), _ts(40)),
            ("rpt-3", "lc-2", "10.0.2.0/24", _ts(50), _ts(50)),
            ("rpt-new", "lc-1", "10.0.0.0/24", _ts(2), _ts(2)),
        ],
    )
 
    # locks: 2 expired (old), 1 active (future expiry)
    conn.executemany(
        """INSERT INTO locks
           (lock_id, lock_type, subject_id, held_by, acquired_at, expires_at, status)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            ("lk-exp-1", "DEVICE", "dev-1", "lc-1", _ts(40), _ts(39), "ACTIVE"),
            ("lk-exp-2", "CONFIG", "cfg-1", "lc-2", _ts(35), _ts(34), "ACTIVE"),
            ("lk-active", "DEVICE", "dev-2", "lc-1", _ts(1), _ts(-1), "ACTIVE"),  # expires tomorrow
        ],
    )
 
    # policies: 2 inactive old, 1 active
    conn.executemany(
        """INSERT INTO policies
           (policy_id, policy_version, scope, content, distributed_by, valid_until, is_active)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            ("pol-old-1", "v1", "global", "{}", "gc-1", _ts(40), 0),
            ("pol-old-2", "v2", "global", "{}", "gc-1", _ts(35), 0),
            ("pol-active", "v3", "global", "{}", "gc-1", _ts(-10), 1),  # valid for another 10d
        ],
    )
 
    # events: 2 rows — these must NEVER be deleted
    conn.executemany(
        """INSERT INTO events
           (event_id, event_type, actor, action, timestamp, signature, details)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            ("evt-old", "DEVICE_ADDED", "lc-1", "ADD", _ts(100), "sig", "{}"),
            ("evt-new", "CONFIG_APPROVED", "gc-1", "APPROVE", _ts(1), "sig", "{}"),
        ],
    )
 
    conn.commit()
    conn.close()
    return path
 
 
@pytest.fixture()
def dry_cfg(db_path: Path) -> CleanupConfig:
    return CleanupConfig(db_path=db_path, retention_days=30, dry_run=True)
 
 
@pytest.fixture()
def exec_cfg(db_path: Path) -> CleanupConfig:
    return CleanupConfig(db_path=db_path, retention_days=30, dry_run=False)
 
 
# ---------------------------------------------------------------------------
# Unit tests — SQL helpers
# ---------------------------------------------------------------------------
 
class TestTableExists:
    def test_existing_table(self, db_path: Path) -> None:
        conn = sqlite3.connect(str(db_path))
        assert _table_exists(conn, "configs") is True
        conn.close()
 
    def test_missing_table(self, db_path: Path) -> None:
        conn = sqlite3.connect(str(db_path))
        assert _table_exists(conn, "nonexistent") is False
        conn.close()
 
 
class TestColumnExists:
    def test_existing_column(self, db_path: Path) -> None:
        conn = sqlite3.connect(str(db_path))
        assert _column_exists(conn, "configs", "proposed_at") is True
        conn.close()
 
    def test_missing_column(self, db_path: Path) -> None:
        conn = sqlite3.connect(str(db_path))
        assert _column_exists(conn, "configs", "nonexistent_col") is False
        conn.close()
 
 
class TestBuildWhere:
    def test_no_status_filter(self) -> None:
        spec = TableSpec("t", "ts", None, 0, "")
        where, params = _build_where(spec, datetime(2024, 1, 1, tzinfo=timezone.utc))
        assert where == "ts < ?"
        assert len(params) == 1
 
    def test_with_status_filter(self) -> None:
        spec = TableSpec("t", "ts", "status = 'X'", 0, "")
        where, params = _build_where(spec, datetime(2024, 1, 1, tzinfo=timezone.utc))
        assert "status = 'X'" in where
        assert where.startswith("ts < ?")
 
 
class TestCountStale:
    def test_configs_stale_count(self, db_path: Path) -> None:
        """Only DENIED configs older than 30 days should be counted."""
        conn = sqlite3.connect(str(db_path))
        spec = TableSpec("configs", "proposed_at", "status IN ('DENIED', 'ROLLED_BACK', 'FAILED')", 20, "")
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)
        count = _count_stale(conn, spec, cutoff)
        assert count == 2   # cfg-denied-old-1, cfg-denied-old-2
        conn.close()
 
    def test_executed_configs_excluded(self, db_path: Path) -> None:
        """EXECUTED configs must not be counted — not in the status filter."""
        conn = sqlite3.connect(str(db_path))
        spec = TableSpec("configs", "proposed_at", "status IN ('DENIED', 'ROLLED_BACK', 'FAILED')", 20, "")
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)
        count = _count_stale(conn, spec, cutoff)
        assert count == 2   # EXECUTED row is excluded by status_filter
        conn.close()
 
    def test_unused_tokens_excluded(self, db_path: Path) -> None:
        """Unused tokens (used=0) must not be counted even when old."""
        conn = sqlite3.connect(str(db_path))
        spec = TableSpec("execution_tokens", "issued_at", "used = 1", 10, "")
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)
        count = _count_stale(conn, spec, cutoff)
        assert count == 2   # tok-used-old-1 and tok-used-old-2 only
        conn.close()
 
    def test_zero_when_all_recent(self, db_path: Path) -> None:
        conn = sqlite3.connect(str(db_path))
        spec = TableSpec("discovery_reports", "scan_end", None, 30, "")
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=365)
        count = _count_stale(conn, spec, cutoff)
        assert count == 0
        conn.close()
 
 
# ---------------------------------------------------------------------------
# Unit tests — _process_table
# ---------------------------------------------------------------------------
 
class TestProcessTableSkipCases:
    def test_skips_immutable_events(self, db_path: Path, dry_cfg: CleanupConfig) -> None:
        conn = sqlite3.connect(str(db_path))
        spec = TableSpec("events", "timestamp", None, 99, "audit log")
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=1)
        result = _process_table(conn, spec, dry_cfg, cutoff)
        assert result.skipped is True
        assert "immutable" in result.skip_reason.lower()
        conn.close()
 
    def test_skips_missing_table(self, db_path: Path, dry_cfg: CleanupConfig) -> None:
        conn = sqlite3.connect(str(db_path))
        spec = TableSpec("no_such_table", "created_at", None, 99, "")
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)
        result = _process_table(conn, spec, dry_cfg, cutoff)
        assert result.skipped is True
        conn.close()
 
    def test_skips_missing_column(self, db_path: Path, dry_cfg: CleanupConfig) -> None:
        conn = sqlite3.connect(str(db_path))
        spec = TableSpec("configs", "no_such_col", None, 99, "")
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)
        result = _process_table(conn, spec, dry_cfg, cutoff)
        assert result.skipped is True
        conn.close()
 
 
class TestProcessTableDryRun:
    def test_correct_stale_count_for_configs(self, db_path: Path, dry_cfg: CleanupConfig) -> None:
        conn = sqlite3.connect(str(db_path))
        spec = TableSpec("configs", "proposed_at", "status IN ('DENIED', 'ROLLED_BACK', 'FAILED')", 20, "")
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)
        result = _process_table(conn, spec, dry_cfg, cutoff)
        assert result.stale_count == 2
        assert result.deleted_count == 0
        conn.close()
 
    def test_no_rows_deleted_in_dry_run(self, db_path: Path, dry_cfg: CleanupConfig) -> None:
        conn = sqlite3.connect(str(db_path))
        spec = TableSpec("configs", "proposed_at", "status IN ('DENIED', 'ROLLED_BACK', 'FAILED')", 20, "")
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)
        _process_table(conn, spec, dry_cfg, cutoff)
        remaining = conn.execute("SELECT COUNT(*) FROM configs").fetchone()[0]
        assert remaining == 5   # unchanged
        conn.close()
 
 
class TestProcessTableExecute:
    def test_deletes_only_terminal_configs(self, db_path: Path, exec_cfg: CleanupConfig) -> None:
        conn = sqlite3.connect(str(db_path))
        spec = TableSpec("configs", "proposed_at", "status IN ('DENIED', 'ROLLED_BACK', 'FAILED')", 20, "")
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)
        result = _process_table(conn, spec, exec_cfg, cutoff)
        assert result.deleted_count == 2
        remaining = conn.execute("SELECT COUNT(*) FROM configs").fetchone()[0]
        assert remaining == 3  # EXECUTED + 2 PENDING survive
        conn.close()
 
    def test_executed_configs_survive(self, db_path: Path, exec_cfg: CleanupConfig) -> None:
        conn = sqlite3.connect(str(db_path))
        spec = TableSpec("configs", "proposed_at", "status IN ('DENIED', 'ROLLED_BACK', 'FAILED')", 20, "")
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)
        _process_table(conn, spec, exec_cfg, cutoff)
        row = conn.execute(
            "SELECT config_id FROM configs WHERE status = 'EXECUTED'"
        ).fetchone()
        assert row is not None   # cfg-executed-old must still be present
        conn.close()
 
    def test_unused_tokens_survive(self, db_path: Path, exec_cfg: CleanupConfig) -> None:
        conn = sqlite3.connect(str(db_path))
        spec = TableSpec("execution_tokens", "issued_at", "used = 1", 10, "")
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)
        _process_table(conn, spec, exec_cfg, cutoff)
        row = conn.execute(
            "SELECT token_id FROM execution_tokens WHERE used = 0"
        ).fetchone()
        assert row is not None   # tok-unused-old must survive
        conn.close()
 
 
# ---------------------------------------------------------------------------
# Integration tests — run_cleanup
# ---------------------------------------------------------------------------
 
class TestRunCleanupDryRun:
    def test_returns_report(self, db_path: Path, dry_cfg: CleanupConfig) -> None:
        report = run_cleanup(dry_cfg)
        assert isinstance(report, CleanupReport)
        assert report.dry_run is True
 
    def test_total_deleted_is_zero(self, db_path: Path, dry_cfg: CleanupConfig) -> None:
        report = run_cleanup(dry_cfg)
        assert report.total_deleted == 0
 
    def test_finds_stale_rows(self, db_path: Path, dry_cfg: CleanupConfig) -> None:
        report = run_cleanup(dry_cfg)
        assert report.total_stale > 0
 
    def test_no_data_changed(self, db_path: Path, dry_cfg: CleanupConfig) -> None:
        run_cleanup(dry_cfg)
        conn = sqlite3.connect(str(db_path))
        assert conn.execute("SELECT COUNT(*) FROM configs").fetchone()[0] == 5
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 2
        conn.close()
 
    def test_events_always_skipped(self, db_path: Path, dry_cfg: CleanupConfig) -> None:
        report = run_cleanup(dry_cfg)
        events_result = next((r for r in report.results if r.table == "events"), None)
        assert events_result is None or events_result.skipped
 
 
class TestRunCleanupExecute:
    def test_stale_configs_removed(self, db_path: Path, exec_cfg: CleanupConfig) -> None:
        run_cleanup(exec_cfg)
        conn = sqlite3.connect(str(db_path))
        remaining = conn.execute(
            "SELECT COUNT(*) FROM configs WHERE status IN ('DENIED', 'ROLLED_BACK', 'FAILED')"
        ).fetchone()[0]
        assert remaining == 0
        conn.close()
 
    def test_pending_configs_survive(self, db_path: Path, exec_cfg: CleanupConfig) -> None:
        run_cleanup(exec_cfg)
        conn = sqlite3.connect(str(db_path))
        count = conn.execute(
            "SELECT COUNT(*) FROM configs WHERE status = 'PENDING'"
        ).fetchone()[0]
        assert count == 2
        conn.close()
 
    def test_events_untouched(self, db_path: Path, exec_cfg: CleanupConfig) -> None:
        run_cleanup(exec_cfg)
        conn = sqlite3.connect(str(db_path))
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 2
        conn.close()
 
    def test_expired_locks_removed(self, db_path: Path, exec_cfg: CleanupConfig) -> None:
        run_cleanup(exec_cfg)
        conn = sqlite3.connect(str(db_path))
        remaining = conn.execute("SELECT COUNT(*) FROM locks").fetchone()[0]
        assert remaining == 1   # only lk-active survives
        conn.close()
 
    def test_inactive_policies_removed(self, db_path: Path, exec_cfg: CleanupConfig) -> None:
        run_cleanup(exec_cfg)
        conn = sqlite3.connect(str(db_path))
        remaining = conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
        assert remaining == 1   # pol-active survives
        conn.close()
 
    def test_active_policy_survives(self, db_path: Path, exec_cfg: CleanupConfig) -> None:
        run_cleanup(exec_cfg)
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT policy_id FROM policies WHERE is_active = 1"
        ).fetchone()
        assert row is not None
        conn.close()
 
    def test_used_tokens_removed_unused_survives(self, db_path: Path, exec_cfg: CleanupConfig) -> None:
        run_cleanup(exec_cfg)
        conn = sqlite3.connect(str(db_path))
        used = conn.execute(
            "SELECT COUNT(*) FROM execution_tokens WHERE used = 1 AND issued_at < ?",
            ((datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat(),)
        ).fetchone()[0]
        assert used == 0
        unused = conn.execute(
            "SELECT COUNT(*) FROM execution_tokens WHERE used = 0"
        ).fetchone()[0]
        assert unused == 1
        conn.close()
 
    def test_had_no_errors(self, db_path: Path, exec_cfg: CleanupConfig) -> None:
        report = run_cleanup(exec_cfg)
        assert not report.had_errors
 
    def test_report_counts_match_reality(self, db_path: Path, exec_cfg: CleanupConfig) -> None:
        """total_deleted in the report matches what was actually removed."""
        conn_before = sqlite3.connect(str(db_path))
        before = {
            t: conn_before.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]  # noqa: S608
            for t in ["configs", "config_records", "execution_tokens", "discovery_reports", "locks", "policies"]
        }
        conn_before.close()
 
        report = run_cleanup(exec_cfg)
 
        conn_after = sqlite3.connect(str(db_path))
        after = {
            t: conn_after.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]  # noqa: S608
            for t in before
        }
        conn_after.close()
 
        actual_deleted = sum(before[t] - after[t] for t in before)
        assert report.total_deleted == actual_deleted
 
 
class TestRunCleanupEdgeCases:
    def test_raises_on_missing_db(self, tmp_path: Path) -> None:
        cfg = CleanupConfig(db_path=tmp_path / "ghost.db", retention_days=30)
        with pytest.raises(FileNotFoundError):
            run_cleanup(cfg)
 
    def test_raises_on_unknown_table(self, db_path: Path) -> None:
        cfg = CleanupConfig(db_path=db_path, retention_days=30, tables=["not_a_table"])
        with pytest.raises(ValueError, match="Unrecognised"):
            run_cleanup(cfg)
 
    def test_filtered_to_single_table(self, db_path: Path) -> None:
        cfg = CleanupConfig(
            db_path=db_path, retention_days=30, dry_run=True,
            tables=["discovery_reports"]
        )
        report = run_cleanup(cfg)
        assert len(report.results) == 1
        assert report.results[0].table == "discovery_reports"
        assert report.results[0].stale_count == 3
 
    def test_very_long_retention_finds_nothing(self, db_path: Path) -> None:
        cfg = CleanupConfig(db_path=db_path, retention_days=3650, dry_run=True)
        report = run_cleanup(cfg)
        assert report.total_stale == 0
 
    def test_idempotent_second_run(self, db_path: Path, exec_cfg: CleanupConfig) -> None:
        """Running cleanup twice should leave the same result — zero stale rows."""
        run_cleanup(exec_cfg)
        report2 = run_cleanup(exec_cfg)
        assert report2.total_stale == 0
        assert report2.total_deleted == 0
 
 
# ---------------------------------------------------------------------------
# CLI tests — main()
# ---------------------------------------------------------------------------
 
class TestMainCLI:
    def test_dry_run_exits_0(self, db_path: Path) -> None:
        rc = main(["--db", str(db_path), "--days", "30"])
        assert rc == 0
 
    def test_execute_exits_0(self, db_path: Path) -> None:
        rc = main(["--db", str(db_path), "--days", "30", "--execute"])
        assert rc == 0
 
    def test_missing_db_exits_2(self, tmp_path: Path) -> None:
        rc = main(["--db", str(tmp_path / "missing.db"), "--days", "30"])
        assert rc == 2
 
    def test_invalid_days_exits_nonzero(self, db_path: Path) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--db", str(db_path), "--days", "0"])
        assert exc_info.value.code != 0
 
    def test_unknown_table_exits_2(self, db_path: Path) -> None:
        rc = main(["--db", str(db_path), "--days", "30", "--tables", "not_real"])
        assert rc == 2
 
    def test_table_filter_accepted(self, db_path: Path) -> None:
        rc = main([
            "--db", str(db_path), "--days", "30",
            "--tables", "discovery_reports", "locks",
        ])
        assert rc == 0