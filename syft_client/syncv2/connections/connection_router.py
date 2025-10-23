from uuid import UUID
from pydantic import BaseModel
from typing import List
from syft_client.syncv2.connections.base_connection import SyftboxPlatformConnection
from syft_client.syncv2.events.file_change_event import FileChangeEvent
from syft_client.syncv2.messages.proposed_filechange import ProposedFileChangesMessage
from syft_client.syncv2.messages.proposed_filechange import ProposedFileChange


class ConnectionRouter(BaseModel):
    connections: List[SyftboxPlatformConnection]

    def connection_for_send_message(self) -> SyftboxPlatformConnection:
        return self.connections[0]

    def connection_for_receive_message(self) -> SyftboxPlatformConnection:
        return self.connections[0]

    def connection_for_eventlog(self) -> SyftboxPlatformConnection:
        return self.connections[0]

    def connection_for_datasite_watcher(self) -> SyftboxPlatformConnection:
        return self.connections[0]

    def connection_for_outbox(self) -> SyftboxPlatformConnection:
        return self.connections[0]

    def send_proposed_filechange_message(
        self, proposed_file_change_message: ProposedFileChangesMessage
    ):
        # TODO: Implement connection routing logic
        connection = self.connection_for_send_message()
        connection.send_propose_file_change_message(proposed_file_change_message)

    def write_event_to_backing_platform(self, event: FileChangeEvent):
        connection = self.connection_for_eventlog()
        connection.write_event_to_backing_platform(event)

    def write_event_to_outbox(self, event: FileChangeEvent):
        connection = self.connection_for_outbox()
        connection.write_event_to_outbox(event)

    def get_all_events(self) -> List[FileChangeEvent]:
        connection = self.connection_for_eventlog()
        return connection.get_all_events()

    def get_next_proposed_filechange_message(self) -> ProposedFileChangesMessage | None:
        connection = self.connection_for_receive_message()
        return connection.get_next_proposed_filechange_message()

    def remove_proposed_filechange_from_inbox(
        self, proposed_filechange_message_id: UUID
    ):
        connection = self.connection_for_receive_message()
        connection.remove_proposed_filechange_message_from_inbox(
            proposed_filechange_message_id
        )

    def get_events_for_datasite_watcher(
        self, since_timestamp: float | None
    ) -> List[FileChangeEvent]:
        connection = self.connection_for_datasite_watcher()
        return connection.get_events_for_datasite_watcher(
            since_timestamp=since_timestamp
        )
