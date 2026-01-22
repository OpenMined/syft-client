from pathlib import Path

import yaml
from syft_datasets.dataset_manager import FOLDER_NAME as DATASETS_FOLDER_NAME
from pydantic import ConfigDict, Field, BaseModel, PrivateAttr
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from typing import List, Tuple
from syft_client.sync.events.file_change_event import (
    FileChangeEventsMessage,
)
from syft_client.sync.connections.base_connection import (
    ConnectionConfig,
    FileCollection,
)
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

    def get_all_accepted_events_messages_do(
        self, since_timestamp: float | None = None
    ) -> list[FileChangeEventsMessage]:
        message_ids = self.connection_router.get_all_accepted_event_file_ids_do(
            since_timestamp=since_timestamp
        )
        result_messages = self._executor.map(
            self.download_events_message_by_id_with_connection, message_ids
        )
        return list(result_messages)

    def pull_initial_state(self):
        # Get latest cached timestamp to only download new events
        since_timestamp = self.event_cache.latest_cached_timestamp

        # Only download events newer than cached
        events_messages = self.get_all_accepted_events_messages_do(
            since_timestamp=since_timestamp
        )

        for events_message in events_messages:
            self.event_cache.add_events_message_to_local_cache(events_message)

        # load datasets from connection and populate cache
        self._pull_datasets_for_initial_sync()

        self.initial_sync_done = True

    def _pull_datasets_for_initial_sync(self):
        """Load datasets from GDrive when DO connects.

        Restores datasets to local filesystem and populates the _any_shared_datasets cache.
        """
        if self.syftbox_folder is None:
            return

        collections = (
            self.connection_router.list_all_dataset_collections_as_do_with_permissions()
        )

        self._update_any_shared_datasets_cache(collections)

        collections_to_download = self._filter_collections_needing_download(collections)
        self._download_dataset_collections_parallel(collections_to_download)

    def _update_any_shared_datasets_cache(self, collections: list[FileCollection]):
        """Populate _any_shared_datasets cache from collections with 'any' permission."""
        for collection in collections:
            if collection.has_any_permission:
                entry = (collection.tag, collection.content_hash)
                if entry not in self._any_shared_datasets:
                    self._any_shared_datasets.append(entry)

    def _filter_collections_needing_download(
        self, collections: list[FileCollection]
    ) -> list[FileCollection]:
        """Return collections that don't exist locally or have different content hash."""
        result = []
        for collection in collections:
            local_dataset_dir = (
                self.syftbox_folder
                / self.email
                / "public"
                / DATASETS_FOLDER_NAME
                / collection.tag
            )
            local_hash = self._compute_local_dataset_hash(local_dataset_dir)
            if local_hash != collection.content_hash:
                result.append(collection)
        return result

    def _compute_local_dataset_hash(self, dataset_dir: Path) -> str | None:
        """Compute content hash from local dataset files on disk."""
        from syft_client.sync.connections.drive.gdrive_transport import (
            DatasetCollectionFolder,
        )

        if not dataset_dir.exists():
            return None

        files = {}
        for file_path in dataset_dir.iterdir():
            if file_path.is_file():
                files[file_path.name] = file_path.read_bytes()

        return DatasetCollectionFolder.compute_hash(files) if files else None

    def _download_dataset_collections_parallel(self, collections: list[FileCollection]):
        """Download all files from collections in parallel and write to disk."""
        if not collections:
            return

        # Fetch file metadatas for all collections in parallel
        all_file_metadatas = list(
            self._executor.map(
                self._get_file_metadatas_with_new_connection, collections
            )
        )

        # Build list of (collection, file_metadata) tuples
        all_downloads = [
            (collection, metadata)
            for collection, file_metadatas in zip(collections, all_file_metadatas)
            for metadata in file_metadatas
        ]

        if not all_downloads:
            return

        # Download all files in parallel
        file_ids = [metadata["file_id"] for _, metadata in all_downloads]
        downloaded_contents = list(
            self._executor.map(self._download_file_with_new_connection, file_ids)
        )

        # Write all files to disk
        for (collection, metadata), content in zip(all_downloads, downloaded_contents):
            local_dataset_dir = (
                self.syftbox_folder
                / self.email
                / "public"
                / DATASETS_FOLDER_NAME
                / collection.tag
            )
            local_dataset_dir.mkdir(parents=True, exist_ok=True)
            (local_dataset_dir / metadata["file_name"]).write_bytes(content)

    def _get_file_metadatas_with_new_connection(
        self, collection: FileCollection
    ) -> list:
        """Get file metadatas for a collection using a new connection for thread safety."""
        connection = self.connection_router.connection_for_parallel_download()
        return connection.get_dataset_collection_file_metadatas(
            tag=collection.tag,
            content_hash=collection.content_hash,
            owner_email=self.email,
        )

    def _download_file_with_new_connection(self, file_id: str) -> bytes:
        """Download a file using a new connection for thread safety."""
        connection = self.connection_router.connection_for_parallel_download()
        return connection.download_dataset_file(file_id)

    def _is_job_path(self, path: Path) -> bool:
        """Check if path is under app_data/job/."""
        return "app_data/job/" in str(path)

    def _get_job_submitter(self, path: Path) -> str | None:
        """Return submitted_by email for a job file. Returns None if not found."""
        parts = path.parts
        try:
            job_idx = parts.index("job")
            job_name = parts[job_idx + 1]
            job_dir = self.syftbox_folder / self.email / "app_data" / "job" / job_name
            config_path = job_dir / "config.yaml"
            if config_path.exists():
                with open(config_path) as f:
                    config = yaml.safe_load(f)
                return config.get("submitted_by")
        except (ValueError, IndexError, Exception):
            pass
        return None

    def process_local_changes(self, recipients: list[str]):
        file_change_events_message = self.event_cache.process_local_file_changes()
        if file_change_events_message is None:
            return

        # Write all events to the syftbox events queue (local storage)
        self.syftbox_events_queue.put(file_change_events_message)

        # Group events by recipient for outbox filtering
        events_by_recipient: dict[str, list] = {r: [] for r in recipients}

        for event in file_change_events_message.events:
            path = Path(event.path_in_datasite)

            if self._is_job_path(path):
                # Job file - get submitter
                submitter = self._get_job_submitter(path)
                if submitter is None:
                    # Can't determine submitter - skip this event (don't leak)
                    continue
                # Only send to submitter if they're in recipients
                if submitter in events_by_recipient:
                    events_by_recipient[submitter].append(event)
            else:
                # Non-job file - send to all recipients
                for recipient in recipients:
                    events_by_recipient[recipient].append(event)

        # Queue filtered events per recipient for outbox
        for recipient, events in events_by_recipient.items():
            if events:
                msg = FileChangeEventsMessage(events=events)
                self.outbox_queue.put((recipient, msg))

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
