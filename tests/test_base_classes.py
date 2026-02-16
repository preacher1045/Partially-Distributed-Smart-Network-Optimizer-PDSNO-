"""
Tests for Base Classes

Tests AlgorithmBase and BaseController functionality.
"""

import pytest
from datetime import datetime, timezone

from PDSNO.core.base_class import AlgorithmBase
from PDSNO.controllers.base_controller import BaseController


class DummyAlgorithm(AlgorithmBase):
    """Test algorithm for lifecycle testing"""
    
    def initialize(self, context):
        self.value = context.get('test_value', 0)
        self._initialized = True
    
    def execute(self):
        super().execute()  # Check initialization
        self.result = self.value * 2
        self._executed = True
        return self.result
    
    def finalize(self):
        super().finalize()  # Check execution
        return {
            "status": "complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": self.result
        }


def test_algorithm_normal_lifecycle():
    """Test normal algorithm lifecycle: initialize → execute → finalize"""
    algo = DummyAlgorithm()
    
    algo.initialize({'test_value': 10})
    result = algo.execute()
    assert result == 20
    
    payload = algo.finalize()
    assert payload['status'] == "complete"
    assert payload['result'] == 20


def test_algorithm_execute_before_initialize():
    """Test that execute() raises error if called before initialize()"""
    algo = DummyAlgorithm()
    
    with pytest.raises(RuntimeError, match="initialize.*must be called"):
        algo.execute()


def test_algorithm_finalize_before_execute():
    """Test that finalize() raises error if called before execute()"""
    algo = DummyAlgorithm()
    algo.initialize({'test_value': 5})
    
    with pytest.raises(RuntimeError, match="execute.*must be called"):
        algo.finalize()


def test_base_controller_initialization(base_controller):
    """Test BaseController initializes correctly"""
    assert base_controller.controller_id == "test_controller_1"
    assert base_controller.role == "local"
    assert base_controller.region == "test-zone"
    assert base_controller.logger is not None


def test_base_controller_load_algorithm(base_controller):
    """Test loading an algorithm"""
    algo = base_controller.load_algorithm(DummyAlgorithm)
    assert isinstance(algo, DummyAlgorithm)


def test_base_controller_run_algorithm(base_controller):
    """Test running an algorithm through the controller"""
    algo = DummyAlgorithm()
    context = {'test_value': 15}
    
    payload = base_controller.run_algorithm(algo, context)
    
    assert payload['status'] == "complete"
    assert payload['result'] == 30


def test_base_controller_context_operations(base_controller):
    """Test context get/set operations"""
    base_controller.set_context('test_key', 'test_value')
    value = base_controller.get_context('test_key')
    assert value == 'test_value'
    
    # Test default value
    missing = base_controller.get_context('nonexistent', 'default')
    assert missing == 'default'
