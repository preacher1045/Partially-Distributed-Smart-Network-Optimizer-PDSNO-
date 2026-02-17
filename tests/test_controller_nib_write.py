"""
Test for Controller Registration in NIB - Gap Fix

Add this test to tests/test_controller_validation.py
"""

from pdsno.communication.message_format import MessageType
from pdsno.controllers.regional_controller import RegionalController

def test_controller_written_to_nib(gc, rc, message_bus, nib_store):
    """Test that validated controllers are written to NIB"""
    # Register GC
    gc_handlers = {
        MessageType.VALIDATION_REQUEST: gc.handle_validation_request,
        MessageType.CHALLENGE_RESPONSE: gc.handle_challenge_response
    }
    message_bus.register_controller("global_cntl_1", gc_handlers)
    
    # Register RC
    rc_handlers = {}
    message_bus.register_controller(rc.temp_id, rc_handlers)
    
    # Request validation
    rc.request_validation("global_cntl_1")
    
    # Verify RC is validated
    assert rc.validated is True
    assert rc.assigned_id is not None
    
    # NEW: Verify controller record exists in NIB
    controller_record = nib_store.get_controller(rc.assigned_id)
    
    assert controller_record is not None
    assert controller_record.controller_id == rc.assigned_id
    assert controller_record.role == "regional"
    assert controller_record.region == "zone-A"
    assert controller_record.status == "active"
    assert controller_record.validated_by == "global_cntl_1"
    assert controller_record.public_key == "ed25519-pubkey-placeholder"
    
    # Verify audit event was written
    # This would require a get_events_by_type() method in NIBStore
    # For now, we've confirmed the controller record exists


def test_controller_query_by_region(gc, nib_store, message_bus):
    """Test querying controllers by region"""
    # Create and validate two RCs in the same region
    rc1 = RegionalController(
        temp_id="temp-rc-1",
        region="zone-A",
        context_manager=gc.context_manager,  # Reuse GC's context manager for test
        nib_store=nib_store,
        message_bus=message_bus
    )
    
    rc2 = RegionalController(
        temp_id="temp-rc-2",
        region="zone-A",
        context_manager=gc.context_manager,
        nib_store=nib_store,
        message_bus=message_bus
    )
    
    # Register GC
    gc_handlers = {
        MessageType.VALIDATION_REQUEST: gc.handle_validation_request,
        MessageType.CHALLENGE_RESPONSE: gc.handle_challenge_response
    }
    message_bus.register_controller("global_cntl_1", gc_handlers)
    
    # Register and validate both RCs
    message_bus.register_controller(rc1.temp_id, {})
    message_bus.register_controller(rc2.temp_id, {})
    
    rc1.request_validation("global_cntl_1")
    rc2.request_validation("global_cntl_1")
    
    # Query controllers in zone-A
    controllers = nib_store.get_controllers_by_region("zone-A")
    
    assert len(controllers) == 2
    controller_ids = {c.controller_id for c in controllers}
    assert rc1.assigned_id in controller_ids
    assert rc2.assigned_id in controller_ids
