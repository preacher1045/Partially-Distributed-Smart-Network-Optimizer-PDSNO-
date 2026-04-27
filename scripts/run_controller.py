#!/usr/bin/env python3

# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""
Legacy controller startup wrapper.

This script is kept for backwards compatibility and delegates controller startup
to the canonical entry point: `python -m pdsno.main`.
"""

from __future__ import annotations

import argparse
import sys

from pdsno.main import main as pdsno_main


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PDSNO controller runner (compatibility wrapper)",
    )
    parser.add_argument("--type", required=True, choices=["global", "regional", "local"])
    parser.add_argument("--id")
    parser.add_argument("--region")
    parser.add_argument("--parent")
    parser.add_argument("--parent-url")
    parser.add_argument("--subnet")
    parser.add_argument("--discovery-interval", type=int, default=300)
    parser.add_argument("--simulate", action="store_true")

    parser.add_argument("--config", default="config/context_runtime.yaml")
    parser.add_argument("--db", default="config/pdsno.db")
    parser.add_argument("--mqtt-broker")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--port", type=int, default=8001)

    parser.add_argument("--no-validation", action="store_true")
    parser.add_argument("--debug", action="store_true")

    # Deprecated and ignored by the canonical CLI.
    parser.add_argument("--enable-tls", action="store_true")
    parser.add_argument("--cert")
    parser.add_argument("--key")
    parser.add_argument("--ca-cert")

    return parser.parse_args()


def _build_main_argv(args: argparse.Namespace) -> list[str]:
    argv = [
        "pdsno.main",
        "--role",
        args.type,
        "--enable-rest",
        "--rest-port",
        str(args.port),
        "--config",
        args.config,
        "--db",
        args.db,
        "--discovery-interval",
        str(args.discovery_interval),
        "--mqtt-port",
        str(args.mqtt_port),
    ]

    if args.id:
        argv.extend(["--id", args.id])
    if args.region:
        argv.extend(["--region", args.region])
    if args.parent:
        argv.extend(["--parent-id", args.parent])
    if args.parent_url:
        argv.extend(["--parent-url", args.parent_url])
    if args.subnet:
        argv.extend(["--subnet", args.subnet])
    if args.simulate:
        argv.append("--simulate")
    if args.mqtt_broker:
        argv.extend(["--mqtt-broker", args.mqtt_broker])
    if args.debug:
        argv.append("--debug")

    # Legacy behavior allowed parent-only validation without parent URL.
    # Keep startup non-breaking by skipping validation in that case.
    if args.no_validation or (
        args.type in {"regional", "local"} and not args.parent_url
    ):
        argv.append("--no-validation")

    return argv


def main() -> None:
    args = _parse_args()

    if args.enable_tls or args.cert or args.key or args.ca_cert:
        print(
            "WARNING: TLS flags on scripts/run_controller.py are deprecated and "
            "ignored. Use python -m pdsno.main with TLS-capable deployment "
            "configuration instead.",
            file=sys.stderr,
        )

    if args.type in {"regional", "local"} and not args.parent_url and not args.no_validation:
        print(
            "INFO: --parent-url not supplied; enabling --no-validation for "
            "compatibility with legacy runner behavior.",
            file=sys.stderr,
        )

    sys.argv = _build_main_argv(args)
    pdsno_main()


if __name__ == "__main__":
    main()
