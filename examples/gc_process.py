#!/usr/bin/env python3
"""
Global Controller - Standalone REST Server Process

Starts a Global Controller with REST server on port 8001.
Use this for manual testing of REST endpoints.

Example:
    Terminal 1: python examples/gc_process.py
    Terminal 2: curl http://localhost:8001/health
"""

import time
import logging
from pathlib import Path

from pdsno.controllers.global_controller import GlobalController
from pdsno.controllers.context_manager import ContextManager
from pdsno.datastore import NIBStore

logging.basicConfig(level=logging.INFO)

# Setup
sim_dir = Path("./sim_phase6a")
sim_dir.mkdir(exist_ok=True)

gc_context = ContextManager(str(sim_dir / "gc_context.yaml"))
nib_store = NIBStore(str(sim_dir / "pdsno.db"))

# Create GC with REST server
gc = GlobalController(
    controller_id="global_cntl_1",
    context_manager=gc_context,
    nib_store=nib_store,
    enable_rest=True,
    rest_port=8001
)

# Start REST server
gc.start_rest_server_background()

print("Global Controller REST server running on http://localhost:8001")
print("\nAvailable endpoints:")
print("  GET  http://localhost:8001/health")
print("  GET  http://localhost:8001/info")
print("  POST http://localhost:8001/message/validation_request")
print("  POST http://localhost:8001/message/challenge_response")
print("\nPress Ctrl+C to stop")

# Keep running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nShutting down Global Controller")
