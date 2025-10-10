"""
Transport capabilities and requirements system
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class TransportCapabilities:
    """Describes what a transport can do"""

    transport_name: str  # "gdrive_files", "gsheets", "gmail", etc.

    # Size constraints
    max_file_size: Optional[int] = None  # Max size in bytes, None = unlimited
    max_message_size: Optional[int] = None  # Total message size limit

    # Performance characteristics
    typical_latency_ms: int = 1000  # Typical latency in milliseconds
    min_latency_ms: int = 100  # Best case latency
    max_latency_ms: int = 60000  # Worst case latency

    # Features
    supports_batch: bool = False  # Can send multiple files at once
    supports_deletion: bool = False  # Can send deletion messages
    supports_streaming: bool = False  # Can stream large files
    requires_recipient_setup: bool = True  # Recipient needs special setup

    # Requirements
    requires_auth: List[str] = field(default_factory=list)  # Auth scopes needed
    platform_required: Optional[str] = None  # Specific platform requirement


# Registry of known transport capabilities
TRANSPORT_CAPABILITIES = {
    "gdrive_files": TransportCapabilities(
        transport_name="gdrive_files",
        max_file_size=None,  # Effectively unlimited
        typical_latency_ms=3000,  # 3 seconds typical
        min_latency_ms=1000,
        max_latency_ms=30000,
        supports_batch=True,
        supports_deletion=True,
        requires_auth=["https://www.googleapis.com/auth/drive"],
        platform_required="google",
    ),
    "gsheets": TransportCapabilities(
        transport_name="gsheets",
        max_file_size=37_500,  # ~37.5KB before base64 encoding
        max_message_size=50_000,  # Total message must fit in cell
        typical_latency_ms=500,  # Very fast for small files
        min_latency_ms=200,
        max_latency_ms=2000,
        supports_batch=False,  # One file at a time
        supports_deletion=True,
        requires_auth=["https://www.googleapis.com/auth/spreadsheets"],
        platform_required="google",
    ),
    "gmail": TransportCapabilities(
        transport_name="gmail",
        max_file_size=25 * 1024 * 1024,  # 25MB attachment limit
        typical_latency_ms=2000,
        min_latency_ms=500,
        max_latency_ms=10000,
        supports_batch=True,  # Multiple attachments
        supports_deletion=False,  # Email can't delete files
        requires_auth=["https://www.googleapis.com/auth/gmail.send"],
        platform_required="google",
    ),
    "dropbox": TransportCapabilities(
        transport_name="dropbox",
        max_file_size=None,  # Effectively unlimited
        typical_latency_ms=4000,
        min_latency_ms=2000,
        max_latency_ms=60000,
        supports_batch=True,
        supports_deletion=True,
        requires_auth=["files.content.write"],
        platform_required="dropbox",
    ),
    "onedrive": TransportCapabilities(
        transport_name="onedrive",
        max_file_size=250 * 1024 * 1024 * 1024,  # 250GB per file
        typical_latency_ms=3500,
        min_latency_ms=1500,
        max_latency_ms=45000,
        supports_batch=True,
        supports_deletion=True,
        requires_auth=["Files.ReadWrite.All"],
        platform_required="microsoft",
    ),
}


@dataclass
class TransportRequirements:
    """Requirements for a specific send operation"""

    file_size: int  # Size in bytes
    requested_latency_ms: Optional[int] = None  # Desired latency, None = best effort
    requires_deletion_support: bool = False
    requires_batch: bool = False
    priority: str = "normal"  # "urgent", "normal", "background"

    def matches_capabilities(self, capabilities: TransportCapabilities) -> bool:
        """Check if requirements can be met by transport capabilities"""
        # Check file size
        if capabilities.max_file_size and self.file_size > capabilities.max_file_size:
            return False

        # Check latency requirements
        if (
            self.requested_latency_ms
            and capabilities.typical_latency_ms > self.requested_latency_ms
        ):
            return False

        # Check deletion support
        if self.requires_deletion_support and not capabilities.supports_deletion:
            return False

        # Check batch support
        if self.requires_batch and not capabilities.supports_batch:
            return False

        return True


def get_transport_capabilities(transport_name: str) -> Optional[TransportCapabilities]:
    """Get capabilities for a transport by name"""
    return TRANSPORT_CAPABILITIES.get(transport_name)


def list_compatible_transports(requirements: TransportRequirements) -> List[str]:
    """List all transports that meet the given requirements"""
    compatible = []
    for name, capabilities in TRANSPORT_CAPABILITIES.items():
        if requirements.matches_capabilities(capabilities):
            compatible.append(name)
    return compatible


__all__ = [
    "TransportCapabilities",
    "TransportRequirements",
    "TRANSPORT_CAPABILITIES",
    "get_transport_capabilities",
    "list_compatible_transports",
]
