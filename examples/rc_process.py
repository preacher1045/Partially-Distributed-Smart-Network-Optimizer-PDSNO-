#!/usr/bin/env python3
"""
Regional Controller - Standalone REST Server Process

Starts a Regional Controller with REST server on port 8002.
Connects to Global Controller for validation via HTTP.
Use this for manual testing of REST endpoints.

Prerequisites:
    - Global Controller must be running on port 8001
    - Run gc_process.py in another terminal first

Example:
    Terminal 1: python examples/gc_process.py
    Terminal 2: python examples/rc_process.py
    Terminal 3: curl http://localhost:8002/health
"""

import time
import logging
from pathlib import Path

from pdsno.controllers.regional_controller import RegionalController
from pdsno.controllers.context_manager import ContextManager
from pdsno.datastore import NIBStore
from pdsno.communication.http_client import ControllerHTTPClient

logging.basicConfig(level=logging.INFO)

# Setup
sim_dir = Path("./sim_phase6a")
rc_context = ContextManager(str(sim_dir / "rc_context.yaml"))
nib_store = NIBStore(str(sim_dir / "pdsno.db"))

# Create HTTP client
http_client = ControllerHTTPClient()

# Create RC with REST server
rc = RegionalController(
    temp_id="temp-rc-zone-a-001",
    region="zone-A",
    context_manager=rc_context,
    nib_store=nib_store,
    http_client=http_client,
    enable_rest=True,
    rest_port=8002
)

# Start REST server
rc.start_rest_server_background()

# Wait for GC to be ready
time.sleep(2)

# Request validation from GC via HTTP
print("Requesting validation from Global Controller...")
rc.request_validation(
    global_controller_id="global_cntl_1",
    global_controller_url="http://localhost:8001"
)

if rc.validated:
    print(f"✓ Validation successful! Assigned ID: {rc.assigned_id}")
    rc.update_rest_server_id()
else:
    print("- Validation pending or failed")

print("\nRegional Controller REST server running on http://localhost:8002")
print("\nAvailable endpoints:")
print("  GET  http://localhost:8002/health")
print("  GET  http://localhost:8002/info")
print("  POST http://localhost:8002/message/discovery_report")
print("\nPress Ctrl+C to stop")

# Keep running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nShutting down Regional Controller")
