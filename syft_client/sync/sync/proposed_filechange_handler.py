from pathlib import Path
from pydantic import ConfigDict, Field, BaseModel, PrivateAttr
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from typing import List, Tuple
from syft_client.sync.events.file_change_event import (
    FileChangeEventsMessage,
)
from syft_client.sync.connections.base_connection import ConnectionConfig
from syft_client.sync.sync.caches.datasite_owner_cache import (
    DataSiteOwnerEventCacheConfig,
)
from syft_client.sync.connections.connection_router import ConnectionRouter
from syft_client.sync.sync.caches.datasite_owner_cache import DataSiteOwnerEventCache
from syft_client.sync.callback_mixin import BaseModelCallbackMixin
from syft_client.sync.messages.proposed_filechange import ProposedFileChangesMessage


class ProposedFileChangeHandlerConfig(BaseModel):
    email: str
    syftbox_folder: Path | None = None
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
    syftbox_folder: Path | None = None

    syftbox_events_queue: Queue[FileChangeEventsMessage] = Field(default_factory=Queue)
    outbox_queue: Queue[Tuple[str, FileChangeEventsMessage]] = Field(
        default_factory=Queue
    )

    _executor: ThreadPoolExecutor = PrivateAttr(
        default_factory=lambda: ThreadPoolExecutor(max_workers=10)
    )
    # Cache of datasets shared with "any" - list of (tag, content_hash) tuples
    _any_shared_datasets: List[tuple] = PrivateAttr(default_factory=list)

    @classmethod
    def from_config(cls, config: ProposedFileChangeHandlerConfig):
        return cls(
            event_cache=DataSiteOwnerEventCache.from_config(config.cache_config),
            write_files=config.write_files,
            connection_router=ConnectionRouter.from_configs(config.connection_configs),
            email=config.email,
            syftbox_folder=config.syftbox_folder,
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

    def download_events_message_by_id_with_connection(
        self, events_message_id: str
    ) -> FileChangeEventsMessage:
        # we need a new connection object because gdrive connections are not thread safe
        connection = self.connection_router.connection_for_eventlog(create_new=True)
        return connection.download_events_message_by_id(events_message_id)

    def get_all_accepted_events_messages_do(self) -> list[FileChangeEventsMessage]:
        message_ids = self.connection_router.get_all_accepted_event_file_ids_do()
        result_messages = self._executor.map(
            self.download_events_message_by_id_with_connection, message_ids
        )
        return list(result_messages)

    def pull_initial_state(self):
        # pull all events from the syftbox
        events_messages: list[FileChangeEventsMessage] = (
            self.get_all_accepted_events_messages_do()
        )

        for events_message in events_messages:
            self.event_cache.add_events_message_to_local_cache(events_message)

        # load datasets from connection and populate cache
        self._load_datasets_from_connection()

        self.initial_sync_done = True

    def _load_datasets_from_connection(self):
        """Load datasets from GDrive when DO connects.

        This restores datasets to local filesystem so they appear in datasets.get_all(),
        and populates the _any_shared_datasets cache for efficient peer sharing.
        Downloads all datasets in parallel for speed.
        """
        if self.syftbox_folder is None:
            return

        try:
            collections = self.connection_router.list_all_dataset_collections_as_do_with_permissions()
        except Exception:
            # Connection may not support this (e.g., not fully set up)
            return

        # Populate _any_shared_datasets cache (avoid duplicates)
        for collection in collections:
            if collection["has_any_permission"]:
                entry = (collection["tag"], collection["content_hash"])
                if entry not in self._any_shared_datasets:
                    self._any_shared_datasets.append(entry)

        # Download all datasets in parallel
        list(
            self._executor.map(
                self._restore_dataset_to_local_from_collection, collections
            )
        )

    def _restore_dataset_to_local_from_collection(self, collection: dict):
        """Download dataset files from GDrive and write to local filesystem.

        Uses a new connection for thread safety during parallel downloads.
        """
        from syft_datasets.dataset_manager import FOLDER_NAME

        if self.syftbox_folder is None:
            return

        tag = collection["tag"]
        content_hash = collection["content_hash"]

        # Check if dataset already exists locally
        local_dataset_dir = (
            self.syftbox_folder / self.email / "public" / FOLDER_NAME / tag
        )
        metadata_path = local_dataset_dir / "dataset.yaml"
        if metadata_path.exists():
            # Already exists locally, skip
            return

        try:
            # Use a new connection for thread safety
            connection = self.connection_router.connection_for_parallel_download()
            files = connection.download_dataset_collection(
                tag=tag, content_hash=content_hash, owner_email=self.email
            )

            # Write files to local filesystem
            local_dataset_dir.mkdir(parents=True, exist_ok=True)
            for filename, content in files.items():
                file_path = local_dataset_dir / filename
                file_path.write_bytes(content)
        except Exception:
            # Failed to download, skip this dataset
            pass

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
