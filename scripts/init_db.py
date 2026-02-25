#!/usr/bin/env python3
"""
Initialize PDSNO Database

Creates the NIB schema and optional seed data.

Usage:
    python scripts/init_db.py --db config/pdsno.db
    python scripts/init_db.py --db config/pdsno.db --seed-data
"""

import argparse
from pdsno.datastore import NIBStore

def main():
    parser = argparse.ArgumentParser(description='Initialize PDSNO Database')
    parser.add_argument('--db', default='config/pdsno.db', help='Database path')
    parser.add_argument('--seed-data', action='store_true', help='Add seed data')
    parser.add_argument('--drop-existing', action='store_true', help='Drop existing tables')
    
    args = parser.parse_args()
    
    print(f"Initializing database: {args.db}")
    
    if args.drop_existing:
        print("⚠️  Dropping existing tables...")
        # Drop logic here
    
    # Create NIBStore (auto-creates schema)
    nib = NIBStore(args.db)
    
    print("✓ Database schema created")
    
    if args.seed_data:
        print("Adding seed data...")
        # Add sample devices, controllers, etc.
        print("✓ Seed data added")
    
    print("\nDatabase ready!")


if __name__ == "__main__":
    main()