
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
