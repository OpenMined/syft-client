"""
VersionInfo model for representing version information.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from syft_client.version import (
    MIN_SUPPORTED_PROTOCOL_VERSION,
    MIN_SUPPORTED_SYFT_CLIENT_VERSION,
    PROTOCOL_VERSION,
    SYFT_CLIENT_VERSION,
)


class CompatibilityStatus(str, Enum):
    """Outcome of comparing two VersionInfo objects."""

    SAME = "same"
    PATCH_DIFF = "patch_diff"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


def _parse_semver(version_str: str) -> Optional[tuple[int, int, int]]:
    """Parse 'X.Y.Z' into (major, minor, patch). Return None if not parseable."""
    parts = version_str.split(".")
    if len(parts) < 3:
        return None
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


class VersionInfo(BaseModel):
    """Model representing version information for a syft client."""

    syft_client_version: str
    min_supported_syft_client_version: str
    protocol_version: str
    min_supported_protocol_version: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def compatibility_status_with(
        self, other: "VersionInfo" | None
    ) -> CompatibilityStatus:
        """Compare syft_client_version against another VersionInfo."""
        if other is None:
            return CompatibilityStatus.UNKNOWN

        if self.syft_client_version == other.syft_client_version:
            return CompatibilityStatus.SAME

        local = _parse_semver(self.syft_client_version)
        peer = _parse_semver(other.syft_client_version)
        if local is None or peer is None:
            return CompatibilityStatus.INCOMPATIBLE

        if local[0] == peer[0] and local[1] == peer[1]:
            return CompatibilityStatus.PATCH_DIFF

        return CompatibilityStatus.INCOMPATIBLE

    def is_compatible_with(self, other: "VersionInfo" | None) -> bool:
        """True if SAME or PATCH_DIFF (patch differences are non-blocking)."""
        status = self.compatibility_status_with(other)
        return status in (CompatibilityStatus.SAME, CompatibilityStatus.PATCH_DIFF)

    def get_incompatibility_reason(self, other: "VersionInfo") -> Optional[str]:
        """Reason string when minor/major mismatch; None for SAME or PATCH_DIFF."""
        status = self.compatibility_status_with(other)
        if status in (CompatibilityStatus.SAME, CompatibilityStatus.PATCH_DIFF):
            return None
        return (
            f"Client version mismatch (minor or major): "
            f"local={self.syft_client_version}, peer={other.syft_client_version}"
        )

    def get_patch_warning_text(self, other: "VersionInfo") -> Optional[str]:
        """Warning string when only patch versions differ."""
        status = self.compatibility_status_with(other)
        if status != CompatibilityStatus.PATCH_DIFF:
            return None
        return (
            f"Client version differs by patch only: "
            f"local={self.syft_client_version}, peer={other.syft_client_version} "
            f"— proceeding"
        )

    @classmethod
    def current(cls) -> "VersionInfo":
        """Create VersionInfo with current version constants."""
        return cls(
            syft_client_version=SYFT_CLIENT_VERSION,
            min_supported_syft_client_version=MIN_SUPPORTED_SYFT_CLIENT_VERSION,
            protocol_version=PROTOCOL_VERSION,
            min_supported_protocol_version=MIN_SUPPORTED_PROTOCOL_VERSION,
        )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "VersionInfo":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)
