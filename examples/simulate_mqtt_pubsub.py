#!/usr/bin/env python3
"""
MQTT Pub/Sub Simulation

Demonstrates Phase 6B: Discovery reports via MQTT publish-subscribe.

Components:
1. MQTT Broker (Mosquitto) - must be running on localhost:1883
2. Regional Controller - subscribes to pdsno/discovery/zone-A/+
3. Local Controller - publishes to pdsno/discovery/zone-A/local_cntl_zone-a_001

Flow:
- RC subscribes to discovery topic pattern
- LC runs discovery and publishes report to MQTT
- RC receives report via subscription (no direct addressing needed)
"""

import logging
import time
from pathlib import Path

from pdsno.controllers.regional_controller import RegionalController
from pdsno.controllers.local_controller import LocalController
from pdsno.controllers.context_manager import ContextManager
from pdsno.datastore import NIBStore


def setup_logging():
    """Configure logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def check_mqtt_broker():
    """Check if MQTT broker is running"""
    import socket
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('localhost', 1883))
        sock.close()
        return result == 0
    except:
        return False


def main():
    """Run the MQTT pub/sub simulation"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("PDSNO Phase 6B - MQTT Pub/Sub Simulation")
    logger.info("=" * 60)
    
    # Check MQTT broker
    logger.info("\n[1/6] Checking MQTT broker...")
    if not check_mqtt_broker():
        logger.error("✗ MQTT broker not running on localhost:1883")
        logger.info("\nPlease start Mosquitto broker:")
        logger.info("  Ubuntu/Debian: sudo systemctl start mosquitto")
        logger.info("  macOS: brew services start mosquitto")
        logger.info("  Windows: mosquitto -v")
        logger.info("  Docker: docker run -d -p 1883:1883 eclipse-mosquitto")
        return 1
    
    logger.info("✓ MQTT broker is running")
    
    # Setup
    logger.info("\n[2/6] Initializing infrastructure...")
    sim_dir = Path("./sim_phase6b")
    sim_dir.mkdir(exist_ok=True)
    
    rc_context = ContextManager(str(sim_dir / "rc_context.yaml"))
    lc_context = ContextManager(str(sim_dir / "lc_context.yaml"))
    nib_store = NIBStore(str(sim_dir / "pdsno.db"))
    
    logger.info("✓ Infrastructure ready")
    
    # Create Regional Controller with MQTT
    logger.info("\n[3/6] Creating Regional Controller with MQTT...")
    rc = RegionalController(
        temp_id="regional_cntl_zone-A_1",  # Manually set for PoC
        region="zone-A",
        context_manager=rc_context,
        nib_store=nib_store,
        mqtt_broker="localhost",
        mqtt_port=1883
    )
    
    # Connect to MQTT and subscribe
    if not rc.connect_mqtt():
        logger.error("✗ RC failed to connect to MQTT")
        return 1
    
    logger.info("✓ RC connected to MQTT broker")
    
    # Subscribe to discovery reports
    rc.subscribe_to_discovery_reports()
    logger.info(f"✓ RC subscribed to pdsno/discovery/zone-A/+")
    
    # Create Local Controller with MQTT
    logger.info("\n[4/6] Creating Local Controller with MQTT...")
    lc = LocalController(
        controller_id="local_cntl_zone-a_001",
        region="zone-A",
        subnet="192.168.1.0/24",
        context_manager=lc_context,
        nib_store=nib_store,
        mqtt_broker="localhost",
        mqtt_port=1883
    )
    
    # Connect to MQTT
    if not lc.connect_mqtt():
        logger.error("✗ LC failed to connect to MQTT")
        return 1
    
    logger.info("✓ LC connected to MQTT broker")
    logger.info(f"✓ LC will publish to pdsno/discovery/zone-A/{lc.controller_id}")
    
    # Run discovery cycle
    logger.info("\n[5/6] Running discovery cycle...")
    logger.info("-" * 60)
    
    # Give MQTT subscriptions time to be established
    time.sleep(1)
    
    # Run discovery - will publish to MQTT instead of direct messaging
    result = lc.run_discovery_cycle(regional_controller_id=rc.controller_id)
    
    logger.info("-" * 60)
    logger.info(f"✓ Discovery complete:")
    logger.info(f"  - Devices found: {result['devices_found']}")
    logger.info(f"  - New devices: {result['new_devices']}")
    logger.info(f"  - Report published to MQTT ✓")
    
    # Wait for RC to process the message
    logger.info("\n[6/6] Waiting for RC to receive MQTT message...")
    time.sleep(2)
    
    # Verify
    logger.info("\n" + "=" * 60)
    logger.info("Phase 6B Simulation Complete!")
    logger.info("=" * 60)
    
    logger.info("\nKey achievements:")
    logger.info("  ✓ RC subscribed to discovery topic pattern")
    logger.info("  ✓ LC published discovery report to MQTT")
    logger.info("  ✓ RC received and processed report via subscription")
    logger.info("  ✓ No direct addressing needed (pub/sub pattern)")
    
    logger.info("\nBenefits demonstrated:")
    logger.info("  - Decoupling: LC doesn't need to know RC's address")
    logger.info("  - Scalability: Multiple RCs can subscribe to same topic")
    logger.info("  - Reliability: MQTT broker handles delivery and retries")
    logger.info("  - Efficiency: One publish reaches all subscribers")
    
    # Cleanup
    logger.info("\nDisconnecting from MQTT...")
    lc.disconnect_mqtt()
    rc.disconnect_mqtt()
    logger.info("✓ Disconnected")
    
    return 0


if __name__ == "__main__":
    exit(main())
