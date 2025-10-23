from typing import Callable, List

from pydantic import BaseModel, Field
from syft_client.syncv2.connections.base_connection import (
    ConnectionConfig,
    SyftboxPlatformConnection,
)
from syft_client.syncv2.events.file_change_event import FileChangeEvent
from syft_client.syncv2.messages.proposed_filechange import ProposedFileChangesMessage


class InMemoryPlatformConnectionConfig(ConnectionConfig):
    receiver_function: Callable | None = None


class InMemoryBackingPlatform(BaseModel):
    events: List[FileChangeEvent] = []


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

    def send_propose_file_change_message(
        self, proposed_file_change: ProposedFileChangesMessage
    ):
        self.receiver_function(proposed_file_change)

    def write_event_to_backing_platform(self, event: FileChangeEvent):
        self.backing_store.events.append(event)

    def get_events_for_datasite_watcher(
        self, since_timestamp: float | None = None
    ) -> List[FileChangeEvent]:
        # TODO: implement permissions
        if since_timestamp is not None:
            return self.backing_store.events
        else:
            return [
                e for e in self.backing_store.events if e.timestamp > since_timestamp
            ]

    def get_all_events(self) -> List[FileChangeEvent]:
        return self.backing_store.events
