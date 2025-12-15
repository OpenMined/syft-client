from typing import Callable, Dict, List

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
from syft_client.sync.checkpoints.checkpoint import Checkpoint


class InMemoryPlatformConnectionConfig(ConnectionConfig):
    receiver_function: Callable | None = None


class InMemoryBackingPlatform(BaseModel):
    proposed_events_inbox: List[ProposedFileChangesMessage] = Field(
        default_factory=lambda: []
    )
    syftbox_events_message_log: List[FileChangeEventsMessage] = Field(
        default_factory=lambda: []
    )
    peers: Dict[str, List[str]] = Field(default_factory=lambda: {})

    outboxes: Dict[str, List[FileChangeEventsMessage]] = Field(
        default_factory=lambda: {
            "all": [],
        }
    )
    # Checkpoint storage
    checkpoints: List[Checkpoint] = Field(default_factory=lambda: [])


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

    def get_peers_as_do(self) -> List[str]:
        return self.backing_store.peers.get(self.owner_email, [])

    def get_peers_as_ds(self) -> List[str]:
        return self.backing_store.peers.get(self.owner_email, [])

    def send_proposed_file_changes_message(
        self, recipient: str, proposed_file_changes_message: ProposedFileChangesMessage
    ):
        # TODO: do something with the recipient
        self.backing_store.proposed_events_inbox.append(proposed_file_changes_message)

        if self.receiver_function is not None:
            self.receiver_function()

    def add_peer(self, owner_email: str, peer_email: str):
        if owner_email not in self.backing_store.peers:
            self.backing_store.peers[owner_email] = []
        self.backing_store.peers[owner_email].append(peer_email)

    def add_peer_as_do(self, peer_email: str):
        self.add_peer(self.owner_email, peer_email)

    def add_peer_as_ds(self, peer_email: str):
        self.add_peer(self.owner_email, peer_email)

    def get_next_proposed_filechange_message(
        self, sender_email: str = None
    ) -> ProposedFileChangesMessage | None:
        # TODO: either remove the sender parameter in all SyftboxPlatformConnections
        # or implement it here
        # if sender_email is not None:
        #     raise NotImplementedError("Not implemented")

        if len(self.backing_store.proposed_events_inbox) == 0:
            return None
        else:
            return self.backing_store.proposed_events_inbox[0]

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

    # =========================================================================
    # CHECKPOINT METHODS
    # =========================================================================

    def upload_checkpoint(self, checkpoint: Checkpoint) -> str:
        """Upload a checkpoint to in-memory storage."""
        self.backing_store.checkpoints.append(checkpoint)
        return checkpoint.filename

    def get_latest_checkpoint(self) -> Checkpoint | None:
        """Get the latest checkpoint from in-memory storage."""
        if not self.backing_store.checkpoints:
            return None
        # Return checkpoint with highest timestamp
        return max(self.backing_store.checkpoints, key=lambda c: c.timestamp)

    def get_events_count_since_checkpoint(
        self, checkpoint_timestamp: float | None
    ) -> int:
        """Count events created after the checkpoint timestamp."""
        if checkpoint_timestamp is None:
            return len(self.backing_store.syftbox_events_message_log)
        return sum(
            1
            for msg in self.backing_store.syftbox_events_message_log
            if msg.timestamp > checkpoint_timestamp
        )

    def get_events_messages_since_timestamp(
        self, since_timestamp: float
    ) -> List[FileChangeEventsMessage]:
        """Get events created after a specific timestamp."""
        return [
            msg
            for msg in self.backing_store.syftbox_events_message_log
            if msg.timestamp > since_timestamp
        ]
