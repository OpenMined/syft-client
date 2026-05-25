"""
Tests for detecting syft-client installation source.

These tests verify that we can correctly determine how syft-client was installed:
- Editable install from local directory
- Non-editable install from local directory
- Install from PyPI
- Install from GitHub URL
- Override via environment variable
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest  # noqa: F401


class MockDistribution:
    """Mock distribution for testing."""

    def __init__(
        self,
        name: str,
        path: str,
        direct_url: dict | None = None,
        version: str = "0.1.94",
    ):
        self.name = name
        self._path = path
        self._direct_url = direct_url
        self.version = version

    def read_text(self, filename: str) -> str:
        if filename == "direct_url.json" and self._direct_url:
            return json.dumps(self._direct_url)
        raise FileNotFoundError(f"{filename} not found")


def create_mock_distributions(*dists):
    """Create a mock distributions() function that returns the given distributions."""

    def mock_distributions():
        return iter(dists)

    return mock_distributions


class TestGetInstallSource:
    """Tests for get_syft_client_install_source function."""

    def test_env_var_override_takes_precedence(self):
        """Environment variable should override all other detection methods."""
        from syft_job.install_source import get_syft_client_install_source

        with patch.dict(os.environ, {"SYFT_CLIENT_INSTALL_SOURCE": "/custom/path"}):
            result = get_syft_client_install_source()
            assert result.primary == "/custom/path"
            assert result.pypi_fallback is None

    def test_editable_install_returns_local_path(self):
        """Editable install should return the local directory path and a PyPI fallback."""
        from syft_job.install_source import get_syft_client_install_source

        mock_dist = MockDistribution(
            name="syft-client",
            path="/path/to/site-packages/syft_client-0.1.94.dist-info",
            direct_url={
                "url": "file:///Users/test/workspace/syft-client",
                "dir_info": {"editable": True},
            },
        )

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SYFT_CLIENT_INSTALL_SOURCE", None)
            with patch(
                "syft_job.install_source.distributions",
                create_mock_distributions(mock_dist),
            ):
                result = get_syft_client_install_source()
                assert result.primary == "/Users/test/workspace/syft-client"
                assert result.pypi_fallback == "syft-client==0.1.94"

    def test_local_non_editable_install_returns_path(self):
        """Non-editable local install should return the local directory path and a PyPI fallback."""
        from syft_job.install_source import get_syft_client_install_source

        mock_dist = MockDistribution(
            name="syft-client",
            path="/path/to/site-packages/syft_client-0.1.94.dist-info",
            direct_url={
                "url": "file:///Users/test/workspace/syft-client",
                "dir_info": {},  # No editable flag
            },
        )

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SYFT_CLIENT_INSTALL_SOURCE", None)
            with patch(
                "syft_job.install_source.distributions",
                create_mock_distributions(mock_dist),
            ):
                result = get_syft_client_install_source()
                assert result.primary == "/Users/test/workspace/syft-client"
                assert result.pypi_fallback == "syft-client==0.1.94"

    def test_github_install_returns_git_url(self):
        """GitHub install should return the git+ URL with branch."""
        from syft_job.install_source import get_syft_client_install_source

        mock_dist = MockDistribution(
            name="syft-client",
            path="/path/to/site-packages/syft_client-0.1.94.dist-info",
            direct_url={
                "url": "https://github.com/OpenMined/syft-client",
                "vcs_info": {
                    "vcs": "git",
                    "commit_id": "abc123def456",
                    "requested_revision": "main",
                },
            },
        )

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SYFT_CLIENT_INSTALL_SOURCE", None)
            with patch(
                "syft_job.install_source.distributions",
                create_mock_distributions(mock_dist),
            ):
                result = get_syft_client_install_source()
                assert (
                    result.primary
                    == "git+https://github.com/OpenMined/syft-client@main"
                )
                assert result.pypi_fallback is None

    def test_github_install_with_branch(self):
        """GitHub install with specific branch should include branch in URL."""
        from syft_job.install_source import get_syft_client_install_source

        mock_dist = MockDistribution(
            name="syft-client",
            path="/path/to/site-packages/syft_client-0.1.94.dist-info",
            direct_url={
                "url": "https://github.com/OpenMined/syft-client.git",
                "vcs_info": {
                    "vcs": "git",
                    "commit_id": "abc123def456",
                    "requested_revision": "feature/new-stuff",
                },
            },
        )

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SYFT_CLIENT_INSTALL_SOURCE", None)
            with patch(
                "syft_job.install_source.distributions",
                create_mock_distributions(mock_dist),
            ):
                result = get_syft_client_install_source()
                assert (
                    result.primary
                    == "git+https://github.com/OpenMined/syft-client.git@feature/new-stuff"
                )
                assert result.pypi_fallback is None

    def test_github_install_without_branch_uses_commit(self):
        """GitHub install without requested_revision should use commit_id."""
        from syft_job.install_source import get_syft_client_install_source

        mock_dist = MockDistribution(
            name="syft-client",
            path="/path/to/site-packages/syft_client-0.1.94.dist-info",
            direct_url={
                "url": "https://github.com/OpenMined/syft-client",
                "vcs_info": {
                    "vcs": "git",
                    "commit_id": "abc123def456",
                },
            },
        )

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SYFT_CLIENT_INSTALL_SOURCE", None)
            with patch(
                "syft_job.install_source.distributions",
                create_mock_distributions(mock_dist),
            ):
                result = get_syft_client_install_source()
                assert (
                    result.primary
                    == "git+https://github.com/OpenMined/syft-client@abc123def456"
                )
                assert result.pypi_fallback is None

    def test_pypi_install_returns_package_name_with_version(self):
        """PyPI install (no direct_url.json) should return package name with version."""
        from syft_job.install_source import get_syft_client_install_source

        mock_dist = MockDistribution(
            name="syft-client",
            path="/path/to/site-packages/syft_client-0.1.94.dist-info",
            direct_url=None,  # No direct_url.json for PyPI installs
            version="0.1.94",
        )

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SYFT_CLIENT_INSTALL_SOURCE", None)
            with patch(
                "syft_job.install_source.distributions",
                create_mock_distributions(mock_dist),
            ):
                result = get_syft_client_install_source()
                assert result.primary == "syft-client==0.1.94"
                assert result.pypi_fallback is None

    def test_no_package_found_returns_pypi_name_without_version_and_warns(self, caplog):
        """When syft-client is not installed, fall back to PyPI name and log a warning."""
        import logging

        from syft_job.install_source import get_syft_client_install_source

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SYFT_CLIENT_INSTALL_SOURCE", None)
            with patch(
                "syft_job.install_source.distributions",
                create_mock_distributions(),  # No distributions
            ):
                with caplog.at_level(logging.WARNING):
                    result = get_syft_client_install_source()

                assert result.primary == "syft-client"
                assert result.pypi_fallback is None
                assert "Could not detect syft-client installation source" in caplog.text
                assert "Falling back to" in caplog.text

    def test_multiple_distributions_finds_dist_info(self):
        """When both egg-info and dist-info exist, use dist-info with direct_url."""
        from syft_job.install_source import get_syft_client_install_source

        # Egg-info without direct_url.json (older format)
        mock_egg_info = MockDistribution(
            name="syft-client",
            path="syft_client.egg-info",
            direct_url=None,
        )

        # Dist-info with direct_url.json (newer format)
        mock_dist_info = MockDistribution(
            name="syft-client",
            path="/path/to/site-packages/syft_client-0.1.94.dist-info",
            direct_url={
                "url": "file:///Users/test/workspace/syft-client",
                "dir_info": {"editable": True},
            },
        )

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SYFT_CLIENT_INSTALL_SOURCE", None)
            with patch(
                "syft_job.install_source.distributions",
                create_mock_distributions(mock_egg_info, mock_dist_info),
            ):
                result = get_syft_client_install_source()
                assert result.primary == "/Users/test/workspace/syft-client"
                assert result.pypi_fallback == "syft-client==0.1.94"


class TestGetInstallSourceCurrentEnvironment:
    """Test that we can detect the current environment's install source."""

    def test_current_environment_detection(self):
        """
        Test that the function works in the current environment.

        This test verifies that our detection logic actually works with
        real installed packages, not just mocks.
        """
        from syft_job.install_source import get_syft_client_install_source

        # Clear the env var to test auto-detection
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SYFT_CLIENT_INSTALL_SOURCE", None)
            result = get_syft_client_install_source()

            # The result should have a non-empty primary spec
            assert isinstance(result.primary, str)
            assert len(result.primary) > 0

            # In this test environment (editable install), primary is a path
            # and pypi_fallback should be set.
            if Path(result.primary).exists():
                # Check it looks like the syft-client repo
                assert Path(result.primary).is_dir()
                # Should contain syft_client package
                assert (Path(result.primary) / "syft_client").exists() or (
                    Path(result.primary) / "pyproject.toml"
                ).exists()
                # Editable / local installs should always carry a PyPI fallback
                assert result.pypi_fallback is not None


class TestRuntimeEvaluation:
    """Test that install source is evaluated at runtime, not import time."""

    def test_install_source_respects_env_var_change_after_import(self):
        """
        Verify that changing the env var after import affects the result.

        This confirms that the install source is evaluated at call time,
        not at module import time, so tests and runtime code can override
        the source without needing to reload modules.
        """
        from syft_job.install_source import get_syft_client_install_source

        # First, check with no env var
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SYFT_CLIENT_INSTALL_SOURCE", None)
            result_without_env = get_syft_client_install_source()

        # Now set an env var and verify it's respected
        with patch.dict(os.environ, {"SYFT_CLIENT_INSTALL_SOURCE": "/new/test/path"}):
            result_with_env = get_syft_client_install_source()
            assert result_with_env.primary == "/new/test/path"
            assert result_with_env.pypi_fallback is None

        # The results should be different (env var overrides auto-detection)
        assert result_without_env.primary != result_with_env.primary
