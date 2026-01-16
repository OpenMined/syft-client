"""
VersionInfo model for representing version information.
"""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from syft_client.version import (
    MIN_SUPPORTED_PROTOCOL_VERSION,
    MIN_SUPPORTED_SYFT_CLIENT_VERSION,
    PROTOCOL_VERSION,
    SYFT_CLIENT_VERSION,
)


class VersionInfo(BaseModel):
    """Model representing version information for a syft client."""

    syft_client_version: str
    min_supported_syft_client_version: str
    protocol_version: str
    min_supported_protocol_version: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def is_compatible_with(
        self,
        other: "VersionInfo",
        check_client: bool = True,
        check_protocol: bool = True,
    ) -> bool:
        """
        Check if this version is compatible with another version.

        Currently requires exact match for both client and protocol versions.
        Future: can support range-based compatibility using min_supported_* fields.

        Args:
            other: The other VersionInfo to check compatibility with
            check_client: Whether to check client version compatibility
            check_protocol: Whether to check protocol version compatibility

        Returns:
            True if versions are compatible, False otherwise
        """
        if check_protocol:
            if self.protocol_version != other.protocol_version:
                return False

        if check_client:
            if self.syft_client_version != other.syft_client_version:
                return False

        return True

    def get_incompatibility_reason(
        self,
        other: "VersionInfo",
        check_client: bool = True,
        check_protocol: bool = True,
    ) -> Optional[str]:
        """
        Get the reason why two versions are incompatible.

        Args:
            other: The other VersionInfo to check compatibility with
            check_client: Whether to check client version compatibility
            check_protocol: Whether to check protocol version compatibility

        Returns:
            A string describing the incompatibility, or None if compatible
        """
        reasons = []

        if check_protocol and self.protocol_version != other.protocol_version:
            reasons.append(
                f"Protocol version mismatch: local={self.protocol_version}, "
                f"peer={other.protocol_version}"
            )

        if check_client and self.syft_client_version != other.syft_client_version:
            reasons.append(
                f"Client version mismatch: local={self.syft_client_version}, "
                f"peer={other.syft_client_version}"
            )

        if reasons:
            return "; ".join(reasons)
        return None

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
