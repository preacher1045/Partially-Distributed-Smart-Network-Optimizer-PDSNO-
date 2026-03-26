#!/usr/bin/env python3
# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""
Global Controller — Distributed Process

Wraps the existing gc_process.py pattern with environment-variable config
so it works identically on the host and inside a ContainerLab container.

This is a thin wrapper: all the real GC logic lives in
pdsno/controllers/global_controller.py and pdsno/communication/rest_server.py.

Environment variables:
    PDSNO_DB_PATH        Path to the shared SQLite NIB file
    PDSNO_CONTEXT_PATH   Path to GC context YAML
    PDSNO_REST_PORT      Port for GC REST server (default: 8001)
    PDSNO_GC_ID          Controller ID (default: global_cntl_1)

Usage on host:
    PDSNO_DB_PATH=./sim_distributed/pdsno.db python examples/gc_process_distributed.py

Usage in container:
    python /pdsno/examples/gc_process_distributed.py
"""

import os
import sys
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pdsno.controllers.global_controller import GlobalController
from pdsno.controllers.context_manager import ContextManager
from pdsno.datastore import NIBStore
from pdsno.communication.rest_server import ControllerRESTServer
from pdsno.communication.message_format import MessageType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("gc_process")


# ── Config ────────────────────────────────────────────────────────────────────

DB_PATH      = os.environ.get("PDSNO_DB_PATH",      "./sim_distributed/pdsno.db")
CONTEXT_PATH = os.environ.get("PDSNO_CONTEXT_PATH", "./sim_distributed/gc_context.yaml")
REST_PORT    = int(os.environ.get("PDSNO_REST_PORT", "8001"))
GC_ID        = os.environ.get("PDSNO_GC_ID",        "global_cntl_1")


def main():
    logger.info("=" * 60)
    logger.info("PDSNO — Global Controller (distributed mode)")
    logger.info("=" * 60)
    logger.info(f"  GC ID    : {GC_ID}")
    logger.info(f"  REST port: {REST_PORT}")
    logger.info(f"  DB path  : {DB_PATH}")

    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(CONTEXT_PATH).parent.mkdir(parents=True, exist_ok=True)

    context_mgr = ContextManager(CONTEXT_PATH)
    nib_store   = NIBStore(DB_PATH)

    gc = GlobalController(
        controller_id=GC_ID,
        context_manager=context_mgr,
        nib_store=nib_store,
    )

    # REST server — listens for VALIDATION_REQUEST and CHALLENGE_RESPONSE
    # from Regional Controllers attempting to join the network.
    rest_server = ControllerRESTServer(
        controller_id=GC_ID,
        host="0.0.0.0",   # Must bind to 0.0.0.0 inside container (not localhost)
        port=REST_PORT,
    )

    rest_server.register_handler(
        MessageType.VALIDATION_REQUEST,
        gc.handle_validation_request,
    )
    rest_server.register_handler(
        MessageType.CHALLENGE_RESPONSE,
        gc.handle_challenge_response,
    )

    logger.info(f"Starting REST server on 0.0.0.0:{REST_PORT}")
    logger.info("GC is ready. Waiting for Regional Controllers to register.")

    # start_background() is non-blocking; the thread runs until process exits.
    rest_server.start_background()

    # Keep the process alive.
    try:
        while True:
            time.sleep(10)
            logger.debug("GC heartbeat — REST server running")
    except KeyboardInterrupt:
        logger.info("GC shutting down")


if __name__ == "__main__":
    main()