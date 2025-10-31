from typing import Callable, Dict, List

from pydantic import BaseModel, Field
from syft_client.sync.connections.base_connection import (
    ConnectionConfig,
    SyftboxPlatformConnection,
)
from syft_client.sync.events.file_change_event import FileChangeEvent
from syft_client.sync.messages.proposed_filechange import (
    ProposedFileChangesMessage,
)


class InMemoryPlatformConnectionConfig(ConnectionConfig):
    receiver_function: Callable | None = None


class InMemoryBackingPlatform(BaseModel):
    proposed_events_inbox: List[ProposedFileChangesMessage] = []
    event_log: List[FileChangeEvent] = []
    peers: Dict[str, List[str]] = {}

    outboxes: Dict[str, List[FileChangeEvent]] = {
        "all": [],
    }


class InMemoryPlatformConnection(SyftboxPlatformConnection):
    owner_email: str
    receiver_function: Callable | None = None
    backing_store: InMemoryBackingPlatform = Field(
        default_factory=InMemoryBackingPlatform
    )

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

    def write_event_to_syftbox(self, event: FileChangeEvent) -> None:
        self.backing_store.event_log.append(event)

    def write_event_to_outbox_do(
        self, sender_email: str, event: FileChangeEvent
    ) -> None:
        self.backing_store.outboxes["all"].append(event)

    def get_events_for_datasite_watcher(
        self, peer_email: str, since_timestamp: float | None = None
    ) -> List[FileChangeEvent]:
        # TODO: implement permissions
        all_events = self.backing_store.outboxes["all"]
        if since_timestamp is None:
            return all_events
        else:
            return [e for e in all_events if e.timestamp > since_timestamp]

    def get_all_events_do(self) -> List[FileChangeEvent]:
        return self.backing_store.event_log
