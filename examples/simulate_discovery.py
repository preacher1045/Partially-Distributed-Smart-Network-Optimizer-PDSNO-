#!/usr/bin/env python3
"""
Device Discovery Simulation

Demonstrates the complete discovery flow:
1. LC validates with RC, RC validates with GC
2. LC runs discovery cycle (ARP + ICMP + SNMP)
3. LC writes devices to NIB
4. LC sends delta report to RC
5. RC processes report and detects anomalies
6. Verify devices in NIB
"""

import logging
from pathlib import Path

from pdsno.controllers.global_controller import GlobalController
from pdsno.controllers.regional_controller import RegionalController
from pdsno.controllers.local_controller import LocalController
from pdsno.controllers.context_manager import ContextManager
from pdsno.datastore import NIBStore
from pdsno.communication.message_bus import MessageBus
from pdsno.communication.message_format import MessageType


def setup_logging():
    """Configure structured logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def main():
    """Run the discovery simulation"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("PDSNO Phase 5 - Device Discovery Simulation")
    logger.info("=" * 60)
    
    # Create temporary directory for simulation
    sim_dir = Path("./sim_phase5")
    sim_dir.mkdir(exist_ok=True)
    
    # Initialize infrastructure
    logger.info("\n[1/8] Initializing infrastructure...")
    
    message_bus = MessageBus()
    nib_path = sim_dir / "pdsno.db"
    nib_store = NIBStore(str(nib_path))
    
    gc_context = ContextManager(str(sim_dir / "gc_context.yaml"))
    rc_context = ContextManager(str(sim_dir / "rc_context.yaml"))
    lc_context = ContextManager(str(sim_dir / "lc_context.yaml"))
    
    logger.info("✓ Infrastructure ready")
    
    # Create and register Global Controller
    logger.info("\n[2/8] Creating Global Controller...")
    gc = GlobalController(
        controller_id="global_cntl_1",
        context_manager=gc_context,
        nib_store=nib_store
    )
    
    gc_handlers = {
        MessageType.VALIDATION_REQUEST: gc.handle_validation_request,
        MessageType.CHALLENGE_RESPONSE: gc.handle_challenge_response
    }
    message_bus.register_controller("global_cntl_1", gc_handlers)
    logger.info("✓ Global Controller registered")
    
    # Create and validate Regional Controller
    logger.info("\n[3/8] Creating and validating Regional Controller...")
    rc = RegionalController(
        temp_id="temp-rc-zone-a-001",
        region="zone-A",
        context_manager=rc_context,
        nib_store=nib_store,
        message_bus=message_bus
    )
    
    message_bus.register_controller(rc.temp_id, {})
    rc.request_validation("global_cntl_1")
    
    if not rc.validated:
        logger.error("✗ RC validation failed, aborting")
        return 1
    
    logger.info(f"✓ RC validated: {rc.assigned_id}")
    
    # Re-register RC with its permanent ID and discovery handler
    message_bus.unregister_controller(rc.temp_id)
    rc_handlers = {
        MessageType.DISCOVERY_REPORT: rc.handle_discovery_report
    }
    message_bus.register_controller(rc.assigned_id, rc_handlers)
    
    # Create Local Controller
    logger.info("\n[4/8] Creating Local Controller...")
    lc = LocalController(
        controller_id="local_cntl_zone-a_001",  # Manually assigned for PoC
        region="zone-A",
        subnet="192.168.1.0/24",
        context_manager=lc_context,
        nib_store=nib_store,
        message_bus=message_bus
    )
    
    message_bus.register_controller(lc.controller_id, {})
    logger.info(f"✓ LC created: {lc.controller_id}")
    
    # Run discovery cycle
    logger.info("\n[5/8] Running discovery cycle...")
    logger.info("-" * 60)
    
    discovery_result = lc.run_discovery_cycle(regional_controller_id=rc.assigned_id)
    
    logger.info("-" * 60)
    logger.info(f"✓ Discovery complete:")
    logger.info(f"  - Devices found: {discovery_result['devices_found']}")
    logger.info(f"  - New devices: {discovery_result['new_devices']}")
    logger.info(f"  - Updated devices: {discovery_result['updated_devices']}")
    logger.info(f"  - Inactive devices: {discovery_result['inactive_devices']}")
    logger.info(f"  - Duration: {discovery_result['cycle_duration_seconds']:.2f}s")
    
    # Verify devices in NIB
    logger.info("\n[6/8] Verifying devices in NIB...")
    
    # Query some devices from NIB
    import sqlite3
    conn = sqlite3.connect(str(nib_path))
    cursor = conn.execute("SELECT COUNT(*) FROM devices")
    device_count = cursor.fetchone()[0]
    
    cursor = conn.execute(
        "SELECT device_id, ip_address, mac_address, hostname, status FROM devices LIMIT 5"
    )
    sample_devices = cursor.fetchall()
    conn.close()
    
    logger.info(f"✓ Total devices in NIB: {device_count}")
    if sample_devices:
        logger.info("  Sample devices:")
        for dev in sample_devices:
            logger.info(f"    - {dev[2]} ({dev[1]}) - {dev[3] or 'no hostname'} [{dev[4]}]")
    
    # Run second cycle to test delta detection
    logger.info("\n[7/8] Running second discovery cycle (delta test)...")
    
    discovery_result2 = lc.run_discovery_cycle(regional_controller_id=rc.assigned_id)
    
    logger.info(f"✓ Second cycle complete:")
    logger.info(f"  - Devices found: {discovery_result2['devices_found']}")
    logger.info(f"  - New devices: {discovery_result2['new_devices']} (should be 0 or low)")
    logger.info(f"  - Updated devices: {discovery_result2['updated_devices']}")
    
    # System state summary
    logger.info("\n[8/8] System state summary...")
    controllers = message_bus.get_registered_controllers()
    logger.info(f"Registered controllers: {controllers}")
    
    logger.info("\n" + "=" * 60)
    logger.info("Phase 5 Simulation Complete!")
    logger.info("=" * 60)
    logger.info("\nNext steps:")
    logger.info("1. Check NIB: sqlite3 sim_phase5/pdsno.db 'SELECT * FROM devices;'")
    logger.info("2. Check events: sqlite3 sim_phase5/pdsno.db 'SELECT * FROM events;'")
    logger.info("3. Run tests: pytest tests/test_discovery.py")
    
    return 0


if __name__ == "__main__":
    exit(main())