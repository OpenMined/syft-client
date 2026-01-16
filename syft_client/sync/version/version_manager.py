"""
VersionManager for managing version information and compatibility checks.
"""

import warnings
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, PrivateAttr

from syft_client.sync.connections.connection_router import ConnectionRouter
from syft_client.sync.version.exceptions import (
    VersionMismatchError,
    VersionUnknownError,
)
from syft_client.sync.version.version_info import VersionInfo


class VersionManager(BaseModel):
    """Manages version information for self and peers."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    connection_router: ConnectionRouter
    ignore_protocol_version: bool = False
    ignore_client_version: bool = False
    suppress_version_warnings: bool = False

    _own_version: Optional[VersionInfo] = PrivateAttr(default=None)
    _peer_versions: Dict[str, Optional[VersionInfo]] = PrivateAttr(default_factory=dict)
    _executor: Optional[ThreadPoolExecutor] = PrivateAttr(default=None)
    _test_mode: bool = PrivateAttr(default=False)

    def model_post_init(self, __context) -> None:
        """Initialize the thread pool executor."""
        max_workers = 2 if self._test_mode else 10
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def get_own_version(self) -> VersionInfo:
        """Get current client's version info."""
        if self._own_version is None:
            self._own_version = VersionInfo.current()
        return self._own_version

    def write_own_version(self) -> None:
        """Write version file to own SyftBox folder."""
        version_info = self.get_own_version()
        self.connection_router.write_version_file(version_info)

    def share_version_with_peer(self, peer_email: str) -> None:
        """Share version file with a peer so they can read it."""
        self.connection_router.share_version_file_with_peer(peer_email)

    def load_peer_version(self, peer_email: str) -> Optional[VersionInfo]:
        """Load version for a single peer (blocking)."""
        version_info = self.connection_router.read_peer_version_file(peer_email)
        self._peer_versions[peer_email] = version_info
        return version_info

    def _load_single_peer_version(
        self, peer_email: str
    ) -> tuple[str, Optional[VersionInfo]]:
        """Load version for a single peer. Used by parallel loader."""
        try:
            # Create new connection for thread safety
            connection = self.connection_router.connection_for_version_read(
                create_new=True
            )
            version_info = connection.read_peer_version_file(peer_email)
            return (peer_email, version_info)
        except Exception as e:
            if not self.suppress_version_warnings:
                warnings.warn(f"Failed to load version for {peer_email}: {e}")
            return (peer_email, None)

    def load_peer_versions_parallel(
        self, peer_emails: List[str]
    ) -> Dict[str, Optional[VersionInfo]]:
        """Load versions for multiple peers in parallel using internal executor."""
        if not peer_emails:
            return {}

        # Submit all tasks and collect results
        results = list(self._executor.map(self._load_single_peer_version, peer_emails))

        # Update cache and return
        for email, version in results:
            self._peer_versions[email] = version

        return {email: version for email, version in results}

    def get_peer_version(self, peer_email: str) -> Optional[VersionInfo]:
        """Get cached version for peer, None if not loaded or not available."""
        return self._peer_versions.get(peer_email)

    def is_peer_version_compatible(self, peer_email: str) -> bool:
        """
        Check if peer version is compatible with current client.

        Returns True if:
        - Both version checks are ignored
        - Peer version is known and compatible
        """
        if self.ignore_protocol_version and self.ignore_client_version:
            return True

        peer_version = self.get_peer_version(peer_email)
        if peer_version is None:
            return False

        return self.get_own_version().is_compatible_with(
            peer_version,
            check_client=not self.ignore_client_version,
            check_protocol=not self.ignore_protocol_version,
        )

    def check_version_compatibility(
        self,
        peer_email: str,
        operation: Optional[str] = None,
        raise_on_mismatch: bool = True,
        raise_on_unknown: bool = True,
    ) -> bool:
        """
        Check if peer version is compatible.

        Args:
            peer_email: The peer to check
            operation: Description of the operation for error messages
            raise_on_mismatch: Raise VersionMismatchError if incompatible
            raise_on_unknown: Raise VersionUnknownError if peer version unknown

        Returns:
            True if compatible, False otherwise

        Raises:
            VersionUnknownError: If peer version is unknown and raise_on_unknown=True
            VersionMismatchError: If versions don't match and raise_on_mismatch=True
        """
        if self.ignore_protocol_version and self.ignore_client_version:
            return True

        peer_version = self.get_peer_version(peer_email)

        if peer_version is None:
            if raise_on_unknown:
                raise VersionUnknownError(peer_email, operation)
            return False

        own_version = self.get_own_version()
        is_compatible = own_version.is_compatible_with(
            peer_version,
            check_client=not self.ignore_client_version,
            check_protocol=not self.ignore_protocol_version,
        )

        if not is_compatible and raise_on_mismatch:
            reason = own_version.get_incompatibility_reason(
                peer_version,
                check_client=not self.ignore_client_version,
                check_protocol=not self.ignore_protocol_version,
            )
            raise VersionMismatchError(peer_email, own_version, peer_version, reason)

        return is_compatible

    def get_compatible_peer_emails(
        self, peer_emails: List[str], warn_incompatible: bool = True
    ) -> List[str]:
        """
        Filter peer emails to only those with compatible versions.

        Args:
            peer_emails: List of peer emails to filter
            warn_incompatible: Whether to warn about incompatible peers

        Returns:
            List of peer emails with compatible versions
        """
        if self.ignore_protocol_version and self.ignore_client_version:
            return peer_emails

        compatible = []
        for email in peer_emails:
            if self.is_peer_version_compatible(email):
                compatible.append(email)
            elif warn_incompatible and not self.suppress_version_warnings:
                peer_version = self.get_peer_version(email)
                if peer_version is None:
                    warnings.warn(
                        f"Skipping peer {email}: version information not available."
                    )
                else:
                    own_version = self.get_own_version()
                    reason = own_version.get_incompatibility_reason(
                        peer_version,
                        check_client=not self.ignore_client_version,
                        check_protocol=not self.ignore_protocol_version,
                    )
                    warnings.warn(f"Skipping peer {email}: {reason}")

        return compatible

    def warn_if_all_peers_incompatible(self, peer_emails: List[str]) -> None:
        """
        Warn if all connected peers are incompatible (used by DS during sync).
        """
        if self.suppress_version_warnings:
            return

        if self.ignore_protocol_version and self.ignore_client_version:
            return

        if not peer_emails:
            return

        compatible = self.get_compatible_peer_emails(peer_emails, warn_incompatible=False)
        if not compatible:
            warnings.warn(
                f"All connected peers ({len(peer_emails)}) have incompatible versions. "
                "You may not be able to submit jobs or load datasets until versions match."
            )

    def check_version_for_submission(
        self, peer_email: str, force: bool = False
    ) -> None:
        """
        Check version before job submission (DS side).

        Args:
            peer_email: The DO peer email
            force: If True, skip version check

        Raises:
            VersionUnknownError: If DO version is unknown
            VersionMismatchError: If versions don't match
        """
        if force:
            return

        # Load the peer version if not already cached
        if self.get_peer_version(peer_email) is None:
            self.load_peer_version(peer_email)

        self.check_version_compatibility(
            peer_email,
            operation="submit job",
            raise_on_mismatch=True,
            raise_on_unknown=True,
        )

    def check_version_for_job_execution(
        self, submitter_email: str
    ) -> None:
        """
        Check version before job execution (DO side).

        Args:
            submitter_email: The DS who submitted the job

        Raises:
            VersionUnknownError: If DS version is unknown
            VersionMismatchError: If versions don't match
        """
        self.check_version_compatibility(
            submitter_email,
            operation="execute job",
            raise_on_mismatch=True,
            raise_on_unknown=True,
        )

    def shutdown(self) -> None:
        """Shutdown the thread pool executor."""
        if self._executor:
            self._executor.shutdown(wait=False)
