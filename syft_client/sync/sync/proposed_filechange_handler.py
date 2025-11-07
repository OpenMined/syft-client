from pydantic import ConfigDict, Field, BaseModel
from queue import Queue
from typing import Tuple
from syft_client.sync.events.file_change_event import (
    FileChangeEventsMessage,
)
from syft_client.sync.connections.base_connection import ConnectionConfig
from typing import List
from syft_client.sync.sync.caches.datasite_owner_cache import (
    DataSiteOwnerEventCacheConfig,
)
from syft_client.sync.connections.connection_router import ConnectionRouter
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

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
    event_cache: DataSiteOwnerEventCache = Field(
        default_factory=lambda: DataSiteOwnerEventCache()
    )
    write_files: bool = True
    connection_router: ConnectionRouter
    initial_sync_done: bool = False
    email: str

    syftbox_events_queue: Queue[FileChangeEventsMessage] = Field(default_factory=Queue)
    outbox_queue: Queue[Tuple[str, FileChangeEventsMessage]] = Field(
        default_factory=Queue
    )

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
            self.process_syftbox_events_queue()

    def pull_initial_state(self):
        # pull all events from the syftbox
        events_messages: list[FileChangeEventsMessage] = (
            self.connection_router.get_all_accepted_events_messages_do()
        )
        for events_message in events_messages:
            self.event_cache.add_events_message_to_local_cache(events_message)
        self.initial_sync_done = True

    def process_local_changes(self, recipients: list[str]):
        # TODO: currently permissions are not implemented, so we just write to all recipients
        file_change_events_message = self.event_cache.process_local_file_changes()
        if file_change_events_message is not None:
            self.queue_event_for_syftbox(
                recipients=recipients,
                file_change_events_message=file_change_events_message,
            )
            self.process_syftbox_events_queue()

    def pull_and_process_next_proposed_filechange(
        self, sender_email: str, raise_on_none=True
    ) -> ProposedFileChangesMessage | None:
        # raise on none is useful for testing, shouldnt be used in production
        message = self.connection_router.get_next_proposed_filechange_message(
            sender_email=sender_email
        )
        if message is not None:
            sender_email = message.sender_email
            self.handle_proposed_filechange_events_message(sender_email, message)

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

    def handle_proposed_filechange_events_message(
        self, sender_email: str, proposed_events_message: ProposedFileChangesMessage
    ):
        # for event in proposed_events_message.events:
        #     self.check_permissions(event.path_in_datasite)

        accepted_events_message = self.event_cache.process_proposed_events_message(
            proposed_events_message
        )
        self.queue_event_for_syftbox(
            recipients=[sender_email],
            file_change_events_message=accepted_events_message,
        )

    def queue_event_for_syftbox(
        self, recipients: list[str], file_change_events_message: FileChangeEventsMessage
    ):
        self.syftbox_events_queue.put(file_change_events_message)

        for recipient in recipients:
            self.outbox_queue.put((recipient, file_change_events_message))

    def process_syftbox_events_queue(self):
        # TODO: make this atomic
        while not self.syftbox_events_queue.empty():
            file_change_events_message = self.syftbox_events_queue.get()
            self.connection_router.write_events_message_to_syftbox(
                file_change_events_message
            )
        while not self.outbox_queue.empty():
            recipient, file_change_events_message = self.outbox_queue.get()
            self.connection_router.write_event_messages_to_outbox_do(
                recipient, file_change_events_message
            )

    def write_file_filesystem(self, path: str, content: str):
        if self.write_files:
            raise NotImplementedError("Writing files to filesystem is not implemented")
