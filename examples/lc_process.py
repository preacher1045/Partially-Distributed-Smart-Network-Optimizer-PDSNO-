#!/usr/bin/env python3
# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""
Local Controller — Distributed Process

Standalone startup script for the Local Controller.
Reads config from environment variables so it works identically
on the host and inside a ContainerLab container.

Environment variables:
    PDSNO_DB_PATH            Path to the shared SQLite NIB file
    PDSNO_CONTEXT_PATH       Path to this controller's context YAML
    PDSNO_SUBNET             Subnet to scan, e.g. 172.20.20.0/24
    PDSNO_REGION             Region name, e.g. zone-A
    PDSNO_LC_ID              Controller ID
    PDSNO_RC_URL             RC REST endpoint, e.g. http://172.20.20.6:8002
    PDSNO_RC_ID              RC controller ID
    PDSNO_DISCOVERY_INTERVAL Seconds between discovery cycles (default: 30)

Usage on host:
    PDSNO_SUBNET=172.20.20.0/24 PDSNO_RC_URL=http://172.20.20.6:8002 \\
    python examples/lc_process.py

Usage in container (env set in topology YAML):
    python /pdsno/examples/lc_process.py
"""

import os
import sys
import time
import logging
import requests
import hashlib
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pdsno.controllers.local_controller import LocalController
from pdsno.controllers.context_manager import ContextManager
from pdsno.datastore import NIBStore
from pdsno.communication.message_format import MessageType
from pdsno.communication.rest_server import ControllerRESTServer
from pdsno.security.message_auth import MessageAuthenticator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("lc_process")


# ── Config ────────────────────────────────────────────────────────────────────

DB_PATH      = os.environ.get("PDSNO_DB_PATH",      "./sim_distributed/pdsno.db")
CONTEXT_PATH = os.environ.get("PDSNO_CONTEXT_PATH", "./sim_distributed/lc_context.yaml")
SUBNET       = os.environ.get("PDSNO_SUBNET",       "172.20.20.0/24")
REGION       = os.environ.get("PDSNO_REGION",       "zone-A")
LC_ID        = os.environ.get("PDSNO_LC_ID",        "local_cntl_zone-a_001")
RC_URL       = os.environ.get("PDSNO_RC_URL",       "http://127.0.0.1:8002")
RC_ID        = os.environ.get("PDSNO_RC_ID",        "regional_cntl_zone-A_1")
DISCOVERY_INTERVAL = int(os.environ.get("PDSNO_DISCOVERY_INTERVAL", "30"))
LC_REST_PORT = int(os.environ.get("PDSNO_LC_REST_PORT", "8003"))
MSG_SIGNING_SECRET = os.environ.get(
    "PDSNO_MESSAGE_SIGNING_SECRET",
    "pdsno-message-signing-secret-change-in-production",
)

AUTHENTICATOR = None


def _derive_message_signing_key(secret: str) -> bytes:
    """Derive a fixed-length key suitable for HMAC signing."""
    return hashlib.sha256(secret.encode("utf-8")).digest()


# ── HTTP report sender ────────────────────────────────────────────────────────

def http_send_discovery_report(rc_url: str, lc_id: str, region: str,
                                subnet: str, recipient_id: str,
                                new_count: int, updated_count: int,
                                inactive_count: int) -> bool:
    """
    POST a discovery report notification to the RC REST server.

    The LC's _send_discovery_report() only supports message_bus/MQTT.
    For distributed mode we call RC's REST endpoint directly.

    We send counts rather than full device lists because the actual device
    data is already written to the shared NIB — RC can query it directly.
    This is the delta-notification pattern from the architecture spec.
    """
    if new_count == 0 and updated_count == 0 and inactive_count == 0:
        return True  # Nothing changed — not an error

    payload = {
        "message_id": f"{lc_id}-{int(time.time())}",
        "message_type": MessageType.DISCOVERY_REPORT.value,
        "sender_id": lc_id,
        "recipient_id": recipient_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "lc_id": lc_id,
            "subnet": subnet,
            "region": region,
            "new_count": new_count,
            "updated_count": updated_count,
            "inactive_count": inactive_count,
        },
    }

    if AUTHENTICATOR:
        payload = AUTHENTICATOR.sign_message(payload)

    try:
        resp = requests.post(
            f"{rc_url}/message/discovery_report",
            json=payload,
            timeout=10,
        )

        if resp.status_code == 400 and "recipient" in resp.text.lower():
            refreshed_rc_id = resolve_rc_id(rc_url, recipient_id)
            if refreshed_rc_id != recipient_id:
                payload["recipient_id"] = refreshed_rc_id
                resp = requests.post(
                    f"{rc_url}/message/discovery_report",
                    json=payload,
                    timeout=10,
                )

        if resp.status_code == 200:
            logger.info(
                f"RC accepted discovery report: "
                f"{new_count} new, {updated_count} updated, {inactive_count} inactive"
            )
            return True
        else:
            logger.warning(f"RC returned HTTP {resp.status_code}: {resp.text[:200]}")
            return False
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Cannot reach RC at {rc_url}: {e}")
        return False
    except Exception as e:
        logger.error(f"Discovery report failed: {e}")
        return False


# ── Startup ───────────────────────────────────────────────────────────────────

def wait_for_rc(rc_url: str, timeout_seconds: int = 120) -> bool:
    """
    Poll RC /health until it responds 200 or the timeout expires.

    The RC validates with the GC first (a few seconds of challenge-response).
    We wait for that to complete so the RC is actually ready to handle
    discovery reports before we start sending them.
    """
    logger.info(f"Waiting for RC at {rc_url}/health (timeout {timeout_seconds}s)")
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        try:
            resp = requests.get(f"{rc_url}/health", timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                cid = data.get("controller_id", "?")
                logger.info(f"RC is ready (controller_id={cid})")
                return True
        except requests.exceptions.ConnectionError:
            pass
        except Exception as e:
            logger.debug(f"Health check: {e}")
        time.sleep(3)

    logger.error(f"RC did not become available within {timeout_seconds}s")
    return False


def resolve_rc_id(rc_url: str, fallback_rc_id: str) -> str:
    """Fetch RC controller_id from /health with fallback to configured ID."""
    try:
        resp = requests.get(f"{rc_url}/health", timeout=3)
        if resp.status_code == 200:
            cid = resp.json().get("controller_id")
            if cid:
                return cid
    except Exception:
        pass
    return fallback_rc_id


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("PDSNO — Local Controller (distributed mode)")
    logger.info("=" * 60)
    logger.info(f"  LC ID    : {LC_ID}")
    logger.info(f"  Subnet   : {SUBNET}")
    logger.info(f"  Region   : {REGION}")
    logger.info(f"  RC URL   : {RC_URL}")
    logger.info(f"  REST port: {LC_REST_PORT}")
    logger.info(f"  DB path  : {DB_PATH}")
    logger.info(f"  Interval : {DISCOVERY_INTERVAL}s")

    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(CONTEXT_PATH).parent.mkdir(parents=True, exist_ok=True)

    # Wait for RC before starting.
    # If LC sends reports before RC is listening, they are silently dropped.
    if not wait_for_rc(RC_URL):
        logger.error("RC never became available — exiting")
        sys.exit(1)

    current_rc_id = resolve_rc_id(RC_URL, RC_ID)

    # Initialise
    context_mgr = ContextManager(CONTEXT_PATH)
    nib_store   = NIBStore(DB_PATH)

    global AUTHENTICATOR
    AUTHENTICATOR = MessageAuthenticator(
        shared_secret=_derive_message_signing_key(MSG_SIGNING_SECRET),
        controller_id=LC_ID,
    )

    # message_bus=None — we handle discovery reporting ourselves over HTTP
    lc = LocalController(
        controller_id=LC_ID,
        region=REGION,
        subnet=SUBNET,
        context_manager=context_mgr,
        nib_store=nib_store,
        message_bus=None,
    )

    # Expose LC REST endpoint for RC execution instructions.
    rest_server = ControllerRESTServer(
        controller_id=LC_ID,
        host="0.0.0.0",
        port=LC_REST_PORT,
        authenticator=AUTHENTICATOR,
    )
    rest_server.register_handler(
        MessageType.EXECUTION_INSTRUCTION,
        lc.handle_execution_instruction,
    )
    rest_server.start_background()
    logger.info(f"LC execution endpoint available at 0.0.0.0:{LC_REST_PORT}")

    logger.info(f"LC {LC_ID} ready. Starting discovery loop.")

    cycle = 0
    try:
        while True:
            cycle += 1
            logger.info(f"--- Discovery cycle {cycle} ---")

            try:
                # run_discovery_cycle writes devices to the shared NIB.
                # We pass regional_controller_id=None because we handle
                # the HTTP report ourselves below.
                result = lc.run_discovery_cycle(regional_controller_id=None)

                new_count      = result.get("new_devices", 0)
                updated_count  = result.get("updated_devices", 0)
                inactive_count = result.get("inactive_devices", 0)
                found          = result.get("devices_found", 0)
                duration       = result.get("cycle_duration_seconds", 0)

                logger.info(
                    f"Cycle {cycle}: {found} devices "
                    f"({new_count} new, {updated_count} updated, "
                    f"{inactive_count} inactive) in {duration:.1f}s"
                )

                # Notify RC of delta even though data is already in shared NIB.
                # This lets RC log the event and detect anomalies.
                if new_count or updated_count or inactive_count:
                    current_rc_id = resolve_rc_id(RC_URL, current_rc_id)
                    http_send_discovery_report(
                        rc_url=RC_URL,
                        lc_id=LC_ID,
                        region=REGION,
                        subnet=SUBNET,
                        recipient_id=current_rc_id,
                        new_count=new_count,
                        updated_count=updated_count,
                        inactive_count=inactive_count,
                    )

            except Exception as e:
                logger.error(f"Cycle {cycle} error: {e}", exc_info=True)

            logger.info(f"Sleeping {DISCOVERY_INTERVAL}s ...")
            time.sleep(DISCOVERY_INTERVAL)

    except KeyboardInterrupt:
        logger.info("LC shutting down")


if __name__ == "__main__":
    main()