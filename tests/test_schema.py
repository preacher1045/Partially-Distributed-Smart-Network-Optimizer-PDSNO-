# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""Schema consistency tests for canonical datastore schema."""

import sqlite3
from pathlib import Path

from pdsno.datastore.sqlite_store import NIBStore


REQUIRED_TABLES = {
    "devices",
    "configs",
    "policies",
    "events",
    "locks",
    "controllers",
}


def test_schema_sql_contains_required_tables() -> None:
    schema_path = Path(__file__).resolve().parent.parent / "pdsno" / "datastore" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    for table in REQUIRED_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in schema_sql


def test_nib_store_initializes_required_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "schema_test.db"
    NIBStore(str(db_path))

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    finally:
        conn.close()

    existing_tables = {row[0] for row in rows}
    assert REQUIRED_TABLES.issubset(existing_tables)


def test_legacy_config_records_not_created_by_default(tmp_path: Path) -> None:
    db_path = tmp_path / "schema_test_legacy.db"
    NIBStore(str(db_path))

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='config_records'"
        ).fetchone()
    finally:
        conn.close()

    assert row is None
