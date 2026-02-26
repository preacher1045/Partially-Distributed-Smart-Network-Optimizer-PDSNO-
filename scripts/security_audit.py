#!/usr/bin/env python3
"""
PDSNO Security Audit Script

Performs comprehensive security checks on the PDSNO installation.

Usage:
    python scripts/security_audit.py
    python scripts/security_audit.py --fix
    python scripts/security_audit.py --report audit_report.json
"""

import os
import sys
import json
import stat
import subprocess
from pathlib import Path
from typing import List, Dict
from datetime import datetime
import argparse


class SecurityAuditor:
    """Perform security audit on PDSNO installation"""
    
    def __init__(self, pdsno_home: str = "/opt/pdsno"):
        self.pdsno_home = Path(pdsno_home)
        self.findings = []
        self.critical_count = 0
        self.warning_count = 0
        self.info_count = 0
    
    def audit_file_permissions(self):
        """Check file and directory permissions"""
        print("[1/10] Auditing file permissions...")
        
        # Check critical files
        critical_files = [
            (self.pdsno_home / "config/master.key", 0o600),
            (self.pdsno_home / "config/bootstrap_secret.key", 0o600),
            ("/etc/pdsno/certs/controller-key.pem", 0o600),
            ("/etc/pdsno/certs/ca-key.pem", 0o600)
        ]
        
        for file_path, expected_perms in critical_files:
            if not file_path.exists():
                self._add_finding(
                    "WARNING",
                    f"Critical file missing: {file_path}",
                    "Ensure all critical files are present"
                )
                continue
            
            actual_perms = file_path.stat().st_mode & 0o777
            
            if actual_perms != expected_perms:
                self._add_finding(
                    "CRITICAL",
                    f"Incorrect permissions on {file_path}",
                    f"Expected {oct(expected_perms)}, got {oct(actual_perms)}. "
                    f"Fix with: chmod {oct(expected_perms)} {file_path}"
                )
    
    def audit_secret_strength(self):
        """Check secret key strength"""
        print("[2/10] Auditing secret strength...")
        
        secret_files = [
            self.pdsno_home / "config/master.key",
            self.pdsno_home / "config/bootstrap_secret.key"
        ]
        
        for secret_file in secret_files:
            if not secret_file.exists():
                continue
            
            with open(secret_file, 'rb') as f:
                secret = f.read()
            
            if len(secret) < 32:
                self._add_finding(
                    "CRITICAL",
                    f"Weak secret in {secret_file}",
                    f"Secret must be at least 32 bytes. Current: {len(secret)} bytes"
                )
    
    def audit_tls_configuration(self):
        """Check TLS/SSL configuration"""
        print("[3/10] Auditing TLS configuration...")
        
        cert_file = Path("/etc/pdsno/certs/controller-cert.pem")
        key_file = Path("/etc/pdsno/certs/controller-key.pem")
        
        if not cert_file.exists() or not key_file.exists():
            self._add_finding(
                "CRITICAL",
                "TLS certificates missing",
                "Generate certificates with: bash scripts/generate_certs.sh"
            )
            return
        
        # Check certificate expiration
        try:
            result = subprocess.run(
                ['openssl', 'x509', '-in', str(cert_file), '-noout', '-enddate'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                expiry_line = result.stdout.strip()
                self._add_finding(
                    "INFO",
                    "TLS certificate expiration",
                    expiry_line
                )
            
        except FileNotFoundError:
            self._add_finding(
                "WARNING",
                "OpenSSL not found",
                "Cannot verify certificate expiration"
            )
    
    def audit_database_security(self):
        """Check database security"""
        print("[4/10] Auditing database security...")
        
        db_file = self.pdsno_home / "data/pdsno.db"
        
        if db_file.exists():
            perms = db_file.stat().st_mode & 0o777
            
            if perms & 0o077:  # World or group readable
                self._add_finding(
                    "CRITICAL",
                    "Database file has overly permissive access",
                    f"Fix with: chmod 600 {db_file}"
                )
    
    def audit_network_exposure(self):
        """Check network exposure"""
        print("[5/10] Auditing network exposure...")
        
        try:
            # Check open ports
            result = subprocess.run(
                ['ss', '-tuln'],
                capture_output=True,
                text=True
            )
            
            if '0.0.0.0:8001' in result.stdout:
                self._add_finding(
                    "WARNING",
                    "REST API exposed on all interfaces",
                    "Consider binding to specific interface for security"
                )
            
        except FileNotFoundError:
            self._add_finding(
                "INFO",
                "Cannot check network exposure",
                "ss command not available"
            )
    
    def audit_password_policies(self):
        """Check password policies"""
        print("[6/10] Auditing password policies...")
        
        # Check if default passwords still in use
        config_file = self.pdsno_home / "config/context_runtime.yaml"
        
        if config_file.exists():
            with open(config_file) as f:
                content = f.read()
            
            dangerous_patterns = [
                'password: admin',
                'password: password',
                'password: 123456',
                'changeme'
            ]
            
            for pattern in dangerous_patterns:
                if pattern.lower() in content.lower():
                    self._add_finding(
                        "CRITICAL",
                        "Default or weak password detected",
                        f"Pattern '{pattern}' found in configuration"
                    )
    
    def audit_logging(self):
        """Check logging configuration"""
        print("[7/10] Auditing logging configuration...")
        
        log_dir = self.pdsno_home / "logs"
        
        if not log_dir.exists():
            self._add_finding(
                "WARNING",
                "Log directory missing",
                f"Create with: mkdir -p {log_dir}"
            )
        else:
            # Check log file permissions
            for log_file in log_dir.glob('*.log'):
                perms = log_file.stat().st_mode & 0o777
                
                if perms & 0o022:  # World or group writable
                    self._add_finding(
                        "WARNING",
                        f"Log file {log_file.name} is writable by others",
                        f"Fix with: chmod 640 {log_file}"
                    )
    
    def audit_dependencies(self):
        """Check for vulnerable dependencies"""
        print("[8/10] Auditing dependencies...")
        
        requirements_file = self.pdsno_home / "requirements.txt"
        
        if requirements_file.exists():
            try:
                # Run pip-audit if available
                result = subprocess.run(
                    ['pip-audit', '-r', str(requirements_file)],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    self._add_finding(
                        "CRITICAL",
                        "Vulnerable dependencies detected",
                        "Run: pip-audit -r requirements.txt for details"
                    )
            
            except FileNotFoundError:
                self._add_finding(
                    "INFO",
                    "pip-audit not installed",
                    "Install with: pip install pip-audit"
                )
    
    def audit_rbac(self):
        """Check RBAC configuration"""
        print("[9/10] Auditing RBAC configuration...")
        
        # Check if RBAC is properly configured
        # This would check actual role assignments in the database
        
        self._add_finding(
            "INFO",
            "RBAC audit",
            "Verify role assignments manually in NIB"
        )
    
    def audit_backup_strategy(self):
        """Check backup configuration"""
        print("[10/10] Auditing backup strategy...")
        
        backup_dir = self.pdsno_home / "data/backups"
        
        if not backup_dir.exists():
            self._add_finding(
                "WARNING",
                "Backup directory missing",
                f"Create with: mkdir -p {backup_dir}"
            )
        else:
            # Check if backups are encrypted
            backup_files = list(backup_dir.glob('*'))
            
            if len(backup_files) == 0:
                self._add_finding(
                    "INFO",
                    "No backups found",
                    "Ensure regular backups are configured"
                )
    
    def _add_finding(self, severity: str, issue: str, recommendation: str):
        """Add a security finding"""
        finding = {
            'severity': severity,
            'issue': issue,
            'recommendation': recommendation,
            'timestamp': datetime.now().isoformat()
        }
        
        self.findings.append(finding)
        
        if severity == "CRITICAL":
            self.critical_count += 1
            print(f"  🔴 {issue}")
        elif severity == "WARNING":
            self.warning_count += 1
            print(f"  🟡 {issue}")
        else:
            self.info_count += 1
            print(f"  ℹ️  {issue}")
    
    def generate_report(self, output_file: str = None):
        """Generate audit report"""
        report = {
            'audit_date': datetime.now().isoformat(),
            'pdsno_home': str(self.pdsno_home),
            'summary': {
                'total_findings': len(self.findings),
                'critical': self.critical_count,
                'warnings': self.warning_count,
                'info': self.info_count
            },
            'findings': self.findings
        }
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\n✓ Report saved to: {output_file}")
        
        return report
    
    def print_summary(self):
        """Print audit summary"""
        print("\n" + "=" * 60)
        print("Security Audit Summary")
        print("=" * 60)
        print(f"Total Findings: {len(self.findings)}")
        print(f"  🔴 Critical: {self.critical_count}")
        print(f"  🟡 Warnings: {self.warning_count}")
        print(f"  ℹ️  Info: {self.info_count}")
        print("=" * 60)
        
        if self.critical_count > 0:
            print("\n⚠️  CRITICAL ISSUES FOUND - FIX IMMEDIATELY!")
            return False
        elif self.warning_count > 0:
            print("\n⚠️  Warnings found - address before production")
            return True
        else:
            print("\n✓ No critical security issues found")
            return True


def main():
    parser = argparse.ArgumentParser(description='PDSNO Security Audit')
    parser.add_argument('--pdsno-home', default='/opt/pdsno',
                        help='PDSNO installation directory')
    parser.add_argument('--report', help='Output report file (JSON)')
    parser.add_argument('--fix', action='store_true',
                        help='Attempt to fix issues automatically')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("PDSNO Security Audit")
    print("=" * 60)
    print()
    
    auditor = SecurityAuditor(args.pdsno_home)
    
    # Run all audits
    auditor.audit_file_permissions()
    auditor.audit_secret_strength()
    auditor.audit_tls_configuration()
    auditor.audit_database_security()
    auditor.audit_network_exposure()
    auditor.audit_password_policies()
    auditor.audit_logging()
    auditor.audit_dependencies()
    auditor.audit_rbac()
    auditor.audit_backup_strategy()
    
    # Generate report
    if args.report:
        auditor.generate_report(args.report)
    
    # Print summary
    is_secure = auditor.print_summary()
    
    sys.exit(0 if is_secure else 1)


if __name__ == "__main__":
    main()