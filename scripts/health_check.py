#!/usr/bin/env python3
"""
PDSNO Health Check

Verify system health and connectivity.

Usage:
    python scripts/health_check.py --url http://localhost:8001
    python scripts/health_check.py --url https://localhost:8001 --cert /path/to/ca.pem
"""

import argparse
import requests
import sys
from datetime import datetime


def check_health(url, timeout=5, verify=True, cert=None):
    """Check /health endpoint"""
    try:
        response = requests.get(
            f"{url}/health",
            timeout=timeout,
            verify=verify if verify else cert
        )
        
        if response.status_code == 200:
            data = response.json()
            return True, data
        else:
            return False, f"HTTP {response.status_code}"
    
    except requests.exceptions.RequestException as e:
        return False, str(e)


def check_metrics(url, timeout=5):
    """Check Prometheus metrics endpoint"""
    try:
        # Metrics on different port
        metrics_url = url.replace(':8001', ':9090') + '/metrics'
        response = requests.get(metrics_url, timeout=timeout)
        
        return response.status_code == 200
    
    except:
        return False


def main():
    parser = argparse.ArgumentParser(description='PDSNO Health Check')
    parser.add_argument('--url', default='http://localhost:8001', help='Controller URL')
    parser.add_argument('--cert', help='CA certificate for TLS verification')
    parser.add_argument('--no-verify', action='store_true', help='Skip TLS verification')
    parser.add_argument('--timeout', type=int, default=5, help='Request timeout in seconds')
    
    args = parser.parse_args()
    
    print("PDSNO Health Check")
    print("=" * 60)
    print(f"URL:     {args.url}")
    print(f"Time:    {datetime.now().isoformat()}")
    print(f"Timeout: {args.timeout}s")
    print("=" * 60)
    
    # Check health endpoint
    print("\n[1/2] Checking health endpoint...")
    healthy, result = check_health(
        args.url,
        timeout=args.timeout,
        verify=not args.no_verify,
        cert=args.cert
    )
    
    if healthy:
        print(f"✓ Controller: {result.get('status')}")
        print(f"✓ Version: {result.get('version', 'unknown')}")
        print(f"✓ Timestamp: {result.get('timestamp')}")
    else:
        print(f"✗ Health check failed: {result}")
        sys.exit(1)
    
    # Check metrics
    print("\n[2/2] Checking metrics endpoint...")
    if check_metrics(args.url, timeout=args.timeout):
        print("✓ Prometheus metrics available")
    else:
        print("⚠ Metrics endpoint not available (non-fatal)")
    
    print("\n" + "=" * 60)
    print("✓ All checks passed!")
    print("=" * 60)
    
    sys.exit(0)


if __name__ == "__main__":
    main()