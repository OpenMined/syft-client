from pydantic import BaseModel
from typing import List
from syft_client.syncv2.connections.base_connection import SyftboxPlatformConnection
from syft_client.syncv2.events.file_change_event import FileChangeEvent
from syft_client.syncv2.messages.proposed_filechange import ProposedFileChangesMessage


class ConnectionRouter(BaseModel):
    connections: List[SyftboxPlatformConnection]

    def connection_for_message(self) -> SyftboxPlatformConnection:
        return self.connections[0]

    def connection_for_backing_platform(self) -> SyftboxPlatformConnection:
        return self.connections[0]

    def connection_for_datasite_watcher(self) -> SyftboxPlatformConnection:
        return self.connections[0]

    def send_proposed_filechange_message(
        self, proposed_file_change_message: ProposedFileChangesMessage
    ):
        # TODO: Implement connection routing logic
        connection = self.connection_for_message()
        connection.send_propose_file_change_message(proposed_file_change_message)

    def write_event_to_backing_platform(self, event: FileChangeEvent):
        connection = self.connection_for_backing_platform()
        connection.write_event_to_backing_platform(event)

    def get_all_events(self) -> List[FileChangeEvent]:
        connection = self.connection_for_backing_platform()
        return connection.get_all_events()

    def get_events_for_datasite_watcher(self) -> List[FileChangeEvent]:
        connection = self.connection_for_datasite_watcher()
        return connection.get_events_for_datasite_watcher()
