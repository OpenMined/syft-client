from typing import Callable, Dict, List
from uuid import UUID

from pydantic import BaseModel, Field
from syft_client.syncv2.connections.base_connection import (
    ConnectionConfig,
    SyftboxPlatformConnection,
)
from syft_client.syncv2.events.file_change_event import FileChangeEvent
from syft_client.syncv2.messages.proposed_filechange import (
    ProposedFileChange,
    ProposedFileChangesMessage,
)


class InMemoryPlatformConnectionConfig(ConnectionConfig):
    receiver_function: Callable | None = None


class InMemoryBackingPlatform(BaseModel):
    proposed_events_inbox: List[ProposedFileChangesMessage] = []
    event_log: List[FileChangeEvent] = []

    outboxes: Dict[str, List[FileChangeEvent]] = {
        "all": [],
    }


class InMemoryPlatformConnection(SyftboxPlatformConnection):
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

    def send_proposed_file_changes_message(
        self, recipient: str, proposed_file_changes_message: ProposedFileChangesMessage
    ):
        # TODO: do something with the recipient
        self.backing_store.proposed_events_inbox.append(proposed_file_changes_message)
        self.receiver_function(proposed_file_changes_message)

    def get_next_proposed_filechange_message(
        self, sender_email: str = None
    ) -> ProposedFileChangesMessage | None:
        # TODO: either remove the sender parameter in all SyftboxPlatformConnections
        # or implement it here
        if sender_email is not None:
            raise NotImplementedError("Not implemented")

        if len(self.backing_store.proposed_events_inbox) == 0:
            return None
        else:
            return self.backing_store.proposed_events_inbox[0]

    def remove_proposed_filechange_message_from_inbox(
        self, proposed_filechange_message_id: UUID
    ):
        self.backing_store.proposed_events_inbox = [
            e
            for e in self.backing_store.proposed_events_inbox
            if e.id != proposed_filechange_message_id
        ]

    def write_event_to_backing_platform(self, event: FileChangeEvent) -> None:
        self.backing_store.event_log.append(event)

    def write_event_to_outbox(self, event: FileChangeEvent) -> None:
        self.backing_store.outboxes["all"].append(event)

    def get_events_for_datasite_watcher(
        self, since_timestamp: float | None = None
    ) -> List[FileChangeEvent]:
        # TODO: implement permissions
        all_events = self.backing_store.outboxes["all"]
        if since_timestamp is None:
            return all_events
        else:
            return [e for e in all_events if e.timestamp > since_timestamp]

    def get_all_events(self) -> List[FileChangeEvent]:
        return self.backing_store.event_log
