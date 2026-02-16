"""
Tests for NIBStore

Tests database operations, optimistic locking, and data models.
"""

import pytest
from datetime import datetime, timezone

from PDSNO.datastore.sqlite_store import NIBStore
from PDSNO.datastore.models import Device, DeviceStatus, Event, Lock, LockType, NIBResult


def test_nib_store_initialization(nib_store):
    """Test NIBStore initializes with schema"""
    assert nib_store.db_path.exists()


def test_device_insert(nib_store):
    """Test inserting a new device"""
    device = Device(
        device_id="",  # Will be auto-generated
        ip_address="192.168.1.100",
        mac_address="AA:BB:CC:DD:EE:FF",
        hostname="test-device",
        status=DeviceStatus.DISCOVERED
    )
    
    result = nib_store.upsert_device(device)
    assert result.success
    assert result.data is not None  # Device ID


def test_device_get_by_mac(nib_store):
    """Test retrieving device by MAC address"""
    device = Device(
        device_id="test-dev-001",
        ip_address="192.168.1.101",
        mac_address="11:22:33:44:55:66",
        hostname="test-host",
        status=DeviceStatus.ACTIVE
    )
    
    nib_store.upsert_device(device)
    
    retrieved = nib_store.get_device_by_mac("11:22:33:44:55:66")
    assert retrieved is not None
    assert retrieved.hostname == "test-host"
    assert retrieved.status == DeviceStatus.ACTIVE


def test_device_optimistic_locking(nib_store):
    """Test optimistic locking prevents concurrent writes"""
    device = Device(
        device_id="test-dev-002",
        ip_address="192.168.1.102",
        mac_address="AA:11:22:33:44:55",
        hostname="lock-test",
        status=DeviceStatus.DISCOVERED
    )
    
    # Insert device
    nib_store.upsert_device(device)
    
    # Retrieve device (version 0)
    device1 = nib_store.get_device_by_mac("AA:11:22:33:44:55")
    device2 = nib_store.get_device_by_mac("AA:11:22:33:44:55")
    
    # First update succeeds
    device1.hostname = "updated-1"
    result1 = nib_store.upsert_device(device1)
    assert result1.success
    
    # Second update fails (version mismatch)
    device2.hostname = "updated-2"
    result2 = nib_store.upsert_device(device2)
    assert not result2.success
    assert result2.conflict


def test_event_log_write(nib_store):
    """Test writing to event log"""
    event = Event(
        event_id="",
        event_type="device_discovered",
        controller_id="test_controller",
        timestamp=datetime.now(timezone.utc),
        details={"device_id": "dev-001", "ip": "192.168.1.1"}
    )
    
    result = nib_store.write_event(event)
    assert result.success
    assert result.data is not None  # Event ID


def test_lock_acquire_and_release(nib_store):
    """Test lock acquisition and release"""
    # Acquire lock
    result = nib_store.acquire_lock(
        subject_id="device-001",
        lock_type=LockType.CONFIG_APPROVAL,
        held_by="controller-1",
        ttl_seconds=300
    )
    assert result.success
    lock_id = result.data
    
    # Check lock exists
    lock = nib_store.check_lock("device-001", LockType.CONFIG_APPROVAL)
    assert lock is not None
    assert lock.held_by == "controller-1"
    
    # Try to acquire again (should fail)
    result2 = nib_store.acquire_lock(
        subject_id="device-001",
        lock_type=LockType.CONFIG_APPROVAL,
        held_by="controller-2",
        ttl_seconds=300
    )
    assert not result2.success
    
    # Release lock
    release_result = nib_store.release_lock(lock_id, "controller-1")
    assert release_result.success
    
    # Lock should be gone
    lock_after = nib_store.check_lock("device-001", LockType.CONFIG_APPROVAL)
    assert lock_after is None
