import pytest
from syft_process_manager import ProcessManager


@pytest.fixture
def process_manager(tmp_path):
    """ProcessManager instance with temporary directory for testing."""
    pm_dir = tmp_path / "syft-pm-test"
    return ProcessManager(dir=pm_dir)
