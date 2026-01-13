"""
Pytest configuration for all tests.

This file is automatically loaded by pytest and configures the test environment.
"""

import os
from pathlib import Path

import pytest

# Store original value before any modifications
_original_syft_client_install_source = os.environ.get("SYFT_CLIENT_INSTALL_SOURCE")


def pytest_configure(config):
    """
    Set SYFT_CLIENT_INSTALL_SOURCE BEFORE any test modules are imported.

    This hook runs before pytest collects tests, which means it runs
    before test modules are imported. This is critical because
    syft_job.client reads SYFT_CLIENT_INSTALL_SOURCE at module import time.

    Using a fixture doesn't work because fixtures run after imports.
    """
    repo_root = Path(__file__).parent.parent.resolve()
    os.environ["SYFT_CLIENT_INSTALL_SOURCE"] = str(repo_root)


def pytest_unconfigure(config):
    """
    Restore original SYFT_CLIENT_INSTALL_SOURCE value after all tests.
    """
    if _original_syft_client_install_source is not None:
        os.environ["SYFT_CLIENT_INSTALL_SOURCE"] = _original_syft_client_install_source
    else:
        os.environ.pop("SYFT_CLIENT_INSTALL_SOURCE", None)


@pytest.fixture(scope="session", autouse=True)
def disable_pre_sync_for_tests():
    """
    Disable PRE_SYNC by default for all tests.

    PRE_SYNC is enabled by default in production, but for tests we want
    explicit control over when sync() is called to avoid unexpected behavior
    and make tests faster.

    Individual tests can override this by setting os.environ["PRE_SYNC"] = "true"
    if they specifically want to test the auto-sync behavior.
    """
    original_value = os.environ.get("PRE_SYNC")
    os.environ["PRE_SYNC"] = "false"

    yield

    # Restore original value after all tests
    if original_value is not None:
        os.environ["PRE_SYNC"] = original_value
    else:
        os.environ.pop("PRE_SYNC", None)
