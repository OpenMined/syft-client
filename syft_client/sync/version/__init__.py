"""
Version negotiation module for syft-client.

Note: VersionManager is not exported here to avoid circular imports.
Import it directly: from syft_client.sync.version.version_manager import VersionManager
"""

from syft_client.sync.version.version_info import VersionInfo
from syft_client.sync.version.exceptions import (
    VersionError,
    VersionMismatchError,
    VersionUnknownError,
    ClientVersionMismatchError,
    ProtocolVersionMismatchError,
)

__all__ = [
    "VersionInfo",
    "VersionError",
    "VersionMismatchError",
    "VersionUnknownError",
    "ClientVersionMismatchError",
    "ProtocolVersionMismatchError",
]
