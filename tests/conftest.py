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
