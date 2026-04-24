#!/usr/bin/env python3
# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""Add device credentials to the PDSNO secret store.

This script stores device passwords in the encrypted SecretManager storage.
It intentionally never prints secret values.

By convention, device passwords are stored under:
    device_<device_id>_password

This matches how ConnectionManager retrieves credentials.
"""

from __future__ import annotations

import argparse
import base64
import os
import re
import sys
from getpass import getpass

from pdsno.security.secret_manager import SecretManager, SecretType


_SAFE_ID_RE = re.compile(r"^[0-9A-Za-z_.-]+$")


def _require_safe_id(value: str, field_name: str) -> str:
    if not value or not _SAFE_ID_RE.fullmatch(value):
        raise ValueError(
            f"Invalid {field_name}. Only letters, digits, '_', '-', '.' are allowed."
        )
    return value


def _load_master_key_b64(value: str) -> bytes:
    try:
        key = base64.b64decode(value, validate=True)
    except Exception as e:
        raise ValueError("Master key must be base64-encoded") from e

    if len(key) < 32:
        raise ValueError("Master key must decode to at least 32 bytes")

    return key


def _read_secret_from_args(args: argparse.Namespace) -> str:
    if args.password is not None:
        return args.password

    if args.password_file is not None:
        with open(args.password_file, "r", encoding="utf-8") as f:
            return f.read().strip("\n")

    if args.password_stdin:
        return sys.stdin.read().strip("\n")

    if args.prompt:
        return getpass("Device password (input hidden): ")

    # Default behavior: prompt only if interactive
    if sys.stdin.isatty():
        return getpass("Device password (input hidden): ")

    raise ValueError(
        "No password provided. Use --password, --password-file, --password-stdin, or --prompt."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Store a device password in the PDSNO secret store (encrypted at rest)."
    )

    parser.add_argument(
        "--device-id",
        required=True,
        help="Device identifier (used to build secret id: device_<device_id>_password)",
    )
    parser.add_argument(
        "--username",
        default=None,
        help="Optional device username (stored as metadata; not a secret).",
    )
    parser.add_argument(
        "--protocol",
        default="ssh",
        help="Optional protocol label to store as metadata (default: ssh).",
    )

    password_group = parser.add_mutually_exclusive_group()
    password_group.add_argument(
        "--password",
        default=None,
        help="Device password (discouraged: visible in shell history).",
    )
    password_group.add_argument(
        "--password-file",
        default=None,
        help="Path to a file containing the password.",
    )
    password_group.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read the password from stdin.",
    )
    password_group.add_argument(
        "--prompt",
        action="store_true",
        help="Prompt for the password (input hidden).",
    )

    parser.add_argument(
        "--storage-path",
        default=os.environ.get("PDSNO_SECRETS_PATH", "./secrets"),
        help="Secret store path (default: $PDSNO_SECRETS_PATH or ./secrets).",
    )

    parser.add_argument(
        "--master-key-b64",
        default=os.environ.get("PDSNO_SECRET_MASTER_KEY_B64"),
        help=(
            "Base64 master key for SecretManager encryption "
            "(default: $PDSNO_SECRET_MASTER_KEY_B64). Required unless --allow-generate-master-key."
        ),
    )
    parser.add_argument(
        "--allow-generate-master-key",
        action="store_true",
        help=(
            "Allow generating a new master key if none is provided. "
            "Not recommended for production."
        ),
    )

    parser.add_argument(
        "--secret-id",
        default=None,
        help="Override the secret id. Must be filesystem-safe.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        device_id = _require_safe_id(args.device_id, "device-id")
        secret_id = args.secret_id or f"device_{device_id}_password"
        secret_id = _require_safe_id(secret_id, "secret-id")

        if args.master_key_b64:
            master_key = _load_master_key_b64(args.master_key_b64)
        else:
            if not args.allow_generate_master_key:
                raise ValueError(
                    "Missing master key. Set PDSNO_SECRET_MASTER_KEY_B64 or pass --master-key-b64."
                )
            master_key = None

        password = _read_secret_from_args(args)
        if not password:
            raise ValueError("Empty password is not allowed")

        secret_mgr = SecretManager(master_key=master_key, storage_path=args.storage_path)

        meta = {
            "device_id": device_id,
            "protocol": args.protocol,
        }
        if args.username:
            meta["username"] = args.username

        secret_mgr.store_secret(
            secret_id=secret_id,
            secret_value=password.encode("utf-8"),
            secret_type=SecretType.DEVICE_PASSWORD,
            metadata=meta,
        )

        print(f"Stored device credentials for '{device_id}' as secret '{secret_id}'.")
        return 0

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
