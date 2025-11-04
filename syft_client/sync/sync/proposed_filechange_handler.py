from pydantic import ConfigDict, Field, BaseModel
from syft_client.sync.events.file_change_event import FileChangeEvent
from syft_client.sync.connections.base_connection import ConnectionConfig
from typing import List
from syft_client.sync.sync.caches.datasite_owner_cache import (
    DataSiteOwnerEventCacheConfig,
)
from syft_client.sync.connections.connection_router import ConnectionRouter
from syft_client.sync.messages.proposed_filechange import ProposedFileChange
from syft_client.sync.sync.caches.datasite_owner_cache import DataSiteOwnerEventCache
from syft_client.sync.callback_mixin import BaseModelCallbackMixin
from syft_client.sync.messages.proposed_filechange import ProposedFileChangesMessage


class ProposedFileChangeHandlerConfig(BaseModel):
    email: str
    write_files: bool = True
    cache_config: DataSiteOwnerEventCacheConfig = Field(
        default_factory=DataSiteOwnerEventCacheConfig
    )
    connection_configs: List[ConnectionConfig] = []


class ProposedFileChangeHandler(BaseModelCallbackMixin):
    """Responsible for downloading files and checking permissions"""

    model_config = ConfigDict(extra="allow")
    event_cache: DataSiteOwnerEventCache = Field(
        default_factory=lambda: DataSiteOwnerEventCache()
    )
    write_files: bool = True
    connection_router: ConnectionRouter
    initial_sync_done: bool = False
    email: str

    @classmethod
    def from_config(cls, config: ProposedFileChangeHandlerConfig):
        return cls(
            event_cache=DataSiteOwnerEventCache.from_config(config.cache_config),
            write_files=config.write_files,
            connection_router=ConnectionRouter.from_configs(config.connection_configs),
            email=config.email,
        )

    def sync(self, peer_emails: list[str], recompute_hashes: bool = True):
        if not self.initial_sync_done:
            self.pull_initial_state()

        if recompute_hashes:
            self.process_local_changes(recipients=peer_emails)

        # first, pull existing state
        for peer_email in peer_emails:
            while True:
                msg = self.pull_and_process_next_proposed_filechange(
                    peer_email, raise_on_none=False
                )
                if msg is None:
                    # no new message, we are done
                    break

    def pull_initial_state(self):
        # pull all events from the syftbox
        events: list[FileChangeEvent] = (
            self.connection_router.get_all_accepted_events_do()
        )
        for event in events:
            self.event_cache.add_event_to_local_cache(event)
        self.initial_sync_done = True

    def process_local_changes(self, recipients: list[str]):
        # TODO: currently permissions are not implemented, so we just write to all recipients
        events = self.event_cache.process_local_file_changes()
        for event in events:
            self.write_event_to_syftbox(recipients=recipients, event=event)

    def pull_and_process_next_proposed_filechange(
        self, sender_email: str, raise_on_none=True
    ) -> ProposedFileChangesMessage | None:
        # raise on none is useful for testing, shouldnt be used in production
        message = self.connection_router.get_next_proposed_filechange_message(
            sender_email=sender_email
        )
        if message is not None:
            sender_email = message.sender_email
            for proposed_file_change in message.proposed_file_changes:
                self.handle_proposed_filechange_event(
                    sender_email, proposed_file_change
                )

            # delete the message once we are done
            self.connection_router.remove_proposed_filechange_from_inbox(message)
            return message
        elif raise_on_none:
            raise ValueError("No proposed file change to process")
        else:
            return None

    # def on_proposed_filechange_receive(
    #     self, proposed_file_change_message: ProposedFileChangesMessage
    # ):
    #     for proposed_file_change in proposed_file_change_message.proposed_file_changes:
    #         for callback in self.callbacks.get("on_proposed_filechange_receive", []):
    #             callback(proposed_file_change)

    def check_permissions(self, path: str):
        pass

    def handle_proposed_filechange_event(
        self, sender_email: str, proposed_event: ProposedFileChange
    ):
        self.check_permissions(proposed_event.path)

        accepted_event = self.event_cache.process_proposed_event(proposed_event)
        self.write_event_to_syftbox(recipients=[sender_email], event=accepted_event)

    def write_event_to_syftbox(self, recipients: list[str], event: FileChangeEvent):
        self.connection_router.write_event_to_syftbox(event)
        for recipient in recipients:
            self.connection_router.write_event_to_outbox_do(recipient, event)

    def write_file_filesystem(self, path: str, content: str):
        if self.write_files:
            raise NotImplementedError("Writing files to filesystem is not implemented")
