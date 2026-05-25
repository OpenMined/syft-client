"""
Detect how syft-client was installed to determine the correct dependency string.

This module uses PEP 610 (direct_url.json) to determine if syft-client was installed
from a local directory, a git URL, or from PyPI.

See: https://packaging.python.org/en/latest/specifications/direct-url/
"""

import json
import logging
import os
from dataclasses import dataclass
from importlib.metadata import distributions
from typing import Optional

logger = logging.getLogger(__name__)

PACKAGE_NAME = "syft-client"
ENV_VAR_NAME = "SYFT_CLIENT_INSTALL_SOURCE"


@dataclass(frozen=True)
class InstallSpec:
    """Resolved syft-client install source.

    primary: The spec to install (e.g. ``syft-client==x.x.x``, a git URL, or
        a local directory path).
    pypi_fallback: Only set when ``primary`` is a local-directory path that
        may not exist on a remote runner. The generated
        ``run.sh`` falls back to this PyPI spec when the local path is missing.
    """

    primary: str
    pypi_fallback: Optional[str] = None


def _pypi_spec(version: Optional[str]) -> str:
    return f"{PACKAGE_NAME}=={version}" if version else PACKAGE_NAME


def _parse_direct_url(direct_url: dict, version: Optional[str]) -> InstallSpec:
    """
    Parse a direct_url.json content and return the pip-installable spec.

    Args:
        direct_url: Parsed direct_url.json content
        version: Installed package version (used to build the PyPI fallback
            when the install is a local directory).

    Returns:
        An ``InstallSpec`` suitable for pip/uv install. ``pypi_fallback`` is
        set only for local-directory installs.
    """
    url = direct_url.get("url", "")

    # VCS install (git, hg, svn, bzr)
    if "vcs_info" in direct_url:
        vcs_info = direct_url["vcs_info"]
        vcs = vcs_info.get("vcs", "git")

        # Get the revision to pin to
        revision = vcs_info.get("requested_revision") or vcs_info.get("commit_id")

        if revision:
            return InstallSpec(primary=f"{vcs}+{url}@{revision}")
        return InstallSpec(primary=f"{vcs}+{url}")

    # Local directory install (editable or not). Capture a PyPI fallback so
    # that a generated run.sh can recover when the local path doesn't exist
    # on the runner machine.
    if "dir_info" in direct_url:
        local_path = url[7:] if url.startswith("file://") else url
        return InstallSpec(primary=local_path, pypi_fallback=_pypi_spec(version))

    # Archive URL install
    if "archive_info" in direct_url:
        return InstallSpec(primary=url)

    # Fallback: return the URL as-is
    return InstallSpec(primary=url)


def _find_syft_client_info() -> tuple[dict | None, str | None]:
    """
    Find the direct_url.json content and version for syft-client.

    Returns:
        Tuple of (direct_url dict or None, version string or None)
    """
    version = None

    for dist in distributions():
        # try except because some distributions may not have a name and it raises
        try:
            if dist.name != PACKAGE_NAME:
                continue
        except Exception:
            continue

        # Always capture the version
        if version is None:
            version = dist.version

        try:
            content = dist.read_text("direct_url.json")
            if content:
                return json.loads(content), version
        except FileNotFoundError:
            # This distribution doesn't have direct_url.json, try next
            continue
        except json.JSONDecodeError:
            continue

    return None, version


def get_syft_client_install_source() -> InstallSpec:
    """
    Determine how syft-client was installed and return the appropriate install spec.

    Priority:
    1. Environment variable override (SYFT_CLIENT_INSTALL_SOURCE)
    2. Auto-detection from package metadata (direct_url.json)
    3. Fallback to PyPI package name with version

    Returns:
        An ``InstallSpec`` whose ``primary`` field is suitable for pip/uv
        install. ``pypi_fallback`` is set only when ``primary`` is a local
        directory path (so callers can emit a portable run.sh).
    """
    # Check for environment variable override
    env_override = os.environ.get(ENV_VAR_NAME)
    if env_override:
        return InstallSpec(primary=env_override)

    # Try to detect from package metadata
    direct_url, version = _find_syft_client_info()
    if direct_url:
        return _parse_direct_url(direct_url, version)

    # Fallback to PyPI package name with version
    if version:
        return InstallSpec(primary=_pypi_spec(version))

    logger.warning(
        f"Could not detect syft-client installation source or version. "
        f"Falling back to '{PACKAGE_NAME}'. "
        f"Jobs may fail if syft-client is not available on PyPI."
    )
    return InstallSpec(primary=PACKAGE_NAME)
