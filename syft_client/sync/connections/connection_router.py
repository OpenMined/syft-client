from pydantic import BaseModel
from typing import List
from syft_client.sync.connections.base_connection import (
    SyftboxPlatformConnection,
    ConnectionConfig,
)
from syft_client.sync.connections.drive.gdrive_transport import GDriveConnection
from syft_client.sync.events.file_change_event import (
    FileChangeEventsMessage,
)
from syft_client.sync.messages.proposed_filechange import ProposedFileChangesMessage
from syft_client.sync.platforms.gdrive_files_platform import GdriveFilesPlatform
from syft_client.sync.peers.peer import Peer
from syft_client.sync.utils.print_utils import (
    print_peer_adding_to_platform,
    print_peer_added_to_platform,
)


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
            return GDriveConnection.from_token_path(
                connection.email, connection.token_path
            )
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

    def download_events_message_by_id(
        self, events_message_id: str
    ) -> FileChangeEventsMessage:
        connection = self.connection_for_eventlog()
        return connection.download_event_message_by_id(events_message_id)

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

    # def delete_syftbox(self):
    #     connection = self.connection_for_own_syftbox()
    #     connection.delete_syftbox()

    def delete_multiple_files_by_ids(self, file_ids: List[str]):
        connection = self.connection_for_own_syftbox()
        connection.delete_multiple_files_by_ids(file_ids)

    def get_all_accepted_event_file_ids_do(self) -> List[str]:
        connection = self.connection_for_eventlog()
        return connection.get_all_accepted_event_file_ids_do()

    def gather_all_file_and_folder_ids(self) -> List[str]:
        connection = self.connection_for_own_syftbox()
        return connection.gather_all_file_and_folder_ids()

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
        self, sender_email: str, events_message: FileChangeEventsMessage
    ):
        connection = self.connection_for_outbox()
        connection.write_event_messages_to_outbox_do(sender_email, events_message)

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

    def get_events_messages_for_datasite_watcher(
        self, peer_email: str, since_timestamp: float | None
    ) -> List[FileChangeEventsMessage]:
        connection = self.connection_for_datasite_watcher()
        return connection.get_events_messages_for_datasite_watcher(
            peer_email=peer_email, since_timestamp=since_timestamp
        )

    def create_dataset_collection_folder(self, tag: str, owner_email: str) -> str:
        connection = self.connection_for_send_message()
        return connection.create_dataset_collection_folder(tag, owner_email)

    def share_dataset_collection(self, tag: str, users: list[str] | str) -> None:
        connection = self.connection_for_send_message()
        connection.share_dataset_collection(tag, users)

    def upload_dataset_files(self, tag: str, files: dict[str, bytes]) -> None:
        connection = self.connection_for_send_message()
        connection.upload_dataset_files(tag, files)

    def list_dataset_collections_as_do(self) -> list[str]:
        connection = self.connection_for_send_message()
        return connection.list_dataset_collections_as_do()

    def list_dataset_collections_as_ds(self) -> list[str]:
        connection = self.connection_for_receive_message()
        return connection.list_dataset_collections_as_ds()

    def download_dataset_collection(
        self, tag: str, owner_email: str
    ) -> dict[str, bytes]:
        connection = self.connection_for_datasite_watcher()
        return connection.download_dataset_collection(tag, owner_email)
