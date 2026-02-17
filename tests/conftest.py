"""
Pytest Configuration and Shared Fixtures

Provides common fixtures for PDSNO tests.
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from pdsno.controllers.context_manager import ContextManager
from pdsno.datastore.sqlite_store import NIBStore
from pdsno.controllers.base_controller import BaseController
from pdsno.controllers.global_controller import GlobalController
from pdsno.controllers.regional_controller import RegionalController
from pdsno.communication.message_bus import MessageBus


@pytest.fixture
def temp_dir():
    """Provide a temporary directory that gets cleaned up after test"""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def context_manager(temp_dir):
    """Provide a ContextManager with temporary storage"""
    context_path = temp_dir / "context_runtime.yaml"
    return ContextManager(str(context_path))


@pytest.fixture
def nib_store(temp_dir):
    """Provide a NIBStore with temporary database"""
    db_path = temp_dir / "test_pdsno.db"
    return NIBStore(str(db_path))


@pytest.fixture
def base_controller(context_manager):
    """Provide a basic controller instance for testing"""
    return BaseController(
        controller_id="test_controller_1",
        role="local",
        context_manager=context_manager,
        region="test-zone"
    )


@pytest.fixture
def message_bus():
    """Provide a message bus instance for tests"""
    return MessageBus()


@pytest.fixture
def gc(temp_dir, nib_store):
    """Provide a GlobalController for validation tests"""
    context_path = temp_dir / "gc_context.yaml"
    context_mgr = ContextManager(str(context_path))
    return GlobalController(
        controller_id="global_cntl_1",
        context_manager=context_mgr,
        nib_store=nib_store
    )


@pytest.fixture
def rc(temp_dir, nib_store, message_bus):
    """Provide a RegionalController for validation tests"""
    context_path = temp_dir / "rc_context.yaml"
    context_mgr = ContextManager(str(context_path))
    return RegionalController(
        temp_id="temp-rc-test-001",
        region="zone-A",
        context_manager=context_mgr,
        nib_store=nib_store,
        message_bus=message_bus
    )
