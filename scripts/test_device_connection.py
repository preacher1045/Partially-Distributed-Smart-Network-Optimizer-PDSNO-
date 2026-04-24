#!/usr/bin/env python3

# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""
PDSNO Device Connection Preflight

Runs a connectivity and authentication check against a target device using
vendor adapters.

Usage:
  python scripts/test_device_connection.py --vendor cisco --platform ios \
    --host 10.0.0.10 --username admin --password-env DEVICE_PASS

  python scripts/test_device_connection.py --vendor frr --platform linux \
    --hostname frr-spine --device-id frr-spine-01

  python scripts/test_device_connection.py --vendor netconf --platform generic \
    --host 10.0.0.20 --username admin --password secret --supports-netconf
"""

import argparse
import os
import sys
import getpass
from typing import Optional

from pdsno.adapters import VendorAdapterFactory
from pdsno.security.secret_manager import SecretManager


def _load_master_key(args) -> Optional[bytes]:
    if args.master_key_env:
        value = os.environ.get(args.master_key_env)
        if value:
            return value.encode("utf-8")
    if args.master_key_file:
        with open(args.master_key_file, "rb") as handle:
            return handle.read()
    return None


def _load_password(args) -> Optional[str]:
    if args.password:
        return args.password
    if args.password_env:
        return os.environ.get(args.password_env)
    return None


def _load_password_from_secret_manager(args) -> Optional[str]:
    if not args.device_id:
        return None
    master_key = _load_master_key(args)
    if not master_key:
        return None

    secret_manager = SecretManager(
        master_key=master_key,
        storage_path=args.secret_dir,
    )
    secret = secret_manager.retrieve_secret(f"device_{args.device_id}_password")
    if not secret:
        return None
    return secret.decode("utf-8")


def _build_device_info(args, password: Optional[str]) -> dict:
    device_info = {
        "vendor": args.vendor,
        "platform": args.platform,
    }

    if args.host:
        device_info["ip"] = args.host
    if args.hostname:
        device_info["hostname"] = args.hostname
    if args.container_name:
        device_info["container_name"] = args.container_name
    if args.username:
        device_info["username"] = args.username
    if password:
        device_info["password"] = password
    if args.port:
        device_info["port"] = args.port
    if args.timeout:
        device_info["timeout"] = args.timeout
    if args.supports_netconf:
        device_info["supports_netconf"] = True

    return device_info


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PDSNO device connection preflight",
    )
    parser.add_argument("--vendor", required=True, help="Device vendor (cisco, juniper, frr, netconf)")
    parser.add_argument("--platform", required=True, help="Platform (ios, junos, linux, generic)")
    parser.add_argument("--host", help="Device IP address")
    parser.add_argument("--hostname", help="Device hostname (used by FRR adapter)")
    parser.add_argument("--container-name", help="FRR container name override")
    parser.add_argument("--port", type=int, help="Port override (default depends on adapter)")
    parser.add_argument("--timeout", type=int, default=15, help="Connection timeout seconds")
    parser.add_argument("--username", help="Device username")
    parser.add_argument("--password", help="Device password (use --password-env if possible)")
    parser.add_argument("--password-env", help="Env var containing device password")
    parser.add_argument("--device-id", help="Device ID used to load secrets")
    parser.add_argument("--secret-dir", default="./secrets", help="Secret store directory")
    parser.add_argument("--master-key-env", help="Env var holding secret manager master key")
    parser.add_argument("--master-key-file", help="Path to secret manager master key")
    parser.add_argument("--supports-netconf", action="store_true", help="Force NETCONF fallback if adapter missing")

    args = parser.parse_args()

    password = _load_password(args)
    if not password:
        password = _load_password_from_secret_manager(args)
    if not password and args.username:
        password = getpass.getpass("Device password: ")

    if args.username and not password:
        print("Missing password for device connection", file=sys.stderr)
        return 2

    device_info = _build_device_info(args, password)

    try:
        adapter = VendorAdapterFactory.create_adapter(device_info)
    except ValueError as exc:
        print(f"Adapter selection failed: {exc}", file=sys.stderr)
        return 2

    print("PDSNO Device Connection Preflight")
    print("=" * 60)
    print(f"Vendor:   {args.vendor}")
    print(f"Platform: {args.platform}")
    if args.device_id:
        print(f"Device ID: {args.device_id}")
    if args.host:
        print(f"Host:     {args.host}")
    if args.hostname:
        print(f"Hostname: {args.hostname}")

    ok = adapter.connect(device_info)
    if not ok:
        print("✗ Connection failed", file=sys.stderr)
        return 1

    print("✓ Connection succeeded")
    adapter.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
