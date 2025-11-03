from pydantic import BaseModel
from typing import List
from syft_client.sync.connections.base_connection import SyftboxPlatformConnection
from syft_client.sync.events.file_change_event import FileChangeEvent
from syft_client.sync.messages.proposed_filechange import ProposedFileChangesMessage
from syft_client.sync.platforms.gdrive_files_platform import GdriveFilesPlatform
from syft_client.sync.peers.peer import Peer
from syft_client.sync.utils.print_utils import (
    print_peer_adding_to_platform,
    print_peer_added_to_platform,
)


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

    def add_peer_as_do(self, peer_email: str, verbose: bool = True) -> Peer:
        connection = self.connection_for_send_message()
        platform = GdriveFilesPlatform()

        if verbose:
            print_peer_adding_to_platform(peer_email, platform.module_path)

        connection.add_peer_as_do(peer_email=peer_email)

        if verbose:
            print_peer_added_to_platform(peer_email, platform.module_path)
        return Peer(email=peer_email, platforms=[platform])

    def add_peer_as_ds(self, peer_email: str, verbose: bool = True) -> Peer:
        connection = self.connection_for_receive_message()
        platform = GdriveFilesPlatform()

        if verbose:
            print_peer_adding_to_platform(peer_email, platform.module_path)

        connection.add_peer_as_ds(peer_email=peer_email)

        if verbose:
            print_peer_added_to_platform(peer_email, platform.module_path)
        return Peer(email=peer_email, platforms=[platform])

    def delete_syftbox(self):
        connection = self.connection_for_own_syftbox()
        connection.delete_syftbox()

    def write_event_to_syftbox(self, event: FileChangeEvent):
        connection = self.connection_for_eventlog()
        connection.write_event_to_syftbox(event)

    def write_event_to_outbox_do(self, sender_email: str, event: FileChangeEvent):
        connection = self.connection_for_outbox()
        connection.write_event_to_outbox_do(sender_email, event)

    def get_all_accepted_events_do(self) -> List[FileChangeEvent]:
        connection = self.connection_for_eventlog()
        return connection.get_all_events_do()

    def get_next_proposed_filechange_message(
        self, sender_email: str = None
    ) -> ProposedFileChangesMessage | None:
        connection = self.connection_for_receive_message()
        return connection.get_next_proposed_filechange_message(
            sender_email=sender_email
        )

    def get_peers_as_do(self) -> List[Peer]:
        connection = self.connection_for_send_message()
        peer_emails = connection.get_peers_as_do()
        return [
            Peer(email=peer_email, platforms=[GdriveFilesPlatform()])
            for peer_email in peer_emails
        ]

    def get_peers_as_ds(self) -> List[Peer]:
        connection = self.connection_for_receive_message()
        peer_emails = connection.get_peers_as_ds()
        return [
            Peer(email=peer_email, platforms=[GdriveFilesPlatform()])
            for peer_email in peer_emails
        ]

    def remove_proposed_filechange_from_inbox(
        self, proposed_filechange_message: ProposedFileChangesMessage
    ):
        connection = self.connection_for_receive_message()
        connection.remove_proposed_filechange_message_from_inbox(
            proposed_filechange_message
        )

    def get_events_for_datasite_watcher(
        self, peer_email: str, since_timestamp: float | None
    ) -> List[FileChangeEvent]:
        connection = self.connection_for_datasite_watcher()
        return connection.get_events_for_datasite_watcher(
            peer_email=peer_email, since_timestamp=since_timestamp
        )
