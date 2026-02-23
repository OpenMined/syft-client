"""
VersionManager for managing version information and compatibility checks.
"""

import warnings
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, PrivateAttr

from syft_client.sync.connections.base_connection import ConnectionConfig
from syft_client.sync.connections.connection_router import ConnectionRouter
from syft_client.sync.peers.peer import Peer, PeerState
from syft_client.sync.platforms.gdrive_files_platform import GdriveFilesPlatform
from syft_client.sync.utils.print_utils import (
    print_peer_added,
    print_peer_added_to_platform,
    print_peer_adding_to_platform,
)
from syft_client.sync.version.exceptions import (
    VersionMismatchError,
    VersionUnknownError,
)
from syft_client.sync.version.version_info import VersionInfo


class VersionManagerConfig(BaseModel):
    """Configuration for VersionManager."""

    connection_configs: List[ConnectionConfig] = []
    ignore_protocol_version: bool = False
    ignore_client_version: bool = False
    suppress_version_warnings: bool = False
    n_threads: int = 10
    is_do: bool = False


class VersionManager(BaseModel):
    """Manages version information for self and peers."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    connection_router: ConnectionRouter
    ignore_protocol_version: bool = False
    ignore_client_version: bool = False
    suppress_version_warnings: bool = False
    n_threads: int = 10
    is_do: bool = False

    _own_version: Optional[VersionInfo] = PrivateAttr(default=None)
    _executor: Optional[ThreadPoolExecutor] = PrivateAttr(default=None)
    _peers: List[Peer] = PrivateAttr(default_factory=list)

    # ========== Peer List Properties ==========

    @property
    def approved_peers(self) -> List[Peer]:
        """Get all approved peers (DO side)."""
        return [p for p in self._peers if p.is_approved]

    @property
    def pending_peers(self) -> List[Peer]:
        """Get all pending peer requests (DO side)."""
        return [p for p in self._peers if p.is_pending]

    @property
    def outstanding_peers(self) -> List[Peer]:
        """Get all outstanding outgoing requests (DS side)."""
        return [p for p in self._peers if p.is_outstanding]

    @classmethod
    def from_config(cls, config: VersionManagerConfig) -> "VersionManager":
        """Create a VersionManager from a config."""
        return cls(
            connection_router=ConnectionRouter.from_configs(config.connection_configs),
            ignore_protocol_version=config.ignore_protocol_version,
            ignore_client_version=config.ignore_client_version,
            suppress_version_warnings=config.suppress_version_warnings,
            n_threads=config.n_threads,
            is_do=config.is_do,
        )

    def model_post_init(self, __context) -> None:
        """Initialize the thread pool executor."""
        self._executor = ThreadPoolExecutor(max_workers=self.n_threads)

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

    def get_cached_peer(self, email: str) -> Optional[Peer]:
        """Get a peer by email, or None if not found."""
        for p in self._peers:
            if p.email == email:
                return p
        return None

    def load_peer_version(self, peer_email: str) -> Optional[VersionInfo]:
        """Load version for a single peer (blocking)."""
        version_info = self.connection_router.read_peer_version_file(peer_email)
        cached_peer = self.get_cached_peer(peer_email)
        if cached_peer:
            cached_peer.version = version_info
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
        self, peer_emails: List[str], force: bool = False
    ) -> Dict[str, Optional[VersionInfo]]:
        """Load versions for multiple peers in parallel using internal executor."""

        if self.ignore_protocol_version and self.ignore_client_version and not force:
            return {}

        if not peer_emails:
            return {}

        # Submit all tasks and collect results
        results = list(self._executor.map(self._load_single_peer_version, peer_emails))

        # Update peer version fields and return
        for email, version in results:
            peer = self.get_cached_peer(email)
            if peer:
                peer.version = version

        return {email: version for email, version in results}

    def get_peer_version(self, peer_email: str) -> Optional[VersionInfo]:
        """Get cached version for peer, None if not loaded or not available."""
        peer = self.get_cached_peer(peer_email)
        return peer.version if peer else None

    def clear_peer_version(self, peer_email: str) -> None:
        """Clear the cached version for a peer (useful for testing)."""
        peer = self.get_cached_peer(peer_email)
        if peer:
            peer.version = None

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

        compatible = self.get_compatible_peer_emails(
            peer_emails, warn_incompatible=False
        )
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

    def check_version_for_job_execution(self, submitter_email: str) -> None:
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

    # ========== Peer Management Methods ==========

    def add_peer(self, peer_email: str, force: bool = False, verbose: bool = True):
        """
        Add a peer. For DS, creates a peer request. For DO, this is a no-op that auto-approves.

        Args:
            peer_email: Email of the peer to add
            force: If True, add even if peer already exists
            verbose: If True, print status messages
        """
        existing_peer = self.get_cached_peer(peer_email)
        if existing_peer and existing_peer.is_approved and not force:
            print(f"Peer {peer_email} already exists, skipping")
        else:
            if self.is_do:
                # this is a no-op for DOs
                platform = GdriveFilesPlatform()
                if verbose:
                    print_peer_adding_to_platform(peer_email, platform.module_path)
                    print_peer_added_to_platform(peer_email, platform.module_path)
                self.approve_peer_request(peer_email, verbose=False)
            else:
                peer = self.connection_router.add_peer_as_ds(peer_email=peer_email)
                # Set state to outstanding for DS
                peer.state = PeerState.OUTSTANDING
                # Share version file with the peer (DO)
                self.share_version_with_peer(peer_email)
                # Try to load the peer's version (may not be available yet if not approved)
                version_info = self.connection_router.read_peer_version_file(peer_email)
                peer.version = version_info
                # Add to peers list
                self._peers.append(peer)
                print_peer_added(peer)

    def load_peers(self):
        """Load peers from connection router based on role (DO or DS)."""
        peers = []
        if self.is_do:
            # Load approved peers
            for peer in self.connection_router.get_approved_peers_as_do():
                peer.state = PeerState.ACCEPTED
                peers.append(peer)
            # Load pending peer requests
            for peer in self.connection_router.get_peer_requests_as_do():
                peer.state = PeerState.PENDING
                peers.append(peer)
        else:
            # DS: load outstanding outgoing requests
            for peer in self.connection_router.get_peers_as_ds():
                peer.state = PeerState.OUTSTANDING
                peers.append(peer)

        self._peers = peers
        self.load_peer_versions_parallel([peer.email for peer in peers])

    def check_peer_request_exists(self, email: str) -> bool:
        """Check if a peer request exists for the given email."""
        return any(p.email == email for p in self.pending_peers)

    def approve_peer_request(
        self,
        email_or_peer: str | Peer,
        verbose: bool = True,
        peer_must_exist: bool = True,
    ):
        """
        Approve a pending peer request. DO only.

        Args:
            email_or_peer: Email string or Peer object to approve
            verbose: If True, print status messages
            peer_must_exist: If True, raise error if peer not in pending requests
        """
        if not self.is_do:
            raise ValueError("Only Data Owners can approve peer requests")

        email = email_or_peer if isinstance(email_or_peer, str) else email_or_peer.email

        # Early return if peer is already approved
        peer = self.get_cached_peer(email)
        if peer and peer.is_approved:
            if verbose:
                print(f"Peer {email} is already approved, skipping")
            return

        # Find peer in pending requests, reload cache if not found
        peer_is_pending = peer and peer.is_pending
        if not peer_is_pending:
            self.load_peers()
            peer = self.get_cached_peer(email)
            peer_is_pending = peer and peer.is_pending
        if peer_must_exist and not peer_is_pending:
            raise ValueError(
                f"Peer {email} not found in pending requests."
                f"Use client.peers to see current requests."
            )

        # Update state in GDrive
        self.connection_router.update_peer_state(email, PeerState.ACCEPTED.value)

        # Share version file with the approved peer (DS)
        self.share_version_with_peer(email)
        # Load the peer's version (DS should have shared it when they added us)
        version_info = self.connection_router.read_peer_version_file(email)

        if peer:
            # Update existing peer
            peer.state = PeerState.ACCEPTED
            peer.version = version_info
        else:
            # Create new peer if not found (peer_must_exist=False case)
            new_peer = Peer(
                email=email,
                platforms=[GdriveFilesPlatform()],
                state=PeerState.ACCEPTED,
                version=version_info,
            )
            self._peers.append(new_peer)

        if verbose:
            print(f"✓ Approved peer request from {email}")

    def reject_peer_request(self, email_or_peer: str | Peer):
        """
        Reject a pending peer request. DO only.

        Args:
            email_or_peer: Email string or Peer object to reject
        """
        if not self.is_do:
            raise ValueError("Only Data Owners can reject peer requests")

        email = email_or_peer if isinstance(email_or_peer, str) else email_or_peer.email

        # Find peer in pending requests
        peer = self.get_cached_peer(email)
        if not peer or not peer.is_pending:
            raise ValueError(
                f"Peer {email} not found in pending requests. "
                f"Use client.peers to see current requests."
            )

        # Update state in GDrive
        self.connection_router.update_peer_state(email, PeerState.REJECTED.value)

        # Update peer state to rejected
        peer.state = PeerState.REJECTED

        print(f"✗ Rejected peer request from {email}")
