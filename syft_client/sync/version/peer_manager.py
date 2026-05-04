"""
PeerManager for managing peers, version information, and compatibility checks.
"""

import json
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, PrivateAttr

from syft_client.sync.connections.base_connection import ConnectionConfig
from syft_client.sync.connections.connection_router import ConnectionRouter
from syft_client.sync.peers.peer import Peer, PeerState
from syft_client.sync.peers.peer_store import PeerStore
from syft_client.sync.utils.print_utils import (
    print_peer_already_connected,
    print_peer_connection_established,
    print_peer_request_accepting,
    print_peer_request_resending,
    print_peer_request_sending,
    print_peer_request_sent,
)
from syft_client.sync.version.exceptions import (
    VersionMismatchError,
    VersionUnknownError,
)
from syft_client.sync.version.version_info import VersionInfo


class PeerManagerConfig(BaseModel):
    """Configuration for PeerManager."""

    syftbox_folder: Path
    connection_configs: List[ConnectionConfig] = []
    ignore_protocol_version: bool = False
    ignore_client_version: bool = False
    suppress_version_warnings: bool = False
    n_threads: int = 10
    has_do_role: bool = False
    has_ds_role: bool = False
    use_encryption: bool = False


class PeerManager(BaseModel):
    """Manages version information for self and peers."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    syftbox_folder: Path
    connection_router: ConnectionRouter
    peer_store: PeerStore
    ignore_protocol_version: bool = False
    ignore_client_version: bool = False
    suppress_version_warnings: bool = False
    n_threads: int = 10
    has_do_role: bool = False
    has_ds_role: bool = False

    _own_version: Optional[VersionInfo] = PrivateAttr(default=None)
    _executor: Optional[ThreadPoolExecutor] = PrivateAttr(default=None)

    # ========== Peer List Properties ==========

    def clear_caches(self) -> None:
        """Clear the caches."""
        self.peer_store.clear_caches()

    @property
    def approved_peers(self) -> List[Peer]:
        """Get all approved peers (DO side)."""
        return self.peer_store.approved_peers

    @property
    def requested_by_peer_peers(self) -> List[Peer]:
        """Get all peers that requested us (DO side)."""
        return self.peer_store.requested_by_peer_peers

    @property
    def requested_by_me_peers(self) -> List[Peer]:
        """Get all peers we requested but haven't reciprocated yet."""
        return self.peer_store.requested_by_me_peers

    @property
    def syncable_peers(self) -> List[Peer]:
        """Get all peers we can sync with (DS side)."""
        return self.peer_store.syncable_peers

    @classmethod
    def from_config(cls, config: PeerManagerConfig, email: str = "") -> "PeerManager":
        """Create a PeerManager from a config."""
        peer_store = PeerStore(email=email, use_encryption=config.use_encryption)
        connection_router = ConnectionRouter.from_configs(
            email, config.connection_configs
        )
        connection_router.peer_store = peer_store
        return cls(
            syftbox_folder=config.syftbox_folder,
            connection_router=connection_router,
            peer_store=peer_store,
            ignore_protocol_version=config.ignore_protocol_version,
            ignore_client_version=config.ignore_client_version,
            suppress_version_warnings=config.suppress_version_warnings,
            n_threads=config.n_threads,
            has_do_role=config.has_do_role,
            has_ds_role=config.has_ds_role,
        )

    def model_post_init(self, __context) -> None:
        """Initialize the thread pool executor."""
        self._executor = ThreadPoolExecutor(max_workers=self.n_threads)

    def get_own_version(self) -> VersionInfo:
        """Get current client's version info."""
        if self._own_version is None:
            self._own_version = VersionInfo.current()
        return self._own_version

    def read_own_version(self) -> Optional[VersionInfo]:
        """Read existing version file from own SyftBox folder on Drive."""
        return self.connection_router.read_own_version_file()

    def write_own_version(self) -> None:
        """Write version file to own SyftBox folder (remote) and local disk."""
        from syft_client.sync.version.local_version import write_local_version

        version_info = self.get_own_version()
        self.connection_router.write_version_file(version_info)
        write_local_version(self.syftbox_folder)

    def share_version_with_peer(self, peer_email: str) -> None:
        """Share version file with a peer so they can read it."""
        self.connection_router.share_version_file_with_peer(peer_email)

    def get_cached_peer(self, email: str) -> Optional[Peer]:
        """Get a peer by email, or None if not found."""
        return self.peer_store.get_cached_peer(email)

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
        """Add a peer — creates peer datasite folders on own drive, shares with peer.

        State-aware and idempotent:
        - If peer is REQUESTED_BY_PEER, creates our folders and marks ACCEPTED.
        - If peer is REQUESTED_BY_ME or ACCEPTED, skips (unless force=True).
        - If no existing peer, creates folders and marks REQUESTED_BY_ME.
        """
        existing_peer_obj = self.get_cached_peer(peer_email)
        if existing_peer_obj and not force:
            if existing_peer_obj.state == PeerState.REQUESTED_BY_ME:
                if verbose:
                    print_peer_already_connected(
                        peer_email, PeerState.REQUESTED_BY_ME.value
                    )
                return
            if existing_peer_obj.state == PeerState.ACCEPTED:
                if verbose:
                    print_peer_already_connected(peer_email, PeerState.ACCEPTED.value)
                return
            # REQUESTED_BY_PEER falls through to accept the incoming request

        is_accepting = (
            existing_peer_obj and existing_peer_obj.state == PeerState.REQUESTED_BY_PEER
        )

        if verbose:
            if force:
                print_peer_request_resending(peer_email)
            elif is_accepting:
                print_peer_request_accepting(peer_email)
            else:
                print_peer_request_sending(peer_email)

        new_state = PeerState.ACCEPTED if is_accepting else PeerState.REQUESTED_BY_ME

        new_peer_obj = self.connection_router.add_peer(
            peer_email=peer_email, verbose=False
        )

        if existing_peer_obj:
            new_peer_obj = existing_peer_obj

        # Exchange encryption bundles if key_manager is set
        if self.peer_store.use_encryption:
            self._write_encryption_bundle_for_peer(peer_email)

        peer_bundle = None
        if self.peer_store.use_encryption and is_accepting:
            peer_bundle = self._read_peer_encryption_bundle(peer_email)

        self.connection_router.update_peer_state(
            peer_email, new_state.value, public_encryption_bundle=peer_bundle
        )
        self.share_version_with_peer(peer_email)
        version_info = self.connection_router.read_peer_version_file(peer_email)

        new_peer_obj.version = version_info
        new_peer_obj.public_encryption_bundle = peer_bundle
        new_peer_obj.state = new_state
        self.peer_store.set_peer(new_peer_obj)

        if verbose:
            if is_accepting:
                print_peer_connection_established(peer_email)
            else:
                print_peer_request_sent(peer_email)

    def _write_encryption_bundle_for_peer(self, peer_email: str) -> dict | None:
        """Write own encryption bundle for a peer if encryption is enabled."""
        if not self.peer_store.use_encryption:
            raise ValueError("Encryption is not enabled")
        bundle = self.peer_store.get_public_bundle()
        bundle_json = json.dumps({"public_encryption_bundle": bundle})
        self.connection_router.write_encryption_bundle(peer_email, bundle_json)
        self.connection_router.share_encryption_bundles_folder(peer_email)
        return bundle

    def _read_peer_encryption_bundle(self, peer_email: str) -> dict | None:
        """Read a peer's encryption bundle if available."""
        bundle_json = self.connection_router.read_peer_encryption_bundle(peer_email)
        if not bundle_json:
            return None
        data = json.loads(bundle_json)
        return data.get("public_encryption_bundle")

    def load_peers(self, force_redownload: bool = False):
        """Load peers: from JSON (accepted + requested_by_me) + new requests from folder scan.

        Args:
            force_redownload: If True, re-fetch SYFT_peers.json from Drive instead
                of using the cached copy. Use when an external writer (e.g. another
                process) may have modified the file.
        """
        if not self.has_do_role and not self.has_ds_role:
            raise ValueError("Client has no role. Set has_do_role or has_ds_role.")

        json_peers = self.connection_router.get_all_peers_from_json(
            force_redownload=force_redownload
        )
        peers = [
            p
            for p in json_peers
            if p.state in (PeerState.ACCEPTED, PeerState.REQUESTED_BY_ME)
        ]

        # Detect new peer requests (folders for our datasite not yet in JSON)
        known_emails = {p.email for p in peers}
        peer_request_emails = {
            p.email for p in self.connection_router.get_peer_requests()
        }
        for email in peer_request_emails:
            if email not in known_emails:
                from syft_client.sync.platforms.gdrive_files_platform import (
                    GdriveFilesPlatform,
                )

                peers.append(
                    Peer(
                        email=email,
                        platforms=[GdriveFilesPlatform()],
                        state=PeerState.REQUESTED_BY_PEER,
                    )
                )
            else:
                # Both sides created folders — upgrade state
                existing = next(p for p in peers if p.email == email)
                if existing.state == PeerState.REQUESTED_BY_ME:
                    existing.state = PeerState.ACCEPTED
                    self.connection_router.update_peer_state(
                        email, PeerState.ACCEPTED.value
                    )

        self.peer_store.set_peers(peers)

        # Try to read encryption bundles from GDrive for peers missing bundles
        if self.peer_store.use_encryption:
            for peer in peers:
                if peer.state in (PeerState.ACCEPTED, PeerState.REQUESTED_BY_ME):
                    if not self.peer_store.has_peer_bundle(peer.email):
                        bundle = self._read_peer_encryption_bundle(peer.email)
                        if bundle:
                            self.peer_store.set_peer_bundle(peer.email, bundle)
                            self.connection_router.update_peer_state(
                                peer.email,
                                peer.state.value,
                                public_encryption_bundle=bundle,
                            )

        self.load_peer_versions_parallel([peer.email for peer in peers])

    def check_peer_request_exists(self, email: str) -> bool:
        """Check if a peer request exists for the given email."""
        return any(p.email == email for p in self.requested_by_peer_peers)

    def approve_peer_request(
        self,
        email_or_peer: str | Peer,
        verbose: bool = True,
        peer_must_exist: bool = True,
    ):
        """Approve a pending peer request.

        Validates the request exists, then delegates to add_peer(force=True).
        """
        email = email_or_peer if isinstance(email_or_peer, str) else email_or_peer.email

        peer = self.get_cached_peer(email)
        if peer and peer.is_approved:
            if verbose:
                print(f"Peer {email} is already approved, skipping")
            return

        peer_can_approve = peer and peer.state == PeerState.REQUESTED_BY_PEER
        if not peer_can_approve:
            self.load_peers()
            peer = self.get_cached_peer(email)
            peer_can_approve = peer and peer.state == PeerState.REQUESTED_BY_PEER
        if peer_must_exist and not peer_can_approve:
            raise ValueError(
                f"Peer {email} not found in pending requests. "
                f"Use client.peers to see current requests."
            )

        self.add_peer(email, force=True, verbose=False)
        if verbose:
            print(f"Approved peer request from {email}")

    def reject_peer_request(self, email_or_peer: str | Peer):
        """Reject a pending peer request."""
        email = email_or_peer if isinstance(email_or_peer, str) else email_or_peer.email

        peer = self.get_cached_peer(email)
        if not peer or not peer.is_requested_by_peer:
            raise ValueError(
                f"Peer {email} not found in pending requests. "
                f"Use client.peers to see current requests."
            )

        self.connection_router.update_peer_state(email, PeerState.REJECTED.value)
        peer.state = PeerState.REJECTED
        print(f"Rejected peer request from {email}")
