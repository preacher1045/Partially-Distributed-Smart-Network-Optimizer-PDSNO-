"""
Test vendor adapters - intent translation (no real device connections)
"""
import pytest
from unittest.mock import patch, MagicMock

from pdsno.adapters import VendorAdapterFactory, ConfigIntent, IntentType
from pdsno.adapters.cisco_ios_adapter import CiscoIOSAdapter
from pdsno.adapters.juniper_adapter import JuniperAdapter
from pdsno.adapters.arista_adapter import AristaAdapter


@pytest.fixture
def vlan_intent():
    """Common VLAN creation intent for testing"""
    return ConfigIntent(
        intent_type=IntentType.CREATE_VLAN,
        parameters={
            'vlan_id': 100,
            'name': 'Engineering',
            'description': 'Engineering department'
        }
    )


@pytest.fixture
def cisco_device():
    return {
        'vendor': 'cisco',
        'platform': 'ios',
        'ip': '192.168.1.10',
        'username': 'admin',
        'password': 'cisco123'
    }


@pytest.fixture
def juniper_device():
    return {
        'vendor': 'juniper',
        'platform': 'junos',
        'ip': '192.168.1.20',
        'username': 'admin',
        'password': 'juniper123'
    }


@pytest.fixture
def arista_device():
    return {
        'vendor': 'arista',
        'platform': 'eos',
        'ip': '192.168.1.30',
        'username': 'admin',
        'password': 'arista123'
    }


class TestVendorAdapterFactory:
    """Test adapter factory creates correct adapter types"""
    
    def test_creates_cisco_adapter(self, cisco_device):
        adapter = VendorAdapterFactory.create_adapter(cisco_device)
        assert isinstance(adapter, CiscoIOSAdapter)
    
    def test_creates_juniper_adapter(self, juniper_device):
        adapter = VendorAdapterFactory.create_adapter(juniper_device)
        assert isinstance(adapter, JuniperAdapter)
    
    def test_creates_arista_adapter(self, arista_device):
        adapter = VendorAdapterFactory.create_adapter(arista_device)
        assert isinstance(adapter, AristaAdapter)
    
    def test_raises_for_unknown_vendor(self):
        unknown_device = {'vendor': 'unknown', 'platform': 'x'}
        with pytest.raises((ValueError, KeyError)):
            VendorAdapterFactory.create_adapter(unknown_device)


class TestCiscoAdapter:
    """Test Cisco IOS adapter intent translation"""
    
    def test_translate_vlan_intent(self, cisco_device, vlan_intent):
        adapter = CiscoIOSAdapter(cisco_device)
        commands = adapter.translate_intent(vlan_intent)
        
        assert 'vlan 100' in commands
        assert 'name Engineering' in commands
        assert 'exit' in commands
    
    @patch('pdsno.adapters.cisco_ios_adapter.ConnectHandler')
    def test_connect_calls_netmiko(self, mock_connect, cisco_device):
        adapter = CiscoIOSAdapter(cisco_device)
        adapter.connect(cisco_device)
        mock_connect.assert_called_once()


class TestJuniperAdapter:
    """Test Juniper adapter intent translation"""
    
    def test_translate_vlan_intent(self, juniper_device, vlan_intent):
        adapter = JuniperAdapter(juniper_device)
        commands = adapter.translate_intent(vlan_intent)
        
        # Juniper uses set commands
        assert any('set vlans' in cmd for cmd in commands)
        assert any('vlan-id 100' in cmd for cmd in commands)


class TestAristaAdapter:
    """Test Arista adapter intent translation"""
    
    def test_translate_vlan_intent(self, arista_device, vlan_intent):
        adapter = AristaAdapter(arista_device)
        commands = adapter.translate_intent(vlan_intent)
        
        # Arista uses similar syntax to Cisco
        assert 'vlan 100' in commands
        assert any('name' in cmd for cmd in commands)


class TestConfigIntent:
    """Test ConfigIntent data class"""
    
    def test_valid_intent_creation(self):
        intent = ConfigIntent(
            intent_type=IntentType.CREATE_VLAN,
            parameters={'vlan_id': 10}
        )
        assert intent.intent_type == IntentType.CREATE_VLAN
        assert intent.parameters['vlan_id'] == 10
    
    def test_invalid_intent_type_raises(self):
        with pytest.raises(ValueError):
            ConfigIntent(
                intent_type='invalid',
                parameters={}
            )