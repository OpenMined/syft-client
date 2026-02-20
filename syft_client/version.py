"""
Version constants for syft-client.
Bump these versions on each release.

NOTE: SYFT_CLIENT_VERSION must be kept in sync with __version__ in syft_client/__init__.py
"""

# Current client version
# Keep in sync with __version__ in syft_client/__init__.py and pyproject.toml
SYFT_CLIENT_VERSION = "0.1.99"

# Minimum client version we support communicating with
MIN_SUPPORTED_SYFT_CLIENT_VERSION = "0.1.93"

# Protocol version - bump when making breaking changes to the sync protocol
PROTOCOL_VERSION = "1.0.0"

# Minimum protocol version we support
MIN_SUPPORTED_PROTOCOL_VERSION = "1.0.0"

# Name of the version file stored in SyftBox folder
VERSION_FILE_NAME = "SYFT_version.json"
