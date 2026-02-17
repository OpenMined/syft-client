from pydantic import BaseModel
from typing import TYPE_CHECKING, List, Optional
from syft_client.sync.connections.base_connection import (
    ConnectionConfig,
    FileCollection,
    SyftboxPlatformConnection,
)
from syft_client.sync.connections.drive.gdrive_transport import GDriveConnection
from syft_client.sync.events.file_change_event import (
    FileChangeEventsMessage,
)
from syft_client.sync.checkpoints.checkpoint import Checkpoint, IncrementalCheckpoint
from syft_client.sync.checkpoints.rolling_state import RollingState
from syft_client.sync.messages.proposed_filechange import ProposedFileChangesMessage
from syft_client.sync.platforms.gdrive_files_platform import GdriveFilesPlatform
from syft_client.sync.peers.peer import Peer, PeerState
from syft_client.sync.utils.print_utils import (
    print_peer_adding_to_platform,
    print_peer_added_to_platform,
)

if TYPE_CHECKING:
    from syft_client.sync.version.version_info import VersionInfo


class ConnectionRouter(BaseModel):
    connections: List[SyftboxPlatformConnection]

    @classmethod
    def from_configs(cls, connection_configs: List[ConnectionConfig]):
        return cls(
            connections=[
                SyftboxPlatformConnection.from_config(config)
                for config in connection_configs
            ]
        )

    def add_connection(self, connection: SyftboxPlatformConnection):
        self.connections.append(connection)

    def connection_for_send_message(self) -> SyftboxPlatformConnection:
        return self.connections[0]

    def connection_for_receive_message(self) -> SyftboxPlatformConnection:
        return self.connections[0]

    def copy_connection(
        self, connection: SyftboxPlatformConnection
    ) -> SyftboxPlatformConnection:
        if isinstance(connection, GDriveConnection):
            # Check if using mock service (no credentials and no token_path)
            return connection.copy()
        else:
            return connection

    def connection_for_eventlog(
        self, create_new: bool = False
    ) -> SyftboxPlatformConnection:
        existing_connection = self.connections[0]
        if create_new:
            return self.copy_connection(existing_connection)
        else:
            return existing_connection

    def connection_for_datasite_watcher(self) -> SyftboxPlatformConnection:
        return self.connections[0]

    def connection_for_outbox(self) -> SyftboxPlatformConnection:
        return self.connections[0]

    def connection_for_own_syftbox(self) -> SyftboxPlatformConnection:
        return self.connections[0]

    def send_proposed_file_changes_message(
        self, recipient: str, proposed_file_changes_message: ProposedFileChangesMessage
    ):
        # TODO: Implement connection routing logic
        connection = self.connection_for_send_message()
        connection.send_proposed_file_changes_message(
            recipient, proposed_file_changes_message
        )

    def add_peer_as_ds(self, peer_email: str, verbose: bool = True) -> Peer:
        connection = self.connection_for_receive_message()
        platform = GdriveFilesPlatform()

        if verbose:
            print_peer_adding_to_platform(peer_email, platform.module_path)

        connection.add_peer_as_ds(peer_email=peer_email)

        if verbose:
            print_peer_added_to_platform(peer_email, platform.module_path)
        return Peer(email=peer_email, platforms=[platform])

    # def delete_syftbox(self):
    #     connection = self.connection_for_own_syftbox()
    #     connection.delete_syftbox()

    def delete_multiple_files_by_ids(
        self,
        file_ids: List[str],
        ignore_permissions_errors: bool = True,
        ignore_file_not_found: bool = True,
    ):
        connection = self.connection_for_own_syftbox()
        connection.delete_multiple_files_by_ids(
            file_ids,
            ignore_permissions_errors=ignore_permissions_errors,
            ignore_file_not_found=ignore_file_not_found,
        )

    def get_all_accepted_event_file_ids_do(
        self, since_timestamp: float | None = None
    ) -> List[str]:
        connection = self.connection_for_eventlog()
        return connection.get_all_accepted_event_file_ids_do(since_timestamp)

    def gather_all_file_and_folder_ids(self) -> List[str]:
        connection = self.connection_for_own_syftbox()
        return connection.gather_all_file_and_folder_ids()

    def find_orphaned_message_files(self) -> List[str]:
        """Find message files by name pattern (catches orphaned files)."""
        connection = self.connection_for_own_syftbox()
        return connection.find_orphaned_message_files()

    def reset_caches(self):
        connection = self.connection_for_own_syftbox()
        connection.reset_caches()

    def delete_file_by_id(self, file_id: str):
        connection = self.connection_for_own_syftbox()
        connection.delete_file_by_id(file_id)

    def write_events_message_to_syftbox(self, events_message: FileChangeEventsMessage):
        connection = self.connection_for_eventlog()
        connection.write_events_message_to_syftbox(events_message)

    def write_event_messages_to_outbox_do(
        self, recipient_email: str, events_message: FileChangeEventsMessage
    ):
        connection = self.connection_for_outbox()
        connection.write_event_messages_to_outbox_do(recipient_email, events_message)

    def get_all_accepted_events_messages_do(self) -> List[FileChangeEventsMessage]:
        connection = self.connection_for_eventlog()
        return connection.get_all_events_messages_do()

    def get_next_proposed_filechange_message(
        self, sender_email: str = None
    ) -> ProposedFileChangesMessage | None:
        connection = self.connection_for_receive_message()
        return connection.get_next_proposed_filechange_message(
            sender_email=sender_email
        )

    def get_peers_as_ds(self) -> List[Peer]:
        connection = self.connection_for_receive_message()
        peer_emails = connection.get_peers_as_ds()
        return [
            Peer(email=peer_email, platforms=[GdriveFilesPlatform()])
            for peer_email in peer_emails
        ]

    def get_approved_peers_as_do(self) -> List[Peer]:
        """Get approved peers for DO"""
        connection = self.connection_for_send_message()
        peer_emails = connection.get_approved_peers_as_do()
        return [
            Peer(
                email=peer_email,
                platforms=[GdriveFilesPlatform()],
                state=PeerState.ACCEPTED,
            )
            for peer_email in peer_emails
        ]

    def get_peer_requests_as_do(self) -> List[Peer]:
        """Get pending peer requests for DO"""
        connection = self.connection_for_send_message()
        peer_emails = connection.get_peer_requests_as_do()
        return [
            Peer(
                email=peer_email,
                platforms=[GdriveFilesPlatform()],
                state=PeerState.PENDING,
            )
            for peer_email in peer_emails
        ]

    def update_peer_state(self, peer_email: str, state: str):
        """Update peer state in storage"""
        connection = self.connection_for_send_message()
        connection._update_peer_state(peer_email, state)

    def remove_proposed_filechange_from_inbox(
        self, proposed_filechange_message: ProposedFileChangesMessage
    ):
        connection = self.connection_for_receive_message()
        connection.remove_proposed_filechange_message_from_inbox(
            proposed_filechange_message
        )

    def get_events_messages_for_datasite_watcher(
        self, peer_email: str, since_timestamp: float | None
    ) -> List[FileChangeEventsMessage]:
        connection = self.connection_for_datasite_watcher()
        return connection.get_events_messages_for_datasite_watcher(
            peer_email=peer_email, since_timestamp=since_timestamp
        )

    def get_outbox_file_metadatas_for_ds(
        self, peer_email: str, since_timestamp: float | None
    ) -> List[dict]:
        connection = self.connection_for_datasite_watcher()
        return connection.get_outbox_file_metadatas_for_ds(peer_email, since_timestamp)

    def download_events_message_by_id_from_outbox(
        self, file_id: str
    ) -> FileChangeEventsMessage:
        """Download event message from outbox by ID."""
        connection = self.connection_for_datasite_watcher()
        return connection.download_events_message_by_id_from_outbox(file_id)

    def connection_for_parallel_download(self) -> SyftboxPlatformConnection:
        """Create a new connection for thread-safe parallel downloads."""
        return self.copy_connection(self.connection_for_datasite_watcher())

    def create_dataset_collection_folder(
        self, tag: str, content_hash: str, owner_email: str
    ) -> str:
        connection = self.connection_for_send_message()
        return connection.create_dataset_collection_folder(
            tag, content_hash, owner_email
        )

    def tag_dataset_collection_as_any(
        self, tag: str, content_hash: str
    ) -> None:
        connection = self.connection_for_send_message()
        connection.tag_dataset_collection_as_any(tag, content_hash)

    def share_dataset_collection(
        self, tag: str, content_hash: str, users: list[str]
    ) -> None:
        connection = self.connection_for_send_message()
        connection.share_dataset_collection(tag, content_hash, users)

    def upload_dataset_files(
        self, tag: str, content_hash: str, files: dict[str, bytes]
    ) -> None:
        connection = self.connection_for_send_message()
        connection.upload_dataset_files(tag, content_hash, files)

    def list_dataset_collections_as_do(self) -> list[str]:
        connection = self.connection_for_send_message()
        return connection.list_dataset_collections_as_do()

    def list_all_dataset_collections_as_do_with_permissions(
        self,
    ) -> list[FileCollection]:
        connection = self.connection_for_send_message()
        return connection.list_all_dataset_collections_as_do_with_permissions()

    def list_dataset_collections_as_ds(self) -> list[dict]:
        connection = self.connection_for_receive_message()
        return connection.list_dataset_collections_as_ds()

    def download_dataset_collection(
        self, tag: str, content_hash: str, owner_email: str
    ) -> dict[str, bytes]:
        connection = self.connection_for_datasite_watcher()
        return connection.download_dataset_collection(tag, content_hash, owner_email)

    def connection_for_version_read(
        self, create_new: bool = False
    ) -> SyftboxPlatformConnection:
        """Get connection for reading version files. Can create new for thread safety."""
        existing_connection = self.connections[0]
        if create_new:
            return self.copy_connection(existing_connection)
        else:
            return existing_connection

    def write_version_file(self, version_info: "VersionInfo") -> None:
        """Write version file to own SyftBox folder."""
        connection = self.connection_for_own_syftbox()
        connection.write_version_file(version_info)

    def read_peer_version_file(self, peer_email: str) -> Optional["VersionInfo"]:
        """Read version file from a peer's SyftBox folder."""
        connection = self.connection_for_datasite_watcher()
        return connection.read_peer_version_file(peer_email)

    def share_version_file_with_peer(self, peer_email: str) -> None:
        """Share version file with a peer so they can read it."""
        connection = self.connection_for_own_syftbox()
        connection.share_version_file_with_peer(peer_email)

    def get_dataset_collection_file_metadatas(
        self, tag: str, content_hash: str, owner_email: str
    ) -> List[dict]:
        connection = self.connection_for_datasite_watcher()
        return connection.get_dataset_collection_file_metadatas(
            tag, content_hash, owner_email
        )

    def download_dataset_file(self, file_id: str) -> bytes:
        connection = self.connection_for_datasite_watcher()
        return connection.download_dataset_file(file_id)

    # =========================================================================
    # CHECKPOINT METHODS
    # =========================================================================

    def upload_checkpoint(self, checkpoint: Checkpoint) -> str:
        """Upload a checkpoint to the storage backend."""
        connection = self.connection_for_own_syftbox()
        return connection.upload_checkpoint(checkpoint)

    def get_latest_checkpoint(self) -> Checkpoint | None:
        """Get the latest checkpoint from the storage backend."""
        connection = self.connection_for_own_syftbox()
        return connection.get_latest_checkpoint()

    def get_events_count_since_checkpoint(
        self, checkpoint_timestamp: float | None
    ) -> int:
        """Count events created after the checkpoint timestamp."""
        connection = self.connection_for_eventlog()
        return connection.get_events_count_since_checkpoint(checkpoint_timestamp)

    def get_events_messages_since_timestamp(
        self, since_timestamp: float
    ) -> List[FileChangeEventsMessage]:
        """Get events created after a specific timestamp."""
        connection = self.connection_for_eventlog()
        return connection.get_events_messages_since_timestamp(since_timestamp)

    # =========================================================================
    # INCREMENTAL CHECKPOINT METHODS
    # =========================================================================

    def upload_incremental_checkpoint(self, checkpoint: IncrementalCheckpoint) -> str:
        """Upload an incremental checkpoint to the storage backend."""
        connection = self.connection_for_own_syftbox()
        return connection.upload_incremental_checkpoint(checkpoint)

    def get_all_incremental_checkpoints(self) -> List[IncrementalCheckpoint]:
        """Get all incremental checkpoints from the storage backend."""
        connection = self.connection_for_own_syftbox()
        return connection.get_all_incremental_checkpoints()

    def get_incremental_checkpoint_count(self) -> int:
        """Get the number of incremental checkpoints."""
        connection = self.connection_for_own_syftbox()
        return connection.get_incremental_checkpoint_count()

    def get_next_incremental_sequence_number(self) -> int:
        """Get the next sequence number for incremental checkpoints."""
        connection = self.connection_for_own_syftbox()
        return connection.get_next_incremental_sequence_number()

    def delete_all_incremental_checkpoints(self) -> None:
        """Delete all incremental checkpoints from the storage backend."""
        connection = self.connection_for_own_syftbox()
        connection.delete_all_incremental_checkpoints()

    # =========================================================================
    # ROLLING STATE METHODS
    # =========================================================================

    def upload_rolling_state(self, rolling_state: RollingState) -> str:
        """Upload rolling state to the storage backend."""
        connection = self.connection_for_own_syftbox()
        return connection.upload_rolling_state(rolling_state)

    def get_rolling_state(self) -> RollingState | None:
        """Get the rolling state from the storage backend."""
        connection = self.connection_for_own_syftbox()
        return connection.get_rolling_state()

    def delete_rolling_state(self) -> None:
        """Delete rolling state from the storage backend."""
        connection = self.connection_for_own_syftbox()
        connection.delete_rolling_state()
