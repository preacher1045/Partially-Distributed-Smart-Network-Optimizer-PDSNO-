"""
Example: NIB Store Usage

Demonstrates how to use the Network Information Base (NIB) for storing
and retrieving network device information with optimistic locking.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PDSNO.datastore import NIBStore, Device, DeviceStatus, Event, LockType


def main():
    print("="*60)
    print("PDSNO Example: NIB Store Usage")
    print("="*60)
    print()
    
    # 1. Create NIB Store
    print("1. Initializing NIBStore...")
    nib = NIBStore("config/example_pdsno.db")
    print("   ✓ Database initialized\n")
    
    # 2. Create and insert a device
    print("2. Creating a new device...")
    device = Device(
        device_id="",  # Will be auto-generated
        ip_address="192.168.1.100",
        mac_address="AA:BB:CC:DD:EE:01",
        hostname="switch-core-1",
        vendor="Cisco",
        device_type="switch",
        status=DeviceStatus.DISCOVERED,
        region="zone-A",
        managed_by_lc="local_cntl_1"
    )
    
    result = nib.upsert_device(device)
    if result.success:
        device_id = result.data
        print(f"   ✓ Device created with ID: {device_id}\n")
    
    # 3. Retrieve device by MAC
    print("3. Retrieving device by MAC address...")
    retrieved = nib.get_device_by_mac("AA:BB:CC:DD:EE:01")
    if retrieved:
        print(f"   ✓ Device found: {retrieved.hostname}")
        print(f"     IP: {retrieved.ip_address}")
        print(f"     Status: {retrieved.status.value}")
        print(f"     Version: {retrieved.version}\n")
    
    # 4. Demonstrate optimistic locking
    print("4. Testing optimistic locking...")
    
    # Simulate two "processes" reading the same device
    device_v1 = nib.get_device_by_mac("AA:BB:CC:DD:EE:01")
    device_v2 = nib.get_device_by_mac("AA:BB:CC:DD:EE:01")
    
    print(f"   - Process 1 read version: {device_v1.version}")
    print(f"   - Process 2 read version: {device_v2.version}")
    
    # Process 1 updates first
    device_v1.status = DeviceStatus.ACTIVE
    result1 = nib.upsert_device(device_v1)
    print(f"   - Process 1 update: {'SUCCESS' if result1.success else 'FAILED'}")
    
    # Process 2 tries to update (should fail due to version mismatch)
    device_v2.hostname = "switch-core-1-renamed"
    result2 = nib.upsert_device(device_v2)
    print(f"   - Process 2 update: {'SUCCESS' if result2.success else 'FAILED (CONFLICT)'}")
    if result2.conflict:
        print(f"     Reason: {result2.error}\n")
    
    # 5. Write to event log
    print("5. Writing to event log...")
    event = Event(
        event_id="",
        event_type="device_discovered",
        controller_id="local_cntl_1",
        timestamp=datetime.now(timezone.utc),
        details={
            "device_id": device_id,
            "mac_address": "AA:BB:CC:DD:EE:01",
            "ip_address": "192.168.1.100"
        }
    )
    
    event_result = nib.write_event(event)
    if event_result.success:
        print(f"   ✓ Event logged with ID: {event_result.data}")
        print(f"     Signature: {event.signature[:20]}...\n")
    
    # 6. Demonstrate lock mechanism
    print("6. Testing lock mechanism...")
    
    # Acquire lock
    lock_result = nib.acquire_lock(
        subject_id="device-001",
        lock_type=LockType.CONFIG_APPROVAL,
        held_by="controller-1",
        ttl_seconds=300
    )
    
    if lock_result.success:
        print(f"   ✓ Lock acquired by controller-1")
        lock_id = lock_result.data
        
        # Try to acquire same lock (should fail)
        lock_result2 = nib.acquire_lock(
            subject_id="device-001",
            lock_type=LockType.CONFIG_APPROVAL,
            held_by="controller-2",
            ttl_seconds=300
        )
        print(f"   - Controller-2 lock attempt: {'SUCCESS' if lock_result2.success else 'BLOCKED'}")
        
        # Check lock status
        active_lock = nib.check_lock("device-001", LockType.CONFIG_APPROVAL)
        if active_lock:
            print(f"   - Active lock held by: {active_lock.held_by}")
        
        # Release lock
        release_result = nib.release_lock(lock_id, "controller-1")
        print(f"   ✓ Lock released\n")
    
    print("="*60)
    print("✓ All NIB operations completed successfully!")
    print("="*60)


if __name__ == "__main__":
    main()
