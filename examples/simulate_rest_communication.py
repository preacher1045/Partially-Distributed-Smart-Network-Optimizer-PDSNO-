#!/usr/bin/env python3
"""
Multi-Process REST Communication Simulation

Demonstrates Phase 6A: Controllers communicating over HTTP instead of in-process message bus.

Each controller runs in its own process with its own REST server.
Controllers communicate by making HTTP POST requests to each other.
"""

import logging
import time
import subprocess
import sys
from pathlib import Path


def setup_logging():
    """Configure logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def start_global_controller():
    """Start Global Controller in separate process"""
    logger = logging.getLogger(__name__)
    logger.info("Starting Global Controller process...")
    
    script = """
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
print("Press Ctrl+C to stop")

# Keep running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Shutting down Global Controller")
"""
    
    # Write script to temp file
    script_path = Path("./gc_process.py")
    script_path.write_text(script)
    
    # Start process
    proc = subprocess.Popen(
        [sys.executable, str(script_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # Wait for server to start
    time.sleep(3)
    
    return proc


def start_regional_controller():
    """Start Regional Controller in separate process"""
    logger = logging.getLogger(__name__)
    logger.info("Starting Regional Controller process...")
    
    script = """
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
    print("✗ Validation failed")

print("Regional Controller REST server running on http://localhost:8002")
print("Press Ctrl+C to stop")

# Keep running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Shutting down Regional Controller")
"""
    
    # Write script to temp file
    script_path = Path("./rc_process.py")
    script_path.write_text(script)
    
    # Start process
    proc = subprocess.Popen(
        [sys.executable, str(script_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    return proc


def main():
    """Run the multi-process simulation"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("PDSNO Phase 6A - Multi-Process REST Communication")
    logger.info("=" * 60)
    
    gc_proc = None
    rc_proc = None
    
    try:
        # Start Global Controller
        gc_proc = start_global_controller()
        logger.info("✓ Global Controller started on http://localhost:8001")
        
        # Start Regional Controller
        rc_proc = start_regional_controller()
        logger.info("✓ Regional Controller started on http://localhost:8002")
        
        logger.info("\nBoth controllers are running.")
        logger.info("You can:")
        logger.info("  - Check health: curl http://localhost:8001/health")
        logger.info("  - Get info: curl http://localhost:8001/info")
        logger.info("  - View logs above to see HTTP validation flow")
        logger.info("\nPress Ctrl+C to stop all controllers")
        
        # Monitor processes
        while True:
            # Check if processes are still running
            if gc_proc.poll() is not None:
                logger.error("Global Controller process died")
                break
            if rc_proc.poll() is not None:
                logger.error("Regional Controller process died")
                break
            
            # Print process output
            if gc_proc.stdout:
                line = gc_proc.stdout.readline()
                if line:
                    print(f"[GC] {line.strip()}")
            
            if rc_proc.stdout:
                line = rc_proc.stdout.readline()
                if line:
                    print(f"[RC] {line.strip()}")
            
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        logger.info("\n\nShutting down controllers...")
    
    finally:
        # Cleanup
        if gc_proc:
            gc_proc.terminate()
            gc_proc.wait(timeout=5)
        if rc_proc:
            rc_proc.terminate()
            rc_proc.wait(timeout=5)
        
        logger.info("All controllers stopped")


if __name__ == "__main__":
    main()
