"""
Pytest configuration for all tests.

This file is automatically loaded by pytest and configures the test environment.
"""

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def use_local_syft_client_for_jobs():
    """
    Use local syft-client code instead of PyPI for job submissions.

    When jobs are submitted, they install syft-client as a dependency.
    By default, this installs from PyPI, but for testing we want to use
    the local code to test our changes.

    This sets SYFT_CLIENT_INSTALL_SOURCE to the repo root path.
    """
    # Get repo root (tests/ -> syft-client/)
    repo_root = Path(__file__).parent.parent.resolve()
    original_value = os.environ.get("SYFT_CLIENT_INSTALL_SOURCE")
    os.environ["SYFT_CLIENT_INSTALL_SOURCE"] = str(repo_root)

    yield

    # Restore original value after all tests
    if original_value is not None:
        os.environ["SYFT_CLIENT_INSTALL_SOURCE"] = original_value
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
