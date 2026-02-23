"""
Version constants for syft-client.
Single source of truth for all version strings.
Bump these versions on each release (via `bump2version patch/minor/major`).
"""

# Current client version — the single source of truth.
# pyproject.toml and syft_client/__init__.py read from here.
SYFT_CLIENT_VERSION = "0.1.100"

# Minimum client version we support communicating with
MIN_SUPPORTED_SYFT_CLIENT_VERSION = "0.1.93"

# Protocol version - bump when making breaking changes to the sync protocol
PROTOCOL_VERSION = "1.0.0"

# Minimum protocol version we support
MIN_SUPPORTED_PROTOCOL_VERSION = "1.0.0"

# Name of the version file stored in SyftBox folder
VERSION_FILE_NAME = "SYFT_version.json"
