# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""
PDSNO Main Entry Point

Start Global, Regional, or Local Controller with CLI options.
"""

import argparse
import logging
import os
import signal
import sys
import time
import hashlib
from pathlib import Path
from typing import Optional

from pdsno.logging.logger import configure_logging, get_logger
from pdsno import __version__
from pdsno.controllers.global_controller import GlobalController
from pdsno.controllers.regional_controller import RegionalController
from pdsno.controllers.local_controller import LocalController
from pdsno.controllers.context_manager import ContextManager
from pdsno.datastore import NIBStore
from pdsno.communication.message_bus import MessageBus
from pdsno.communication.http_client import ControllerHTTPClient
from pdsno.security.message_auth import MessageAuthenticator


def _load_nib_secret() -> bytes:
    secret = os.environ.get("PDSNO_NIB_SECRET_KEY")
    if not secret:
        raise RuntimeError(
            "PDSNO_NIB_SECRET_KEY must be set to start the controller."
        )
    return secret.encode("utf-8")


def _build_authenticator(controller_id: str) -> Optional[MessageAuthenticator]:
    secret = os.environ.get("PDSNO_MESSAGE_SIGNING_SECRET")
    if not secret:
        return None
    key = hashlib.sha256(secret.encode("utf-8")).digest()
    return MessageAuthenticator(shared_secret=key, controller_id=controller_id)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PDSNO controller startup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--role", required=True, choices=["global", "regional", "local"])
    parser.add_argument("--id", dest="controller_id", help="Controller ID")
    parser.add_argument("--region", help="Region name")
    parser.add_argument("--parent-id", help="Parent controller ID")
    parser.add_argument("--parent-url", help="Parent controller base URL")
    parser.add_argument("--subnet", help="Subnet CIDR (local controllers)")
    parser.add_argument("--discovery-interval", type=int, default=300)
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--config", default="config/context_runtime.yaml")
    parser.add_argument("--db", default="config/pdsno.db")
    parser.add_argument("--enable-rest", action="store_true")
    parser.add_argument("--rest-port", type=int, default=8001)
    parser.add_argument("--mqtt-broker")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--no-validation", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    log_config = Path("config/logging.yaml")
    if log_config.exists():
        configure_logging(str(log_config))
    else:
        logging.basicConfig(level=logging.INFO)

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    logger = get_logger(__name__, controller_id="system")
    logger.info("Starting PDSNO v%s", __version__)

    if args.role in {"regional", "local"} and not args.region:
        raise SystemExit("--region is required for regional/local controllers")
    if args.role == "local" and not args.subnet:
        raise SystemExit("--subnet is required for local controllers")

    context_mgr = ContextManager(args.config)
    nib_store = NIBStore(args.db, secret_key=_load_nib_secret())
    message_bus = MessageBus()

    controller = None

    if args.role == "global":
        controller_id = args.controller_id or "global_cntl_1"
        controller = GlobalController(
            controller_id=controller_id,
            context_manager=context_mgr,
            nib_store=nib_store,
            enable_rest=args.enable_rest,
            rest_port=args.rest_port,
        )
        if args.enable_rest:
            controller.start_rest_server_background()

    elif args.role == "regional":
        controller_id = args.controller_id or f"temp-rc-{args.region}"
        http_client = None
        if args.parent_url:
            authenticator = _build_authenticator(controller_id)
            http_client = ControllerHTTPClient(authenticator=authenticator)
            http_client.register_controller(args.parent_id or "global_cntl_1", args.parent_url)

        controller = RegionalController(
            temp_id=controller_id,
            region=args.region,
            context_manager=context_mgr,
            nib_store=nib_store,
            message_bus=message_bus,
            http_client=http_client,
            enable_rest=args.enable_rest,
            rest_port=args.rest_port,
            mqtt_broker=args.mqtt_broker,
            mqtt_port=args.mqtt_port,
        )

        if args.enable_rest:
            controller.start_rest_server_background()

        if not args.no_validation:
            if not args.parent_url:
                raise SystemExit("--parent-url is required for validation")
            parent_id = args.parent_id or "global_cntl_1"
            controller.request_validation(parent_id, args.parent_url)
            if not controller.validated:
                raise SystemExit("Validation failed")
            controller.update_rest_server_id()

    elif args.role == "local":
        controller_id = args.controller_id or f"local_cntl_{args.region}_1"
        http_client = None
        if args.parent_url:
            authenticator = _build_authenticator(controller_id)
            http_client = ControllerHTTPClient(authenticator=authenticator)
            http_client.register_controller(args.parent_id or "regional_cntl_zone-A_1", args.parent_url)

        controller = LocalController(
            controller_id=controller_id,
            region=args.region,
            subnet=args.subnet,
            context_manager=context_mgr,
            nib_store=nib_store,
            message_bus=message_bus,
            http_client=http_client,
            simulate=args.simulate,
            mqtt_broker=args.mqtt_broker,
            mqtt_port=args.mqtt_port,
        )

    if controller is None:
        raise SystemExit("Controller could not be initialized")

    stop = False

    def _handle_signal(signum, frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info("Controller %s ready (%s)", controller.controller_id, args.role)

    if args.role == "local":
        while not stop:
            controller.run_discovery_cycle(regional_controller_id=args.parent_id)
            time.sleep(args.discovery_interval)
    else:
        while not stop:
            time.sleep(1)


if __name__ == "__main__":
    main()
