from pathlib import Path

import yaml
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
from syft_client.sync.checkpoints.checkpoint import Checkpoint
from syft_client.sync.checkpoints.rolling_state import RollingState

# Default threshold for auto-checkpoint creation
DEFAULT_CHECKPOINT_EVENT_THRESHOLD = 50

# Default: upload rolling state to GDrive after this many events
DEFAULT_ROLLING_STATE_UPLOAD_THRESHOLD = 1


class DatasiteOwnerSyncerConfig(BaseModel):
    email: str
    syftbox_folder: Path | None = None
    write_files: bool = True
    # Full path to collections folder - must be provided explicitly
    collections_folder: Path | None = None
    cache_config: DataSiteOwnerEventCacheConfig = Field(
        default_factory=DataSiteOwnerEventCacheConfig
    )
    connection_configs: List[ConnectionConfig] = []


class DatasiteOwnerSyncer(BaseModelCallbackMixin):
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
    # Full path to collections folder
    collections_folder: Path | None = None

    syftbox_events_queue: Queue[FileChangeEventsMessage] = Field(default_factory=Queue)
    outbox_queue: Queue[Tuple[str, FileChangeEventsMessage]] = Field(
        default_factory=Queue
    )

    _executor: ThreadPoolExecutor = PrivateAttr(
        default_factory=lambda: ThreadPoolExecutor(max_workers=10)
    )
    # Cache of datasets shared with "any" - list of (tag, content_hash) tuples
    _any_shared_datasets: List[tuple] = PrivateAttr(default_factory=list)

    # In-memory rolling state for tracking events since last checkpoint
    _rolling_state: RollingState | None = PrivateAttr(default=None)
    # Counter for events since last rolling state upload
    _events_since_rolling_state_upload: int = PrivateAttr(default=0)

    @classmethod
    def from_config(cls, config: DatasiteOwnerSyncerConfig):
        # Ensure cache config has the same collections_folder (both are now full paths)
        if config.collections_folder is not None:
            config.cache_config.collections_folder = config.collections_folder
        return cls(
            event_cache=DataSiteOwnerEventCache.from_config(config.cache_config),
            write_files=config.write_files,
            connection_router=ConnectionRouter.from_configs(config.connection_configs),
            email=config.email,
            syftbox_folder=config.syftbox_folder,
            collections_folder=config.collections_folder,
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
        """
        Pull initial state from Google Drive.

        Uses checkpoint + rolling state for fastest sync:
        1. Download checkpoint (if exists)
        2. Download rolling state (if exists and matches checkpoint)
        3. Apply both to restore complete state
        4. Download only events newer than rolling state (usually 0-few)
        """
        # Try to use checkpoint for faster sync
        checkpoint = self.connection_router.get_latest_checkpoint()
        rolling_state = self.connection_router.get_rolling_state()

        # Get latest cached timestamp to only download new events
        since_timestamp = self.event_cache.latest_cached_timestamp

        if checkpoint is not None:
            # Restore from checkpoint
            print(f"Found checkpoint with {len(checkpoint.files)} files, restoring...")
            self.event_cache.apply_checkpoint(checkpoint, write_files=self.write_files)

            # Initialize in-memory rolling state
            base_timestamp = checkpoint.last_event_timestamp or checkpoint.timestamp
            self._rolling_state = RollingState(
                email=self.email,
                base_checkpoint_timestamp=base_timestamp,
            )

            # Determine the timestamp to sync from
            events_since_timestamp = checkpoint.last_event_timestamp

            # Check if rolling state matches this checkpoint
            if rolling_state is not None:
                if rolling_state.base_checkpoint_timestamp == base_timestamp:
                    # Rolling state is valid - apply it
                    print(
                        f"Found rolling state with {rolling_state.event_count} events, "
                        "applying..."
                    )
                    self._apply_rolling_state_to_cache(rolling_state)
                    self._rolling_state = rolling_state

                    # Only need events AFTER the rolling state
                    if rolling_state.last_event_timestamp is not None:
                        events_since_timestamp = rolling_state.last_event_timestamp
                else:
                    # Rolling state is stale (different checkpoint) - ignore it
                    print("Rolling state is stale, ignoring...")

            # Download any remaining events since checkpoint/rolling state
            if events_since_timestamp is not None:
                events_messages = (
                    self.connection_router.get_events_messages_since_timestamp(
                        events_since_timestamp
                    )
                )
                if events_messages:
                    print(
                        f"Downloading {len(events_messages)} events since "
                        "checkpoint/rolling state..."
                    )
                    for events_message in events_messages:
                        self.event_cache.add_events_message_to_local_cache(
                            events_message
                        )
                        # Add to rolling state for future syncs
                        self._add_events_to_rolling_state(events_message)
        else:
            # No checkpoint - download all events (fallback)
            print("No checkpoint found, downloading all events...")
            events_messages: list[FileChangeEventsMessage] = (
                self.get_all_accepted_events_messages_do(
                    since_timestamp=since_timestamp
                )
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
        from syft_client.sync.file_utils import compute_directory_hash

        result = []
        for collection in collections:
            # Use cached hash from event_cache first
            cached_hash = self.event_cache.get_collection_hash(collection.tag)
            if cached_hash is None and self.collections_folder is not None:
                # Fallback: compute hash from local filesystem (for locally created datasets)
                local_dataset_dir = self.collections_folder / collection.tag
                cached_hash = compute_directory_hash(local_dataset_dir)
                # Update cache if we computed a hash
                if cached_hash is not None:
                    self.event_cache.set_collection_hash(collection.tag, cached_hash)

            if cached_hash != collection.content_hash:
                result.append(collection)
        return result

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
            local_dataset_dir = self.collections_folder / collection.tag
            local_dataset_dir.mkdir(parents=True, exist_ok=True)
            (local_dataset_dir / metadata["file_name"]).write_bytes(content)

        # Update cached hashes for downloaded collections
        for collection in collections:
            self.event_cache.set_collection_hash(
                collection.tag, collection.content_hash
            )

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
        """Check if path is under app_data/job/. This is a hack which will be removed after permissions are implemented."""
        return "app_data/job/" in str(path)

    def _get_job_submitter(self, path: Path) -> str | None:
        """Return submitted_by email for a job file. Returns None if not found. This is a hack which will be removed after permissions are implemented."""
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
        if accepted_events_message is not None:
            self.queue_event_for_syftbox(
                recipients=[sender_email],
                file_change_events_message=accepted_events_message,
            )
            # Add to rolling state after processing
            self._add_events_to_rolling_state(accepted_events_message)

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

    # =========================================================================
    # ROLLING STATE METHODS
    # =========================================================================

    def _apply_rolling_state_to_cache(self, rolling_state: RollingState) -> None:
        """Apply events from rolling state to the cache."""
        for event in rolling_state.events:
            if event.is_deleted:
                if event.path_in_datasite in self.event_cache.file_hashes:
                    del self.event_cache.file_hashes[event.path_in_datasite]
                if self.write_files:
                    self.event_cache.file_connection.delete_file(
                        str(event.path_in_datasite)
                    )
            else:
                self.event_cache.file_hashes[event.path_in_datasite] = event.new_hash
                if self.write_files:
                    self.event_cache.file_connection.write_file(
                        str(event.path_in_datasite), event.content
                    )

    def _add_events_to_rolling_state(
        self,
        events_message: FileChangeEventsMessage,
        upload_threshold: int = DEFAULT_ROLLING_STATE_UPLOAD_THRESHOLD,
    ) -> None:
        """
        Add events to the in-memory rolling state and upload if threshold is reached.

        Args:
            events_message: The events to add.
            upload_threshold: Upload to GDrive after this many events added.
        """
        if self._rolling_state is None:
            return

        self._rolling_state.add_events_message(events_message)
        self._events_since_rolling_state_upload += len(events_message.events)

        # Upload if threshold reached
        if self._events_since_rolling_state_upload >= upload_threshold:
            self._upload_rolling_state()

    def _upload_rolling_state(self) -> None:
        """Upload the in-memory rolling state to GDrive."""
        if self._rolling_state is None or self._rolling_state.event_count == 0:
            return

        print(
            f"Uploading rolling state with {self._rolling_state.event_count} events..."
        )
        self.connection_router.upload_rolling_state(self._rolling_state)
        self._events_since_rolling_state_upload = 0

    # =========================================================================
    # CHECKPOINT METHODS
    # =========================================================================

    def create_checkpoint(self) -> Checkpoint:
        """
        Create a checkpoint from current state and upload to Google Drive.

        Also deletes the rolling state and resets in-memory tracking.

        Returns:
            The created Checkpoint object.
        """
        # Get the latest event timestamp
        last_event_timestamp = self.event_cache.get_latest_event_timestamp()

        # Create checkpoint from current cache state
        checkpoint = self.event_cache.create_checkpoint(
            last_event_timestamp=last_event_timestamp
        )

        # Upload to Google Drive
        print(f"Creating checkpoint with {len(checkpoint.files)} files...")
        self.connection_router.upload_checkpoint(checkpoint)

        # Delete rolling state from GDrive and reset in-memory state
        self.connection_router.delete_rolling_state()
        base_timestamp = last_event_timestamp or checkpoint.timestamp
        self._rolling_state = RollingState(
            email=self.email,
            base_checkpoint_timestamp=base_timestamp,
        )
        self._events_since_rolling_state_upload = 0

        print("Checkpoint uploaded, rolling state reset!")

        return checkpoint

    def should_create_checkpoint(
        self, threshold: int = DEFAULT_CHECKPOINT_EVENT_THRESHOLD
    ) -> bool:
        """
        Check if we should create a checkpoint based on event count.

        Args:
            threshold: Create checkpoint if events since last checkpoint >= threshold.

        Returns:
            True if checkpoint should be created.
        """
        # Get latest checkpoint timestamp
        checkpoint = self.connection_router.get_latest_checkpoint()
        checkpoint_timestamp = checkpoint.last_event_timestamp if checkpoint else None

        # Count events since checkpoint
        events_count = self.connection_router.get_events_count_since_checkpoint(
            checkpoint_timestamp
        )

        return events_count >= threshold

    def try_create_checkpoint(
        self, threshold: int = DEFAULT_CHECKPOINT_EVENT_THRESHOLD
    ) -> Checkpoint | None:
        """
        Try to create checkpoint if event count exceeds threshold.

        Args:
            threshold: Create checkpoint if events since last checkpoint >= threshold.

        Returns:
            The created Checkpoint, or None if checkpoint was not needed.
        """
        if self.should_create_checkpoint(threshold):
            return self.create_checkpoint()
        return None
