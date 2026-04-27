#!/usr/bin/env python3

# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""
Initialize PDSNO Database

Creates the NIB schema with all tables and optional seed data.

Usage:
    # Initialize with default SQLite
    python scripts/init_db.py
    
    # Initialize with custom path
    python scripts/init_db.py --db /opt/pdsno/data/pdsno.db
    
    # Initialize PostgreSQL
    python scripts/init_db.py --db postgresql://user:pass@localhost/pdsno
    
    # Add seed data
    python scripts/init_db.py --seed-data
    
    # Drop and recreate (WARNING: destroys data)
    python scripts/init_db.py --drop-existing --confirm
"""

import argparse
import sys
import sqlite3
import os
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pdsno.datastore import NIBStore
from pdsno.datastore.models import Device, DeviceStatus, Controller


class DatabaseInitializer:
    """Initialize and manage PDSNO database"""
    
    SCHEMA_VERSION = "1.0.0"
    
    def __init__(self, db_path: str):
        """
        Initialize database initializer.
        
        Args:
            db_path: Database connection string or path
        """
        self.db_path = db_path
        self.is_sqlite = not db_path.startswith('postgresql://')

    def _get_nib_secret_key(self) -> bytes:
        secret = os.environ.get("PDSNO_NIB_SECRET_KEY")
        if not secret:
            raise RuntimeError(
                "PDSNO_NIB_SECRET_KEY must be set to initialize NIBStore."
            )
        return secret.encode("utf-8")
    
    def init_schema(self, drop_existing: bool = False):
        """
        Initialize database schema.
        
        Args:
            drop_existing: Drop existing tables first
        """
        print(f"Initializing database: {self.db_path}")
        
        if self.is_sqlite:
            self._init_sqlite_schema(drop_existing)
        else:
            self._init_postgres_schema(drop_existing)
        
        print("✓ Schema initialized")
    
    def _init_sqlite_schema(self, drop_existing: bool):
        """Initialize SQLite schema from canonical datastore/schema.sql."""
        db_file = Path(self.db_path)
        
        # Create directory if needed
        db_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Drop existing if requested
        if drop_existing and db_file.exists():
            print("⚠️  Dropping existing database...")
            db_file.unlink()
        
        schema_path = Path(__file__).resolve().parent.parent / "pdsno" / "datastore" / "schema.sql"
        if not schema_path.exists():
            raise FileNotFoundError(f"Canonical schema file not found: {schema_path}")

        print(f"Creating tables from {schema_path}...")
        schema_sql = schema_path.read_text(encoding="utf-8")

        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(schema_sql)
            conn.commit()
        finally:
            conn.close()

        # Run forward-compat schema alignment logic used by runtime NIBStore.
        NIBStore(self.db_path, secret_key=self._get_nib_secret_key())
    
    def _init_postgres_schema(self, drop_existing: bool):
        """Initialize PostgreSQL schema"""
        print("PostgreSQL initialization not yet implemented")
        print("Please use SQLite for now or manually create PostgreSQL schema")
        sys.exit(1)
    
    def add_seed_data(self):
        """Add sample seed data for testing"""
        print("Adding seed data...")
        
        nib = NIBStore(self.db_path, secret_key=self._get_nib_secret_key())
        
        # Add sample devices
        devices = [
            {
                'device_id': 'switch-core-01',
                'ip_address': '192.168.1.10',
                'mac_address': 'AA:BB:CC:DD:EE:01',
                'hostname': 'core-switch-01',
                'vendor': 'cisco',
                'device_type': 'switch',
                'status': DeviceStatus.ACTIVE,
                'region': 'zone-A',
                'managed_by_lc': 'local_cntl_zone-A_1'
            },
            {
                'device_id': 'switch-core-02',
                'ip_address': '192.168.1.11',
                'mac_address': 'AA:BB:CC:DD:EE:02',
                'hostname': 'core-switch-02',
                'vendor': 'juniper',
                'device_type': 'switch',
                'status': DeviceStatus.ACTIVE,
                'region': 'zone-A',
                'managed_by_lc': 'local_cntl_zone-A_1'
            },
            {
                'device_id': 'router-edge-01',
                'ip_address': '192.168.1.1',
                'mac_address': 'AA:BB:CC:DD:EE:03',
                'hostname': 'edge-router-01',
                'vendor': 'arista',
                'device_type': 'router',
                'status': DeviceStatus.ACTIVE,
                'region': 'zone-A',
                'managed_by_lc': 'local_cntl_zone-A_1'
            }
        ]
        
        for dev_data in devices:
            device = Device(
                device_id=dev_data['device_id'],
                temp_scan_id='',
                ip_address=dev_data['ip_address'],
                mac_address=dev_data['mac_address'],
                hostname=dev_data['hostname'],
                vendor=dev_data['vendor'],
                device_type=dev_data['device_type'],
                status=dev_data['status'],
                first_seen=datetime.now(timezone.utc),
                last_seen=datetime.now(timezone.utc),
                local_controller=dev_data['managed_by_lc'],
                region=dev_data['region'],
                metadata={}
            )
            
            nib.upsert_device(device)
            print(f"  ✓ Added device: {device.device_id}")
        
        # Add sample controllers
        controllers = [
            {
                'controller_id': 'global_cntl_1',
                'role': 'global',
                'region': None,
                'status': 'active'
            },
            {
                'controller_id': 'regional_cntl_zone-A_1',
                'role': 'regional',
                'region': 'zone-A',
                'status': 'active',
                'validated_by': 'global_cntl_1'
            },
            {
                'controller_id': 'local_cntl_zone-A_1',
                'role': 'local',
                'region': 'zone-A',
                'status': 'active',
                'validated_by': 'regional_cntl_zone-A_1'
            }
        ]
        
        for ctrl_data in controllers:
            controller = Controller(
                controller_id=ctrl_data['controller_id'],
                role=ctrl_data['role'],
                region=ctrl_data.get('region'),
                status=ctrl_data['status'],
                validated_by=ctrl_data.get('validated_by'),
                validated_at=datetime.now(timezone.utc) if ctrl_data.get('validated_by') else None,
                public_key='ed25519-pubkey-placeholder',
                certificate=None,
                capabilities=[],
                metadata={}
            )
            
            nib.upsert_controller(controller)
            print(f"  ✓ Added controller: {controller.controller_id}")
        
        print("✓ Seed data added")
    
    def verify_schema(self) -> bool:
        """Verify schema is correctly initialized"""
        print("Verifying schema...")
        
        try:
            nib = NIBStore(self.db_path, secret_key=self._get_nib_secret_key())
            
            # Check tables exist
            required_tables = [
                'devices', 'configs', 'policies', 'events', 'locks', 'controllers'
            ]
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for table in required_tables:
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                )
                if not cursor.fetchone():
                    print(f"  ✗ Table missing: {table}")
                    return False
                print(f"  ✓ Table exists: {table}")
            
            conn.close()
            
            print("✓ Schema verification complete")
            return True
        
        except Exception as e:
            print(f"  ✗ Verification failed: {e}")
            return False
    
    def show_stats(self):
        """Show database statistics"""
        print("\nDatabase Statistics:")
        print("=" * 60)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        tables = [
            'devices', 'controllers', 'configs', 'policies', 'events', 'locks',
            'config_records', 'config_approvals', 'execution_tokens', 'backups', 'discovery_reports'
        ]
        
        for table in tables:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            )
            if not cursor.fetchone():
                continue
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table:25s}: {count:5d} rows")
        
        # Database size
        if Path(self.db_path).exists():
            size_mb = Path(self.db_path).stat().st_size / (1024 * 1024)
            print(f"\n  Database size: {size_mb:.2f} MB")
        
        conn.close()
        print("=" * 60)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Initialize PDSNO Database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--db',
        default='config/pdsno.db',
        help='Database path or connection string (default: config/pdsno.db)'
    )
    
    parser.add_argument(
        '--drop-existing',
        action='store_true',
        help='Drop existing database (WARNING: destroys all data)'
    )
    
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Confirm destructive operations'
    )
    
    parser.add_argument(
        '--seed-data',
        action='store_true',
        help='Add sample seed data for testing'
    )
    
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Only verify schema, do not initialize'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show database statistics'
    )
    
    args = parser.parse_args()
    
    # Safety check for drop-existing
    if args.drop_existing and not args.confirm:
        print("ERROR: --drop-existing requires --confirm flag")
        print("This will permanently delete all data!")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("PDSNO Database Initialization")
    print("=" * 60 + "\n")
    
    # Initialize
    initializer = DatabaseInitializer(args.db)
    
    # Verify only mode
    if args.verify_only:
        if initializer.verify_schema():
            print("\n✓ Database schema is valid")
            sys.exit(0)
        else:
            print("\n✗ Database schema is invalid")
            sys.exit(1)
    
    # Stats only mode
    if args.stats:
        initializer.show_stats()
        sys.exit(0)
    
    # Initialize schema
    try:
        initializer.init_schema(drop_existing=args.drop_existing)
        
        # Add seed data if requested
        if args.seed_data:
            initializer.add_seed_data()
        
        # Verify
        if not initializer.verify_schema():
            print("\n⚠️  Schema verification failed")
            sys.exit(1)
        
        # Show stats
        initializer.show_stats()
        
        print("\n" + "=" * 60)
        print("✓ Database initialization complete!")
        print("=" * 60)
        print(f"\nDatabase: {args.db}")
        print(f"Schema Version: {initializer.SCHEMA_VERSION}")
        print("\nNext steps:")
        print("  1. Start controllers: python -m pdsno.main --role global --enable-rest")
        print("  2. Check database: sqlite3 config/pdsno.db '.tables'")
        print("  3. View data: python scripts/init_db.py --stats")
        print()
    
    except Exception as e:
        print(f"\n✗ Error during initialization: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()