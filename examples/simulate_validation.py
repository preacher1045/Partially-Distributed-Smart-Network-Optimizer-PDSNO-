#!/usr/bin/env python3
"""
Controller Validation Simulation

Demonstrates the complete validation flow:
1. Global Controller starts and registers with message bus
2. Regional Controller starts and requests validation
3. GC issues challenge
4. RC responds to challenge
5. GC validates and assigns identity
6. RC is now validated and has permanent ID

This is the first moment PDSNO does something real end-to-end.
"""

import logging
from pathlib import Path

from pdsno.controllers.global_controller import GlobalController
from pdsno.controllers.regional_controller import RegionalController
from pdsno.controllers.context_manager import ContextManager
from pdsno.datastore import NIBStore
from pdsno.communication.message_bus import MessageBus
from pdsno.communication.message_format import MessageType
from pdsno.logging.logger import get_logger


def setup_logging():
    """Configure structured logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def main():
    """Run the validation simulation"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("PDSNO Phase 4 - Controller Validation Simulation")
    logger.info("=" * 60)
    
    # Create temporary directory for simulation
    sim_dir = Path("./sim_phase4")
    sim_dir.mkdir(exist_ok=True)
    
    # Initialize infrastructure
    logger.info("\n[1/6] Initializing infrastructure...")
    
    # Message bus (in-process)
    message_bus = MessageBus()
    
    # NIB (shared between controllers in this simulation)
    nib_path = sim_dir / "pdsno.db"
    nib_store = NIBStore(str(nib_path))
    
    # Context managers (one per controller)
    gc_context = ContextManager(str(sim_dir / "gc_context.yaml"))
    rc_context = ContextManager(str(sim_dir / "rc_context.yaml"))
    
    logger.info("✓ Infrastructure ready")
    
    # Create Global Controller
    logger.info("\n[2/6] Creating Global Controller...")
    gc = GlobalController(
        controller_id="global_cntl_1",
        context_manager=gc_context,
        nib_store=nib_store
    )
    
    # Register GC with message bus
    gc_handlers = {
        MessageType.VALIDATION_REQUEST: gc.handle_validation_request,
        MessageType.CHALLENGE_RESPONSE: gc.handle_challenge_response
    }
    message_bus.register_controller("global_cntl_1", gc_handlers)
    
    logger.info("✓ Global Controller registered")
    
    # Create Regional Controller
    logger.info("\n[3/6] Creating Regional Controller...")
    rc = RegionalController(
        temp_id="temp-rc-zone-a-001",
        region="zone-A",
        context_manager=rc_context,
        nib_store=nib_store,
        message_bus=message_bus
    )
    
    # Register RC with message bus (using temp_id initially)
    rc_handlers = {
        MessageType.CHALLENGE: lambda env: None,  # Handled inline in request_validation
        MessageType.VALIDATION_RESULT: lambda env: None  # Handled inline
    }
    message_bus.register_controller(rc.temp_id, rc_handlers)
    
    logger.info("✓ Regional Controller created with temp_id")
    
    # Request validation
    logger.info("\n[4/6] Regional Controller requesting validation...")
    logger.info("-" * 60)
    
    rc.request_validation("global_cntl_1")
    
    logger.info("-" * 60)
    
    # Check result
    logger.info("\n[5/6] Checking validation result...")
    
    if rc.validated:
        logger.info(f"✓ SUCCESS: RC validated and assigned ID: {rc.assigned_id}")
        logger.info(f"  - Role: {rc.certificate['role']}")
        logger.info(f"  - Region: {rc.certificate['region']}")
        logger.info(f"  - Issued by: {rc.certificate['issued_by']}")
        logger.info(f"  - Has delegation credential: {rc.delegation_credential is not None}")
        
        if rc.delegation_credential:
            logger.info(f"  - Can validate: {rc.delegation_credential['permitted_actions']}")
    else:
        logger.error("✗ FAILURE: RC validation failed")
        return 1
    
    # Verify message bus state
    logger.info("\n[6/6] Verifying system state...")
    controllers = message_bus.get_registered_controllers()
    logger.info(f"Registered controllers: {controllers}")
    
    logger.info("\n" + "=" * 60)
    logger.info("Phase 4 Simulation Complete!")
    logger.info("=" * 60)
    logger.info("\nNext step: Implement Phase 5 (Discovery Module)")
    
    return 0


if __name__ == "__main__":
    exit(main())
