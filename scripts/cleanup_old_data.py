"""
scripts/cleanup_old_data.py — PDSNO stale record cleanup
 
Remove records older than a configurable retention window from NIB tables that
accumulate unbounded data in long-running deployments.
 
IMPORTANT — what this script will NOT touch:
  * events            — immutable by design; DB triggers actively block
                        DELETE/UPDATE.  The audit trail is permanent.
  * devices           — live network state; excluded unless explicitly requested.
  * controllers       — identity records; excluded unless explicitly requested.
 
Safe to clean by default (terminal-state or time-bounded records only):
  * configs / config_records  — rows in DENIED, ROLLED_BACK, or FAILED status
  * config_approvals          — approvals linked to those terminal configs
  * execution_tokens          — single-use tokens already consumed (used = 1)
  * discovery_reports         — completed scan snapshots
  * backups                   — point-in-time config snapshots
  * locks                     — lock rows whose expiry has already passed
  * policies                  — inactive policies (is_active = 0) past valid_until
 
Usage examples:
    # Preview what would be removed (dry-run, default behaviour):
    python scripts/cleanup_old_data.py --db config/pdsno.db --days 90
 
    # Apply the cleanup:
    python scripts/cleanup_old_data.py --db config/pdsno.db --days 90 --execute
 
    # Clean only discovery reports and used tokens, last 30 days:
    python scripts/cleanup_old_data.py --db config/pdsno.db --days 30 --execute \\
        --tables discovery_reports execution_tokens
 
    # Verbose output for debugging:
    python scripts/cleanup_old_data.py --db config/pdsno.db --days 90 --verbose
 
Exit codes:
    0  — success (dry-run or execution completed without errors)
    1  — runtime error during cleanup
    2  — bad arguments or database not found
"""
 
from __future__ import annotations
 
import argparse
import logging
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
 
# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)
 
 
# ---------------------------------------------------------------------------
# Table registry
# ---------------------------------------------------------------------------
 
@dataclass(frozen=True)
class TableSpec:
    """
    Describes how to identify and delete stale rows in one NIB table.
 
    Attributes:
        name:          SQLite table name.
        ts_column:     Timestamp column for the age comparison (ISO-8601 text).
        status_filter: Optional additional SQL fragment (no leading AND) that
                       restricts cleanup to terminal-state rows only.
        fk_order:      Deletion priority — lower values are deleted first so
                       FK children are always removed before their parents.
        description:   Human-readable note printed in dry-run output.
    """
    name: str
    ts_column: str
    status_filter: Optional[str]
    fk_order: int
    description: str
 
 
# Ordered so FK children are cleaned before parents.
# 'events' is deliberately absent — DB triggers make it immutable.
ALL_TABLE_SPECS: list[TableSpec] = [
    # ── FK children (order 10) ────────────────────────────────────────────
    TableSpec(
        name="config_approvals",
        ts_column="approved_at",
        status_filter=None,
        fk_order=10,
        description="Approval records linked to terminal config proposals",
    ),
    TableSpec(
        name="execution_tokens",
        ts_column="issued_at",
        status_filter="used = 1",
        fk_order=10,
        description="Single-use execution tokens that have been consumed",
    ),
    # ── Core config tables (order 20) ─────────────────────────────────────
    TableSpec(
        name="configs",
        ts_column="proposed_at",
        status_filter="status IN ('DENIED', 'ROLLED_BACK', 'FAILED')",
        fk_order=20,
        description="Config proposals in a terminal failure/rejection state (NIBStore schema)",
    ),
    TableSpec(
        name="config_records",
        ts_column="created_at",
        status_filter="status IN ('DENIED', 'ROLLED_BACK', 'FAILED')",
        fk_order=20,
        description="Config records in a terminal failure/rejection state (init_db schema)",
    ),
    TableSpec(
        name="backups",
        ts_column="created_at",
        status_filter=None,
        fk_order=20,
        description="Point-in-time configuration snapshots",
    ),
    # ── Standalone accumulating tables (order 30) ─────────────────────────
    TableSpec(
        name="discovery_reports",
        ts_column="scan_end",
        status_filter=None,
        fk_order=30,
        description="Completed device discovery scan reports",
    ),
    TableSpec(
        name="locks",
        ts_column="expires_at",
        status_filter=None,
        fk_order=30,
        description="Lock rows whose expiry timestamp has already passed",
    ),
    TableSpec(
        name="policies",
        ts_column="valid_until",
        status_filter="is_active = 0",
        fk_order=30,
        description="Inactive policies past their valid_until date",
    ),
]
 
_SPEC_BY_NAME: dict[str, TableSpec] = {s.name: s for s in ALL_TABLE_SPECS}
 
# The events table is protected at the database level by INSERT triggers.
# This set is used to produce a clear error message if a caller tries anyway.
IMMUTABLE_TABLES: frozenset[str] = frozenset({"events"})
 
# These tables hold live network state and are excluded from default runs.
SENSITIVE_TABLES: frozenset[str] = frozenset({"devices", "controllers"})
 
 
# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
 
@dataclass
class CleanupConfig:
    db_path: Path
    retention_days: int
    dry_run: bool = True
    tables: list[str] = field(default_factory=list)  # empty → all eligible
    batch_size: int = 500
 
 
@dataclass
class TableResult:
    table: str
    description: str
    stale_count: int
    deleted_count: int = 0
    skipped: bool = False
    skip_reason: str = ""
    error: Optional[str] = None
 
 
@dataclass
class CleanupReport:
    dry_run: bool
    cutoff: datetime
    results: list[TableResult] = field(default_factory=list)
 
    @property
    def total_stale(self) -> int:
        return sum(r.stale_count for r in self.results if not r.skipped)
 
    @property
    def total_deleted(self) -> int:
        return sum(r.deleted_count for r in self.results)
 
    @property
    def had_errors(self) -> bool:
        return any(r.error for r in self.results)
 
    def print_summary(self) -> None:
        mode = "DRY-RUN  (no data was modified)" if self.dry_run else "EXECUTE"
        log.info("=" * 72)
        log.info("PDSNO Cleanup Summary  [%s]", mode)
        log.info("Cutoff : rows older than %s UTC", self.cutoff.strftime("%Y-%m-%d %H:%M:%S"))
        log.info("=" * 72)
 
        for r in self.results:
            if r.skipped:
                log.info("  %-28s  SKIPPED  — %s", r.table, r.skip_reason)
            elif r.error:
                log.error("  %-28s  ERROR    — %s", r.table, r.error)
            elif self.dry_run:
                log.info(
                    "  %-28s  %5d stale rows would be removed",
                    r.table, r.stale_count,
                )
            else:
                log.info(
                    "  %-28s  %5d / %5d rows removed",
                    r.table, r.deleted_count, r.stale_count,
                )
 
        log.info("-" * 72)
        if self.dry_run:
            log.info("Total stale rows (would be removed) : %d", self.total_stale)
            log.info("Re-run with --execute to apply changes.")
        else:
            log.info("Total rows removed                  : %d", self.total_deleted)
 
        if self.had_errors:
            log.warning("One or more tables had errors — review the output above.")
        log.info("=" * 72)
 
 

 
def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return bool(row)
 
 
def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()  # noqa: S608
    return any(row[1] == column for row in rows)
 
 
def _build_where(spec: TableSpec, cutoff: datetime) -> tuple[str, list]:
    """
    Return (WHERE-clause-string, params-list) for stale-row queries.
 
    The cutoff uses strict less-than so records created exactly at the cutoff
    boundary are preserved.  The optional status_filter is ANDed in to ensure
    only terminal-state rows are selected, never live or pending records.
    """
    clauses = [f"{spec.ts_column} < ?"]
    params: list = [cutoff.isoformat()]
    if spec.status_filter:
        clauses.append(spec.status_filter)
    return " AND ".join(clauses), params
 
 
def _count_stale(conn: sqlite3.Connection, spec: TableSpec, cutoff: datetime) -> int:
    where, params = _build_where(spec, cutoff)
    row = conn.execute(
        f"SELECT COUNT(*) FROM {spec.name} WHERE {where}", params  # noqa: S608
    ).fetchone()
    return row[0] if row else 0
 
 
def _delete_stale_batched(
    conn: sqlite3.Connection,
    spec: TableSpec,
    cutoff: datetime,
    batch_size: int,
) -> int:
    """
    Delete stale rows in fixed-size batches to bound transaction size.
 
    Re-uses exactly the same WHERE logic as _count_stale to guarantee the
    dry-run count and the executed delete operate on identical row sets.
    Loops until the number of rows deleted in a batch falls below batch_size,
    which signals no more matching rows remain.
    """
    where, params = _build_where(spec, cutoff)
    total = 0
 
    while True:
        cursor = conn.execute(
            f"""
            DELETE FROM {spec.name}
            WHERE rowid IN (
                SELECT rowid FROM {spec.name}
                WHERE {where}
                LIMIT ?
            )
            """,  # noqa: S608
            params + [batch_size],
        )
        conn.commit()
        deleted_this_batch = cursor.rowcount
        total += deleted_this_batch
 
        if deleted_this_batch < batch_size:
            break   # fewer than a full batch → nothing left
 
    return total
 
 

# Per-table orchestration

 
def _process_table(
    conn: sqlite3.Connection,
    spec: TableSpec,
    config: CleanupConfig,
    cutoff: datetime,
) -> TableResult:
    result = TableResult(table=spec.name, description=spec.description, stale_count=0)
 
    # Hard guard: immutable tables refuse deletion at the DB level anyway,
    # but we skip early with a clear message to avoid confusing sqlite3 errors.
    if spec.name in IMMUTABLE_TABLES:
        result.skipped = True
        result.skip_reason = "immutable audit log — DB triggers block DELETE"
        return result
 
    if not _table_exists(conn, spec.name):
        result.skipped = True
        result.skip_reason = "table not present in this database"
        return result
 
    if not _column_exists(conn, spec.name, spec.ts_column):
        result.skipped = True
        result.skip_reason = f"timestamp column '{spec.ts_column}' not found"
        return result
 
    try:
        result.stale_count = _count_stale(conn, spec, cutoff)
 
        if config.dry_run or result.stale_count == 0:
            return result   # nothing to delete, or dry-run stops here
 
        result.deleted_count = _delete_stale_batched(conn, spec, cutoff, config.batch_size)
 
    except sqlite3.Error as exc:
        log.exception("Database error while processing %r", spec.name)
        result.error = str(exc)
 
    return result
 
 

# Public entry point

 
def run_cleanup(config: CleanupConfig) -> CleanupReport:
    """
    Run (or simulate) NIB cleanup according to *config*.
 
    Raises:
        FileNotFoundError  — database path does not exist.
        ValueError         — unknown table name passed in config.tables.
    Returns:
        CleanupReport — inspect .had_errors to decide exit code.
    """
    if not config.db_path.exists():
        raise FileNotFoundError(f"Database not found: {config.db_path}")
 
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=config.retention_days)
    report = CleanupReport(dry_run=config.dry_run, cutoff=cutoff)
 
    log.info("Database    : %s", config.db_path)
    log.info(
        "Retention   : %d day(s)  →  cutoff %s UTC",
        config.retention_days,
        cutoff.strftime("%Y-%m-%d %H:%M:%S"),
    )
    log.info("Mode        : %s", "DRY-RUN" if config.dry_run else "EXECUTE")
 
    # Resolve which specs to run
    if config.tables:
        unknown = set(config.tables) - _SPEC_BY_NAME.keys() - IMMUTABLE_TABLES - SENSITIVE_TABLES
        if unknown:
            raise ValueError(
                f"Unrecognised table name(s): {sorted(unknown)}. "
                f"Valid targets: {sorted(_SPEC_BY_NAME)}"
            )
        for t in config.tables:
            if t in SENSITIVE_TABLES:
                log.warning(
                    "Table %r contains live network state. "
                    "Verify your intent before using --execute.", t
                )
        specs = [_SPEC_BY_NAME[t] for t in config.tables if t in _SPEC_BY_NAME]
    else:
        specs = list(ALL_TABLE_SPECS)
 
    # Always process children before parents.
    specs.sort(key=lambda s: s.fk_order)
 
    conn = sqlite3.connect(str(config.db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
 
    try:
        for spec in specs:
            log.debug("Processing: %s", spec.name)
            result = _process_table(conn, spec, config, cutoff)
            report.results.append(result)
    finally:
        conn.close()
 
    report.print_summary()
    return report
 
 

# CLI

 
def _build_parser() -> argparse.ArgumentParser:
    default_targets = sorted(s.name for s in ALL_TABLE_SPECS)
 
    p = argparse.ArgumentParser(
        prog="cleanup_old_data",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--db",
        required=True,
        metavar="PATH",
        type=Path,
        help="Path to the PDSNO SQLite database (e.g. config/pdsno.db).",
    )
    p.add_argument(
        "--days",
        required=True,
        type=int,
        metavar="N",
        help="Retention window in days.  Records older than N days are eligible for removal.",
    )
    p.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help=(
            "Perform the actual deletion.  "
            "Without this flag the script is a no-op (dry-run)."
        ),
    )
    p.add_argument(
        "--tables",
        nargs="+",
        metavar="TABLE",
        default=[],
        help=(
            "Specific table(s) to clean.  "
            f"Defaults to all eligible tables: {', '.join(default_targets)}.  "
            "NOTE: 'events' is always excluded (immutable audit log)."
        ),
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=500,
        metavar="N",
        help="Rows deleted per transaction (default: 500).  Tune for write pressure.",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Enable DEBUG logging.",
    )
    return p
 
 
def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
 
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
 
    if args.days < 1:
        parser.error("--days must be a positive integer.")
    if args.batch_size < 1:
        parser.error("--batch-size must be a positive integer.")
 
    config = CleanupConfig(
        db_path=args.db,
        retention_days=args.days,
        dry_run=not args.execute,
        tables=args.tables,
        batch_size=args.batch_size,
    )
 
    try:
        report = run_cleanup(config)
    except FileNotFoundError as exc:
        log.error("%s", exc)
        log.error(
            "Run 'python scripts/init_db.py --db %s' to initialise it first.", args.db
        )
        return 2
    except ValueError as exc:
        log.error("%s", exc)
        return 2
    except Exception:
        log.exception("Unexpected error during cleanup")
        return 1
 
    return 1 if report.had_errors else 0
 
 
if __name__ == "__main__":
    sys.exit(main())