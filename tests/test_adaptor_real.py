"""
Real Device Adapter Tests

Tests adapters against real network devices (requires test environment).
Run with: pytest tests/integration/test_adapters_real.py --real-devices
"""

import pytest
import os

from pdsno.adapters import VendorAdapterFactory, ConfigIntent, IntentType


# Skip if not running with real devices
pytestmark = pytest.mark.skipif(
    not os.getenv('PDSNO_TEST_REAL_DEVICES'),
    reason="Real device tests require PDSNO_TEST_REAL_DEVICES=1"
)


@pytest.fixture
def cisco_device():
    """Cisco device credentials from environment"""
    return {
        'vendor': 'cisco',
        'platform': 'ios',
        'ip': os.getenv('CISCO_TEST_IP', '192.168.1.10'),
        'username': os.getenv('CISCO_TEST_USER', 'admin'),
        'password': os.getenv('CISCO_TEST_PASS', 'cisco'),
        'port': int(os.getenv('CISCO_TEST_PORT', 22))
    }


@pytest.fixture
def juniper_device():
    """Juniper device credentials from environment"""
    return {
        'vendor': 'juniper',
        'platform': 'junos',
        'ip': os.getenv('JUNIPER_TEST_IP', '192.168.1.20'),
        'username': os.getenv('JUNIPER_TEST_USER', 'admin'),
        'password': os.getenv('JUNIPER_TEST_PASS', 'juniper'),
        'port': int(os.getenv('JUNIPER_TEST_PORT', 830))
    }


class TestCiscoAdapterReal:
    """Test Cisco adapter with real device"""
    
    def test_connection(self, cisco_device):
        """Test connection to Cisco device"""
        adapter = VendorAdapterFactory.create_adapter(cisco_device)
        
        connected = adapter.connect(cisco_device)
        assert connected is True
        
        adapter.disconnect()
    
    def test_get_config(self, cisco_device):
        """Test retrieving configuration"""
        adapter = VendorAdapterFactory.create_adapter(cisco_device)
        adapter.connect(cisco_device)
        
        config = adapter.get_running_config()
        
        assert config is not None
        assert len(config) > 0
        assert 'version' in config.lower()
        
        adapter.disconnect()
    
    def test_apply_vlan_config(self, cisco_device):
        """Test applying VLAN configuration"""
        adapter = VendorAdapterFactory.create_adapter(cisco_device)
        adapter.connect(cisco_device)
        
        # Create VLAN intent
        vlan_intent = ConfigIntent(
            intent_type=IntentType.CREATE_VLAN,
            parameters={
                'vlan_id': 999,  # Test VLAN
                'name': 'TEST_VLAN',
                'description': 'Integration test VLAN'
            }
        )
        
        # Translate and apply
        commands = adapter.translate_intent(vlan_intent)
        result = adapter.apply_config(commands)
        
        assert result['success'] is True
        
        # Verify
        verified = adapter.verify_config(vlan_intent)
        assert verified is True
        
        # Cleanup - remove test VLAN
        cleanup_commands = [
            'no vlan 999'
        ]
        adapter.apply_config(cleanup_commands)
        
        adapter.disconnect()


class TestJuniperAdapterReal:
    """Test Juniper adapter with real device"""
    
    def test_connection(self, juniper_device):
        """Test connection to Juniper device"""
        adapter = VendorAdapterFactory.create_adapter(juniper_device)
        
        connected = adapter.connect(juniper_device)
        assert connected is True
        
        adapter.disconnect()
    
    def test_get_config(self, juniper_device):
        """Test retrieving configuration"""
        adapter = VendorAdapterFactory.create_adapter(juniper_device)
        adapter.connect(juniper_device)
        
        config = adapter.get_running_config()
        
        assert config is not None
        assert len(config) > 0
        
        adapter.disconnect()


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--real-devices"])