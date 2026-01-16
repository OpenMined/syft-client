from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from pydantic import BaseModel, Field
from syft_client.sync.connections.base_connection import (
    ConnectionConfig,
    SyftboxPlatformConnection,
)
from syft_client.sync.events.file_change_event import (
    FileChangeEventsMessage,
)
from syft_client.sync.messages.proposed_filechange import (
    ProposedFileChangesMessage,
)
from syft_datasets.dataset_manager import SHARE_WITH_ANY

if TYPE_CHECKING:
    from syft_client.sync.version.version_info import VersionInfo


class InMemoryPlatformConnectionConfig(ConnectionConfig):
    receiver_function: Callable | None = None


class InMemoryDatasetsFolder(BaseModel):
    """Represents a dataset collection with files and permissions."""

    tag: str  # Dataset name
    content_hash: str  # Hash of file contents
    owner_email: str
    allowed_users: List[str]  # List of emails or ["any"]. Empty list = no access
    files: Dict[str, bytes] = Field(default_factory=dict)  # filename -> content


class InMemoryBackingPlatform(BaseModel):
    proposed_events_inbox: List[ProposedFileChangesMessage] = Field(
        default_factory=lambda: []
    )
    syftbox_events_message_log: List[FileChangeEventsMessage] = Field(
        default_factory=lambda: []
    )

    # Peer state tracking for request/approval flow
    # Structure: {owner_email: {peer_email: state}}
    # Example: {"do@test.com": {"ds1@test.com": "accepted", "ds2@test.com": "pending"}}
    # Note: backing_store is shared between connections, so we need nested dicts
    # State can be: "pending", "accepted", or "rejected"
    peer_states: Dict[str, Dict[str, str]] = Field(default_factory=dict)

    outboxes: Dict[str, List[FileChangeEventsMessage]] = Field(
        default_factory=lambda: {
            "all": [],
        }
    )

    # Dataset collections storage
    dataset_collections: List[InMemoryDatasetsFolder] = Field(default_factory=list)

    # Version files storage: {owner_email: version_json_string}
    version_files: Dict[str, str] = Field(default_factory=dict)

    # Version file permissions: {owner_email: set of emails that can read}
    version_file_permissions: Dict[str, List[str]] = Field(default_factory=dict)


class InMemoryPlatformConnection(SyftboxPlatformConnection):
    owner_email: str
    receiver_function: Callable | None = None
    backing_store: InMemoryBackingPlatform = Field(
        default_factory=InMemoryBackingPlatform
    )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, InMemoryPlatformConnection):
            return False
        return self.owner_email == other.owner_email

    @classmethod
    def from_config(
        cls,
        config: InMemoryPlatformConnectionConfig,
        backing_store: InMemoryBackingPlatform | None = None,
    ):
        return cls(
            config=config,
            receiver_function=config.receiver_function,
            backing_store=backing_store or InMemoryBackingPlatform(),
        )

    def get_peers_as_ds(self) -> List[str]:
        """Get all peers regardless of state"""
        peer_states = self.backing_store.peer_states.get(self.owner_email, {})
        return list(peer_states.keys())

    def send_proposed_file_changes_message(
        self, recipient: str, proposed_file_changes_message: ProposedFileChangesMessage
    ):
        # TODO: do something with the recipient
        self.backing_store.proposed_events_inbox.append(proposed_file_changes_message)

        if self.receiver_function is not None:
            self.receiver_function()

    def create_pending_peer_state(self, owner_email: str, peer_email: str):
        """Add a peer with pending state (creates peer request)"""
        if owner_email not in self.backing_store.peer_states:
            self.backing_store.peer_states[owner_email] = {}
        # Add as pending if not already tracked
        if peer_email not in self.backing_store.peer_states[owner_email]:
            self.backing_store.peer_states[owner_email][peer_email] = "pending"

    def add_peer_as_ds(self, peer_email: str):
        """Add peer as DS - creates peer relationship that DO can discover"""
        # Reversed: add DS to DO's peer list so DO can discover it
        # self.owner_email is DS, peer_email is DO
        # We want peer_states[DO_email][DS_email] = "pending"
        self.create_pending_peer_state(peer_email, self.owner_email)
        self.create_pending_peer_state(self.owner_email, peer_email)

    def _get_peer_states(self) -> Dict[str, str]:
        """Get peer states for this owner. Returns {peer_email: state}"""
        return self.backing_store.peer_states.get(self.owner_email, {})

    def _update_peer_state(self, peer_email: str, state: str):
        """Update a peer's state"""
        if self.owner_email not in self.backing_store.peer_states:
            self.backing_store.peer_states[self.owner_email] = {}
        self.backing_store.peer_states[self.owner_email][peer_email] = state

    def get_approved_peers_as_do(self) -> List[str]:
        """Get list of approved peer emails"""
        peer_states = self._get_peer_states()
        return [email for email, state in peer_states.items() if state == "accepted"]

    def get_peer_requests_as_do(self) -> List[str]:
        """Get list of pending peer requests"""
        # Get all peers that have been added (in backing_store.peers)
        # Filter to only those not in peer_states or with pending state
        peer_states = self._get_peer_states()
        pending = [email for email, state in peer_states.items() if state == "pending"]
        return pending

    def get_next_proposed_filechange_message(
        self, sender_email: str = None
    ) -> ProposedFileChangesMessage | None:
        """Get next message from specific sender (or any if sender_email=None)"""
        if len(self.backing_store.proposed_events_inbox) == 0:
            return None

        if sender_email is None:
            # No filter - return first message
            return self.backing_store.proposed_events_inbox[0]

        # Filter by sender
        for message in self.backing_store.proposed_events_inbox:
            if message.sender_email == sender_email:
                return message

        return None  # No message from this sender

    def remove_proposed_filechange_message_from_inbox(
        self, proposed_filechange_message: ProposedFileChangesMessage
    ):
        self.backing_store.proposed_events_inbox = [
            e
            for e in self.backing_store.proposed_events_inbox
            if e.id != proposed_filechange_message.id
        ]

    def write_events_message_to_syftbox(
        self, events_message: FileChangeEventsMessage
    ) -> None:
        self.backing_store.syftbox_events_message_log.append(events_message)

    def write_event_messages_to_outbox_do(
        self, sender_email: str, events_message: FileChangeEventsMessage
    ) -> None:
        self.backing_store.outboxes["all"].append(events_message)

    def get_events_messages_for_datasite_watcher(
        self, peer_email: str, since_timestamp: float | None = None
    ) -> List[FileChangeEventsMessage]:
        # TODO: implement permissions
        all_event_messages = self.backing_store.outboxes["all"]
        if since_timestamp is None:
            return all_event_messages
        else:
            return [e for e in all_event_messages if e.timestamp > since_timestamp]

    def get_all_events_messages_do(self) -> List[FileChangeEventsMessage]:
        return self.backing_store.syftbox_events_message_log

    def create_dataset_collection_folder(
        self, tag: str, content_hash: str, owner_email: str
    ) -> str:
        # Check if collection already exists with same hash
        for collection in self.backing_store.dataset_collections:
            if (
                collection.tag == tag
                and collection.owner_email == owner_email
                and collection.content_hash == content_hash
            ):
                return tag

        # Create new collection
        new_collection = InMemoryDatasetsFolder(
            tag=tag,
            content_hash=content_hash,
            owner_email=owner_email,
            allowed_users=[],
        )
        self.backing_store.dataset_collections.append(new_collection)
        return tag

    def share_dataset_collection(
        self, tag: str, content_hash: str, users: list[str] | str
    ) -> None:
        # Find collection
        collection = None
        for c in self.backing_store.dataset_collections:
            if (
                c.tag == tag
                and c.owner_email == self.owner_email
                and c.content_hash == content_hash
            ):
                collection = c
                break

        if collection is None:
            raise ValueError(
                f"Collection {tag} with hash {content_hash} not found for owner {self.owner_email}"
            )

        # Update permissions
        if isinstance(users, str):
            if users == SHARE_WITH_ANY:
                collection.allowed_users = [SHARE_WITH_ANY]
            else:
                if users not in collection.allowed_users:
                    collection.allowed_users.append(users)
        else:
            for user in users:
                if user not in collection.allowed_users:
                    collection.allowed_users.append(user)

    def upload_dataset_files(
        self, tag: str, content_hash: str, files: dict[str, bytes]
    ) -> None:
        # Find collection and upload files to backing store
        collection = None
        for c in self.backing_store.dataset_collections:
            if (
                c.tag == tag
                and c.owner_email == self.owner_email
                and c.content_hash == content_hash
            ):
                collection = c
                break

        if collection is None:
            raise ValueError(f"Collection {tag} with hash {content_hash} not found")

        # Store files in backing store
        collection.files.update(files)

    def list_dataset_collections_as_do(self) -> list[str]:
        result = []
        for collection in self.backing_store.dataset_collections:
            if collection.owner_email == self.owner_email:
                result.append(collection.tag)
        return result

    def list_dataset_collections_as_ds(self) -> list[dict]:
        result = []
        for collection in self.backing_store.dataset_collections:
            if collection.owner_email == self.owner_email:
                continue  # Skip own collections

            # Check permissions - empty list means no access
            if not collection.allowed_users:
                continue

            if (
                SHARE_WITH_ANY in collection.allowed_users
                or self.owner_email in collection.allowed_users
            ):
                result.append(
                    {
                        "owner_email": collection.owner_email,
                        "tag": collection.tag,
                        "content_hash": collection.content_hash,
                    }
                )

        return result

    def download_dataset_collection(
        self, tag: str, content_hash: str, owner_email: str
    ) -> dict[str, bytes]:
        # Find collection
        collection = None
        for c in self.backing_store.dataset_collections:
            if (
                c.tag == tag
                and c.owner_email == owner_email
                and c.content_hash == content_hash
            ):
                collection = c
                break

        if collection is None:
            raise ValueError(
                f"Collection {tag} with hash {content_hash} not found for owner {owner_email}"
            )

        # Check permissions - empty list means no access
        if not collection.allowed_users:
            raise PermissionError(f"No access granted to collection {tag}")

        if (
            SHARE_WITH_ANY not in collection.allowed_users
            and self.owner_email not in collection.allowed_users
        ):
            raise PermissionError(f"Access denied to collection {tag}")

        # Return copy of files from backing store
        return collection.files.copy()

    def get_all_accepted_event_file_ids_do(self) -> List[str]:
        return [
            e.message_filepath.id for e in self.backing_store.syftbox_events_message_log
        ]

    def download_events_message_by_id(
        self, events_message_id: str
    ) -> FileChangeEventsMessage:
        return [
            e
            for e in self.backing_store.syftbox_events_message_log
            if e.message_filepath.id == events_message_id
        ][0]

    def write_version_file(self, version_info: "VersionInfo") -> None:
        """Write version file to this user's storage."""
        self.backing_store.version_files[self.owner_email] = version_info.to_json()

    def read_peer_version_file(self, peer_email: str) -> Optional["VersionInfo"]:
        """Read version file from a peer's storage."""
        from syft_client.sync.version.version_info import VersionInfo

        # Check if version file exists
        version_json = self.backing_store.version_files.get(peer_email)
        if version_json is None:
            return None

        # Check if we have permission to read it
        permissions = self.backing_store.version_file_permissions.get(peer_email, [])
        if self.owner_email not in permissions:
            return None

        return VersionInfo.from_json(version_json)

    def share_version_file_with_peer(self, peer_email: str) -> None:
        """Share the version file with a peer so they can read it."""
        if self.owner_email not in self.backing_store.version_file_permissions:
            self.backing_store.version_file_permissions[self.owner_email] = []
        if peer_email not in self.backing_store.version_file_permissions[self.owner_email]:
            self.backing_store.version_file_permissions[self.owner_email].append(peer_email)
