#!/usr/bin/env python3
"""
PDSNO Performance Tuning Script

Analyzes performance and provides optimization recommendations.

Usage:
    python scripts/performance_tuning.py --analyze
    python scripts/performance_tuning.py --optimize
"""

import argparse
import sqlite3
import os
import shutil
from pathlib import Path
import json


class PerformanceTuner:
    """Analyze and optimize PDSNO performance"""
    
    def __init__(self, db_path: str = "config/pdsno.db"):
        self.db_path = db_path
        self.recommendations = []
    
    def analyze(self):
        """Analyze system performance"""
        print("Analyzing PDSNO Performance...")
        print("=" * 60)
        
        self.analyze_database()
        self.analyze_filesystem()
        self.analyze_configuration()
        
        self.print_recommendations()
    
    def analyze_database(self):
        """Analyze database performance"""
        print("\n[1/3] Database Analysis")
        
        if not Path(self.db_path).exists():
            print("  ⚠️  Database not found")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check database size
        db_size_mb = Path(self.db_path).stat().st_size / (1024 * 1024)
        print(f"  Database size: {db_size_mb:.2f} MB")
        
        if db_size_mb > 1000:
            self.recommendations.append({
                'severity': 'warning',
                'component': 'database',
                'issue': 'Large database size',
                'recommendation': 'Consider archiving old data or switching to PostgreSQL'
            })
        
        # Check for missing indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = cursor.fetchall()
        print(f"  Indexes: {len(indexes)}")
        
        if len(indexes) < 10:
            self.recommendations.append({
                'severity': 'critical',
                'component': 'database',
                'issue': 'Missing indexes',
                'recommendation': 'Run: python scripts/init_db.py to create indexes'
            })
        
        # Check for locked tables
        try:
            cursor.execute("SELECT * FROM locks WHERE expires_at < datetime('now')")
            expired_locks = cursor.fetchall()
            
            if expired_locks:
                self.recommendations.append({
                    'severity': 'warning',
                    'component': 'database',
                    'issue': f'{len(expired_locks)} expired locks found',
                    'recommendation': 'Clean up with: DELETE FROM locks WHERE expires_at < datetime("now")'
                })
        except:
            pass
        
        # Check fragmentation
        cursor.execute("PRAGMA page_count")
        page_count = cursor.fetchone()[0]
        cursor.execute("PRAGMA freelist_count")
        freelist_count = cursor.fetchone()[0]
        
        fragmentation = (freelist_count / page_count * 100) if page_count > 0 else 0
        print(f"  Fragmentation: {fragmentation:.2f}%")
        
        if fragmentation > 20:
            self.recommendations.append({
                'severity': 'warning',
                'component': 'database',
                'issue': 'High fragmentation',
                'recommendation': 'Run: sqlite3 pdsno.db "VACUUM"'
            })
        
        conn.close()
    
    def analyze_filesystem(self):
        """Analyze filesystem performance"""
        print("\n[2/3] Filesystem Analysis")
        
        # Check disk space (cross-platform)
        check_path = '/opt/pdsno' if Path('/opt/pdsno').exists() else '.'
        usage = shutil.disk_usage(check_path)
        free_gb = usage.free / (1024**3)
        total_gb = usage.total / (1024**3)
        used_percent = ((total_gb - free_gb) / total_gb) * 100
        
        print(f"  Disk usage: {used_percent:.1f}% ({free_gb:.1f}GB free)")
        
        if used_percent > 80:
            self.recommendations.append({
                'severity': 'critical',
                'component': 'filesystem',
                'issue': 'Low disk space',
                'recommendation': 'Free up disk space or expand storage'
            })
        
        # Check log file sizes
        log_dir = Path('/opt/pdsno/logs' if Path('/opt/pdsno/logs').exists() else 'logs')
        
        if log_dir.exists():
            total_log_size = sum(f.stat().st_size for f in log_dir.glob('*.log'))
            log_size_mb = total_log_size / (1024 * 1024)
            print(f"  Log files: {log_size_mb:.2f} MB")
            
            if log_size_mb > 500:
                self.recommendations.append({
                    'severity': 'warning',
                    'component': 'filesystem',
                    'issue': 'Large log files',
                    'recommendation': 'Configure log rotation or clean old logs'
                })
    
    def analyze_configuration(self):
        """Analyze configuration for performance"""
        print("\n[3/3] Configuration Analysis")
        
        config_file = Path('config/context_runtime.yaml')
        
        if not config_file.exists():
            print("  ⚠️  Configuration file not found")
            return
        
        import yaml
        with open(config_file) as f:
            config = yaml.safe_load(f)
        
        # Check pool size
        pool_size = config.get('database', {}).get('pool_size', 10)
        print(f"  DB pool size: {pool_size}")
        
        if pool_size < 10:
            self.recommendations.append({
                'severity': 'info',
                'component': 'configuration',
                'issue': 'Small database pool',
                'recommendation': 'Increase pool_size to 20+ for better concurrency'
            })
        
        # Check discovery interval
        discovery_interval = config.get('discovery', {}).get('interval_seconds', 300)
        print(f"  Discovery interval: {discovery_interval}s")
        
        if discovery_interval < 60:
            self.recommendations.append({
                'severity': 'warning',
                'component': 'configuration',
                'issue': 'Frequent discovery scans',
                'recommendation': 'Increase interval_seconds to reduce load'
            })
    
    def print_recommendations(self):
        """Print all recommendations"""
        print("\n" + "=" * 60)
        print("Performance Recommendations")
        print("=" * 60)
        
        if not self.recommendations:
            print("✓ No performance issues found")
            return
        
        # Group by severity
        critical = [r for r in self.recommendations if r['severity'] == 'critical']
        warnings = [r for r in self.recommendations if r['severity'] == 'warning']
        info = [r for r in self.recommendations if r['severity'] == 'info']
        
        if critical:
            print("\n🔴 CRITICAL:")
            for rec in critical:
                print(f"  [{rec['component']}] {rec['issue']}")
                print(f"    → {rec['recommendation']}\n")
        
        if warnings:
            print("\n🟡 WARNINGS:")
            for rec in warnings:
                print(f"  [{rec['component']}] {rec['issue']}")
                print(f"    → {rec['recommendation']}\n")
        
        if info:
            print("\nℹ️  INFO:")
            for rec in info:
                print(f"  [{rec['component']}] {rec['issue']}")
                print(f"    → {rec['recommendation']}\n")
    
    def optimize(self):
        """Apply automatic optimizations"""
        print("Applying Performance Optimizations...")
        print("=" * 60)
        
        # Optimize database
        self.optimize_database()
        
        print("\n✓ Optimization complete")
    
    def optimize_database(self):
        """Optimize database"""
        print("\n[1/1] Optimizing database...")
        
        if not Path(self.db_path).exists():
            print("  ⚠️  Database not found")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Vacuum
        print("  Running VACUUM...")
        cursor.execute("VACUUM")
        
        # Analyze
        print("  Running ANALYZE...")
        cursor.execute("ANALYZE")
        
        # Clean expired locks
        print("  Cleaning expired locks...")
        cursor.execute("DELETE FROM locks WHERE expires_at < datetime('now')")
        deleted = cursor.rowcount
        print(f"    Removed {deleted} expired locks")
        
        conn.commit()
        conn.close()
        
        print("  ✓ Database optimized")


def main():
    parser = argparse.ArgumentParser(description='PDSNO Performance Tuning')
    
    parser.add_argument(
        '--analyze',
        action='store_true',
        help='Analyze performance and provide recommendations'
    )
    parser.add_argument(
        '--optimize',
        action='store_true',
        help='Apply automatic optimizations'
    )
    parser.add_argument(
        '--db',
        default='config/pdsno.db',
        help='Database path (default: config/pdsno.db)'
    )
    
    args = parser.parse_args()
    
    if not args.analyze and not args.optimize:
        parser.print_help()
        return
    
    tuner = PerformanceTuner(args.db)
    
    if args.analyze:
        tuner.analyze()
    
    if args.optimize:
        tuner.optimize()


if __name__ == "__main__":
    main()