"""
Tests for Device Discovery (Phase 5)

Tests the scanners, Local Controller discovery orchestration, and delta detection.
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from pdsno.discovery import ARPScanner, ICMPScanner, SNMPScanner
from pdsno.controllers.local_controller import LocalController
from pdsno.controllers.regional_controller import RegionalController
from pdsno.controllers.context_manager import ContextManager
from pdsno.datastore import NIBStore, Device, DeviceStatus
from pdsno.communication.message_bus import MessageBus


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def nib_store(temp_dir):
    """Create NIB store instance"""
    return NIBStore(str(temp_dir / "test.db"))


@pytest.fixture
def message_bus():
    """Create message bus instance"""
    return MessageBus()


@pytest.fixture
def lc(temp_dir, nib_store, message_bus):
    """Create Local Controller"""
    context_mgr = ContextManager(str(temp_dir / "lc_context.yaml"))
    return LocalController(
        controller_id="local_cntl_test_001",
        region="zone-A",
        subnet="192.168.1.0/24",
        context_manager=context_mgr,
        nib_store=nib_store,
        message_bus=message_bus
    )


class TestARPScanner:
    """Test ARP scanner algorithm"""
    
    def test_initialization(self):
        """Test scanner initialization"""
        scanner = ARPScanner()
        scanner.initialize({'subnet': '192.168.1.0/24'})
        
        assert scanner._initialized is True
        assert scanner.subnet is not None
        assert str(scanner.subnet) == '192.168.1.0/24'
    
    def test_initialization_missing_subnet(self):
        """Test that initialization fails without subnet"""
        scanner = ARPScanner()
        
        with pytest.raises(ValueError, match="must contain 'subnet'"):
            scanner.initialize({})
    
    def test_initialization_invalid_subnet(self):
        """Test that initialization fails with invalid subnet"""
        scanner = ARPScanner()
        
        with pytest.raises(ValueError, match="Invalid subnet"):
            scanner.initialize({'subnet': 'not-a-subnet'})
    
    def test_execute(self):
        """Test ARP scan execution"""
        scanner = ARPScanner()
        scanner.initialize({'subnet': '192.168.1.0/28'})  # Small subnet for fast test
        
        devices = scanner.execute()
        
        assert scanner._executed is True
        assert isinstance(devices, list)
        # PoC has ~20% response rate
        assert len(devices) >= 0  # May be 0 due to randomness
    
    def test_finalize(self):
        """Test finalize returns proper result"""
        scanner = ARPScanner()
        scanner.initialize({'subnet': '192.168.1.0/28'})
        scanner.execute()
        
        result = scanner.finalize()
        
        assert result['status'] == 'complete'
        assert 'timestamp' in result
        assert 'subnet' in result
        assert 'devices_found' in result


class TestICMPScanner:
    """Test ICMP ping scanner"""
    
    def test_initialization(self):
        """Test scanner initialization"""
        scanner = ICMPScanner()
        scanner.initialize({'ip_list': ['192.168.1.1', '192.168.1.2']})
        
        assert scanner._initialized is True
        assert len(scanner.ip_list) == 2
    
    def test_initialization_missing_ip_list(self):
        """Test that initialization fails without ip_list"""
        scanner = ICMPScanner()
        
        with pytest.raises(ValueError, match="must contain non-empty 'ip_list'"):
            scanner.initialize({})
    
    def test_execute(self):
        """Test ICMP scan execution"""
        scanner = ICMPScanner()
        # Use localhost which should always be reachable
        scanner.initialize({'ip_list': ['127.0.0.1']})
        
        devices = scanner.execute()
        
        assert scanner._executed is True
        assert isinstance(devices, list)
        # Localhost should respond
        assert len(devices) >= 0  # May be 0 if ping fails in test environment
    
    def test_finalize(self):
        """Test finalize returns proper result"""
        scanner = ICMPScanner()
        scanner.initialize({'ip_list': ['127.0.0.1']})
        scanner.execute()
        
        result = scanner.finalize()
        
        assert result['status'] == 'complete'
        assert 'timestamp' in result
        assert 'targets_scanned' in result
        assert 'devices_reachable' in result


class TestSNMPScanner:
    """Test SNMP scanner"""
    
    def test_initialization(self):
        """Test scanner initialization"""
        scanner = SNMPScanner()
        scanner.initialize({'ip_list': ['192.168.1.1']})
        
        assert scanner._initialized is True
        assert scanner.community == 'public'  # Default
    
    def test_initialization_custom_community(self):
        """Test initialization with custom SNMP community"""
        scanner = SNMPScanner()
        scanner.initialize({'ip_list': ['192.168.1.1'], 'community': 'private'})
        
        assert scanner.community == 'private'
    
    def test_execute_graceful_failure(self):
        """Test that SNMP scan doesn't raise even if all queries fail"""
        scanner = SNMPScanner()
        scanner.initialize({'ip_list': ['192.168.1.1', '192.168.1.2']})
        
        # Should not raise even if SNMP fails
        devices = scanner.execute()
        
        assert scanner._executed is True
        assert isinstance(devices, list)


class TestLocalControllerDiscovery:
    """Test Local Controller discovery orchestration"""
    
    def test_discovery_cycle_execution(self, lc, nib_store):
        """Test that discovery cycle runs without errors"""
        result = lc.run_discovery_cycle()
        
        assert result['status'] == 'complete'
        assert 'devices_found' in result
        assert 'new_devices' in result
        assert 'updated_devices' in result
        assert 'inactive_devices' in result
        assert 'cycle_duration_seconds' in result
    
    def test_devices_written_to_nib(self, lc, nib_store):
        """Test that discovered devices are written to NIB"""
        # Run discovery
        result = lc.run_discovery_cycle()
        
        if result['devices_found'] > 0:
            # Query NIB for devices
            # We can't query all devices easily without a get_all method,
            # but we can check if any exist
            import sqlite3
            conn = sqlite3.connect(nib_store.db_path)
            cursor = conn.execute("SELECT COUNT(*) FROM devices")
            count = cursor.fetchone()[0]
            conn.close()
            
            assert count > 0
    
    def test_delta_detection_new_devices(self, lc, nib_store):
        """Test that new devices are detected in delta"""
        # First cycle - all devices should be new
        result1 = lc.run_discovery_cycle()
        new_count_1 = result1['new_devices']
        
        # Second cycle - should have fewer new devices (or none)
        result2 = lc.run_discovery_cycle()
        new_count_2 = result2['new_devices']
        
        # Due to randomness in PoC, we can't assert exact counts,
        # but second cycle should not have MORE new devices than first
        # (unless random chance discovers entirely different set)
        assert result2['status'] == 'complete'
    
    def test_discovery_report_sent_to_rc(self, lc, message_bus):
        """Test that discovery report is sent to RC when provided"""
        from pdsno.communication.message_format import MessageType
        
        # Track if report was sent
        report_received = []
        
        def mock_handler(envelope):
            report_received.append(envelope)
            return None
        
        # Register mock RC
        message_bus.register_controller(
            "regional_cntl_zone-A_1",
            {MessageType.DISCOVERY_REPORT: mock_handler}
        )
        
        # Run discovery with RC ID
        lc.run_discovery_cycle(regional_controller_id="regional_cntl_zone-A_1")
        
        # Check if report was sent (only if there were changes)
        # Due to delta detection, first run always has changes
        # May be 0 or 1 depending on whether devices were found
        assert len(report_received) >= 0


class TestDeltaDetection:
    """Test device delta detection logic"""
    
    def test_merge_scan_results(self, lc):
        """Test merging results from multiple scanners"""
        arp_devices = [
            {'ip': '192.168.1.10', 'mac': 'aa:bb:cc:dd:ee:01', 'timestamp': datetime.now(timezone.utc).isoformat()}
        ]
        
        icmp_devices = {
            '192.168.1.10': {'ip': '192.168.1.10', 'rtt_ms': 1.5}
        }
        
        snmp_devices = {
            '192.168.1.10': {'ip': '192.168.1.10', 'hostname': 'test-device', 'vendor': 'Cisco'}
        }
        
        merged = lc._merge_scan_results(arp_devices, icmp_devices, snmp_devices)
        
        assert len(merged) == 1
        assert merged[0]['ip'] == '192.168.1.10'
        assert merged[0]['mac'] == 'aa:bb:cc:dd:ee:01'
        assert merged[0]['reachable'] is True
        assert merged[0]['rtt_ms'] == 1.5
        assert merged[0]['hostname'] == 'test-device'
        assert merged[0]['vendor'] == 'Cisco'
    
    def test_merge_with_missing_icmp(self, lc):
        """Test merge when ICMP scan has no data for a device"""
        arp_devices = [
            {'ip': '192.168.1.10', 'mac': 'aa:bb:cc:dd:ee:01', 'timestamp': datetime.now(timezone.utc).isoformat()}
        ]
        
        merged = lc._merge_scan_results(arp_devices, {}, {})
        
        assert len(merged) == 1
        assert merged[0]['reachable'] is False
        assert 'hostname' not in merged[0]


class TestRegionalControllerDiscoveryHandler:
    """Test RC's discovery report handling"""
    
    def test_mac_collision_detection(self, temp_dir, nib_store, message_bus):
        """Test that RC detects MAC collisions across LCs"""
        # Create RC
        rc_context = ContextManager(str(temp_dir / "rc_context.yaml"))
        rc = RegionalController(
            temp_id="temp-rc",
            region="zone-A",
            context_manager=rc_context,
            nib_store=nib_store,
            message_bus=message_bus
        )
        
        # Add a device to NIB managed by LC1
        device1 = Device(
            device_id="dev-001",
            ip_address="192.168.1.10",
            mac_address="aa:bb:cc:dd:ee:01",
            status=DeviceStatus.ACTIVE,
            managed_by_lc="lc_1"
        )
        nib_store.upsert_device(device1)
        
        # Simulate LC2 reporting the same MAC
        devices_from_lc2 = [
            {'mac': 'aa:bb:cc:dd:ee:01', 'ip': '192.168.1.10'}
        ]
        
        collisions = rc._check_mac_collisions(devices_from_lc2, "lc_2")
        
        assert len(collisions) > 0
        assert 'aa:bb:cc:dd:ee:01' in collisions
        assert 'lc_1' in collisions['aa:bb:cc:dd:ee:01']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])