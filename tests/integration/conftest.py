"""
Integration Test Configuration

Shared fixtures and configuration for integration tests.
"""

import pytest
import tempfile
import shutil
from pathlib import Path


def pytest_addoption(parser):
    """Add custom command line options"""
    parser.addoption(
        "--real-devices",
        action="store_true",
        default=False,
        help="Run tests against real network devices"
    )
    parser.addoption(
        "--slow",
        action="store_true",
        default=False,
        help="Run slow integration tests"
    )


def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line(
        "markers",
        "real_devices: mark test as requiring real network devices"
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running"
    )


@pytest.fixture(scope="session")
def integration_temp_dir():
    """Create temporary directory for integration tests"""
    temp_dir = tempfile.mkdtemp(prefix="pdsno_integration_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def clean_database(integration_temp_dir):
    """Provide clean database for each test"""
    db_path = integration_temp_dir / "test.db"
    
    # Initialize database
    from pdsno.datastore import NIBStore
    nib = NIBStore(str(db_path))
    
    yield nib
    
    # Cleanup
    if db_path.exists():
        db_path.unlink()