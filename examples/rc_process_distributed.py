#!/usr/bin/env python3
# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""
Regional Controller — Distributed Process

Wraps the existing rc_process.py pattern with environment-variable config.
On startup the RC validates itself with the GC over HTTP, then starts its
own REST server to accept discovery reports from Local Controllers.

Environment variables:
    PDSNO_DB_PATH        Path to the shared SQLite NIB file
    PDSNO_CONTEXT_PATH   Path to RC context YAML
    PDSNO_GC_URL         GC REST endpoint, e.g. http://172.20.20.5:8001
    PDSNO_GC_ID          GC controller ID (default: global_cntl_1)
    PDSNO_REST_PORT      Port for RC REST server (default: 8002)
    PDSNO_REGION         Region this RC governs (default: zone-A)
    PDSNO_RC_TEMP_ID     Temp ID used during validation (default: temp-rc-zone-a)

Usage on host:
    PDSNO_GC_URL=http://127.0.0.1:8001 python examples/rc_process_distributed.py

Usage in container:
    python /pdsno/examples/rc_process_distributed.py
"""

import os
import sys
import time
import logging
import requests
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pdsno.controllers.regional_controller import RegionalController
from pdsno.controllers.context_manager import ContextManager
from pdsno.datastore import NIBStore
from pdsno.communication.rest_server import ControllerRESTServer
from pdsno.communication.http_client import ControllerHTTPClient
from pdsno.communication.message_format import MessageType
from pdsno.security.message_auth import MessageAuthenticator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("rc_process")


# ── Config ────────────────────────────────────────────────────────────────────

DB_PATH      = os.environ.get("PDSNO_DB_PATH",      "./sim_distributed/pdsno.db")
CONTEXT_PATH = os.environ.get("PDSNO_CONTEXT_PATH", "./sim_distributed/rc_context.yaml")
GC_URL       = os.environ.get("PDSNO_GC_URL",       "http://127.0.0.1:8001")
GC_ID        = os.environ.get("PDSNO_GC_ID",        "global_cntl_1")
REST_PORT    = int(os.environ.get("PDSNO_REST_PORT", "8002"))
REGION       = os.environ.get("PDSNO_REGION",       "zone-A")
TEMP_ID      = os.environ.get("PDSNO_RC_TEMP_ID",   "temp-rc-zone-a")
LC_URL       = os.environ.get("PDSNO_LC_URL",       "http://172.20.20.7:8003")
MSG_SIGNING_SECRET = os.environ.get(
    "PDSNO_MESSAGE_SIGNING_SECRET",
    "pdsno-message-signing-secret-change-in-production",
)


def _derive_message_signing_key(secret: str) -> bytes:
    """Derive a fixed-length key suitable for HMAC signing."""
    return hashlib.sha256(secret.encode("utf-8")).digest()


# ── Startup helpers ───────────────────────────────────────────────────────────

def wait_for_gc(gc_url: str, timeout_seconds: int = 60) -> bool:
    """Poll GC /health until it responds 200 or timeout expires."""
    logger.info(f"Waiting for GC at {gc_url}/health (timeout {timeout_seconds}s)")
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        try:
            resp = requests.get(f"{gc_url}/health", timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"GC is ready (controller_id={data.get('controller_id', '?')})")
                return True
        except requests.exceptions.ConnectionError:
            pass
        except Exception as e:
            logger.debug(f"Health check: {e}")
        time.sleep(3)

    logger.error(f"GC did not become available within {timeout_seconds}s")
    return False


# ── Discovery report handler ──────────────────────────────────────────────────

def handle_discovery_report(envelope):
    """
    Handle an incoming discovery report from a Local Controller.

    The actual device data is already in the shared NIB (written by the LC).
    This handler logs the event and could trigger anomaly detection.
    """
    payload = envelope.payload if hasattr(envelope, "payload") else envelope.get("payload", {})
    lc_id   = payload.get("lc_id", "unknown")
    region  = payload.get("region", "?")
    new_c   = payload.get("new_count", 0)
    upd_c   = payload.get("updated_count", 0)
    ina_c   = payload.get("inactive_count", 0)

    logger.info(
        f"Discovery report from {lc_id} ({region}): "
        f"{new_c} new, {upd_c} updated, {ina_c} inactive"
    )

    # TODO Phase 7: trigger anomaly detection against NIB when counts are high
    # TODO Phase 7: write RC-level audit event to NIB Event Log

    return {"status": "accepted", "rc_id": f"regional_cntl_{region.lower()}_1"}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("PDSNO — Regional Controller (distributed mode)")
    logger.info("=" * 60)
    logger.info(f"  Temp ID  : {TEMP_ID}")
    logger.info(f"  Region   : {REGION}")
    logger.info(f"  GC URL   : {GC_URL}")
    logger.info(f"  LC URL   : {LC_URL}")
    logger.info(f"  REST port: {REST_PORT}")
    logger.info(f"  DB path  : {DB_PATH}")

    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(CONTEXT_PATH).parent.mkdir(parents=True, exist_ok=True)

    # Step 1 — wait for GC to be available
    if not wait_for_gc(GC_URL):
        logger.error("GC never became available — exiting")
        sys.exit(1)

    # Step 2 — initialise infrastructure
    context_mgr = ContextManager(CONTEXT_PATH)
    nib_store   = NIBStore(DB_PATH)

    # RC starts as TEMP_ID and then receives assigned ID from GC.
    authenticator = MessageAuthenticator(
        shared_secret=_derive_message_signing_key(MSG_SIGNING_SECRET),
        controller_id=TEMP_ID,
    )

    http_client = ControllerHTTPClient(authenticator=authenticator)
    http_client.register_controller(GC_ID, GC_URL)

    rc = RegionalController(
        temp_id=TEMP_ID,
        region=REGION,
        context_manager=context_mgr,
        nib_store=nib_store,
        http_client=http_client,
    )

    # Step 3 — validate with the GC over HTTP
    # This runs the full 6-step challenge-response flow.
    logger.info(f"Validating with GC at {GC_URL} ...")
    try:
        success = rc.request_validation(GC_ID, GC_URL)
    except Exception as e:
        logger.error(f"Validation failed with exception: {e}", exc_info=True)
        sys.exit(1)

    if not success:
        logger.error("GC rejected RC validation — exiting")
        sys.exit(1)

    assigned_id = rc.controller_id
    logger.info(f"Validation successful — assigned ID: {assigned_id}")

    # Keep signer identity aligned with dynamically assigned RC identity.
    authenticator.controller_id = assigned_id

    # Register LC endpoint used for execution instruction callbacks.
    if LC_URL:
        http_client.register_controller("local_cntl_zone-a_001", LC_URL)
        logger.info(f"Registered default LC endpoint local_cntl_zone-a_001 -> {LC_URL}")

    # Step 4 — start REST server to receive discovery reports from LCs
    rest_server = ControllerRESTServer(
        controller_id=assigned_id,
        host="0.0.0.0",   # Must be 0.0.0.0 inside container
        port=REST_PORT,
        authenticator=authenticator,
    )

    # Register handler for incoming LC discovery reports
    rest_server.register_handler(
        MessageType.DISCOVERY_REPORT,
        handle_discovery_report,
    )

    def handle_config_proposal(envelope):
        # Ensure sender has a route for RC -> LC execution instruction callbacks.
        sender_id = envelope.sender_id
        if sender_id and sender_id not in http_client.controller_registry and LC_URL:
            http_client.register_controller(sender_id, LC_URL)
            logger.info(f"Dynamically registered LC endpoint {sender_id} -> {LC_URL}")
        return rc.handle_config_proposal(envelope)

    rest_server.register_handler(
        MessageType.CONFIG_PROPOSAL,
        handle_config_proposal,
    )

    rest_server.register_handler(
        MessageType.EXECUTION_RESULT,
        rc.handle_execution_result,
    )

    logger.info(f"Starting REST server on 0.0.0.0:{REST_PORT}")
    logger.info("RC is ready. Waiting for Local Controllers to report.")

    rest_server.start_background()

    # Keep the process alive
    try:
        while True:
            time.sleep(10)
            logger.debug("RC heartbeat — REST server running")
    except KeyboardInterrupt:
        logger.info("RC shutting down")


if __name__ == "__main__":
    main()