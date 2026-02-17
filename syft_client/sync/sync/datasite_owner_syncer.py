from pathlib import Path
from uuid import uuid4

import yaml
from pydantic import ConfigDict, Field, BaseModel, PrivateAttr
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from typing import List, Tuple
from syft_client.sync.events.file_change_event import (
    FileChangeEventsMessage,
    FileChangeEvent,
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
from syft_client.sync.checkpoints.checkpoint import (
    Checkpoint,
    CheckpointFile,
    IncrementalCheckpoint,
    compact_incremental_checkpoints,
    DEFAULT_COMPACTING_THRESHOLD,
)
from syft_client.sync.checkpoints.rolling_state import RollingState

# Default threshold for creating incremental checkpoint from rolling state
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

        Flow:
        1. Check for full (compacted) checkpoint → apply it
        2. Check for incremental checkpoints → apply them in order
        3. Check for rolling state → apply if valid
        4. Download any remaining events since last timestamp
        """
        events_since_timestamp: float | None = None

        # Step 1: Check for full (compacted) checkpoint
        full_checkpoint = self.connection_router.get_latest_checkpoint()
        if full_checkpoint is not None:
            print(
                f"Found full checkpoint with {len(full_checkpoint.files)} files, "
                "restoring..."
            )
            self.event_cache.apply_checkpoint(
                full_checkpoint, write_files=self.write_files
            )
            events_since_timestamp = full_checkpoint.last_event_timestamp

        # Step 2: Check for incremental checkpoints
        incremental_cps = self.connection_router.get_all_incremental_checkpoints()
        if incremental_cps:
            print(f"Found {len(incremental_cps)} incremental checkpoints, applying...")
            for inc_cp in incremental_cps:
                self._apply_incremental_checkpoint_to_cache(inc_cp)
                # Update timestamp to the latest event in this checkpoint
                for event in inc_cp.events:
                    if event.timestamp is not None:
                        if (
                            events_since_timestamp is None
                            or event.timestamp > events_since_timestamp
                        ):
                            events_since_timestamp = event.timestamp

        # Step 3: Check for rolling state
        rolling_state = self.connection_router.get_rolling_state()
        if rolling_state is not None and rolling_state.event_count > 0:
            print(
                f"Found rolling state with {rolling_state.event_count} events, "
                "applying..."
            )
            self._apply_rolling_state_to_cache(rolling_state)
            self._rolling_state = rolling_state

            # Update timestamp from rolling state
            if rolling_state.last_event_timestamp is not None:
                if (
                    events_since_timestamp is None
                    or rolling_state.last_event_timestamp > events_since_timestamp
                ):
                    events_since_timestamp = rolling_state.last_event_timestamp
        else:
            # Initialize empty rolling state
            base_timestamp = events_since_timestamp or 0.0
            self._rolling_state = RollingState(
                email=self.email,
                base_checkpoint_timestamp=base_timestamp,
            )

        # Step 4: Download any remaining events since last timestamp
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
                    self.event_cache.add_events_message_to_local_cache(events_message)
                    self._add_events_to_rolling_state(events_message)
        elif full_checkpoint is None and not incremental_cps:
            # No checkpoints at all - download all events (fallback)
            print("No checkpoints found, downloading all events...")
            since_timestamp = self.event_cache.latest_cached_timestamp
            events_messages_list: list[FileChangeEventsMessage] = (
                self.get_all_accepted_events_messages_do(
                    since_timestamp=since_timestamp
                )
            )
            for events_message in events_messages_list:
                self.event_cache.add_events_message_to_local_cache(events_message)

        # Load datasets from connection and populate _any_shared_datasets cache
        self._pull_datasets_for_initial_sync()

        # Restore private datasets from GDrive (owner-only collections)
        self._pull_private_datasets_for_initial_sync()

        self.initial_sync_done = True

    def _apply_incremental_checkpoint_to_cache(
        self, checkpoint: IncrementalCheckpoint
    ) -> None:
        """Apply events from an incremental checkpoint to the cache."""
        for event in checkpoint.events:
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

    # =========================================================================
    # PRIVATE DATASET RESTORE METHODS
    # =========================================================================

    def _pull_private_datasets_for_initial_sync(self):
        """Restore private datasets from GDrive when DO reconnects.

        Downloads private data from owner-only collection folders
        to {syftbox_folder}/private/syft_datasets/{tag}/.
        """
        if self.syftbox_folder is None:
            return

        collections = self.connection_router.list_private_dataset_collections_as_do()
        if not collections:
            return

        collections_to_download = self._filter_private_collections_needing_download(
            collections
        )
        self._download_private_collections_parallel(collections_to_download)

    def _filter_private_collections_needing_download(
        self, collections: list[FileCollection]
    ) -> list[FileCollection]:
        """Return private collections that don't exist locally yet."""
        result = []
        for collection in collections:
            local_dir = (
                self.syftbox_folder / "private" / "syft_datasets" / collection.tag
            )
            if not local_dir.exists() or not any(local_dir.iterdir()):
                result.append(collection)
        return result

    def _download_private_collections_parallel(self, collections: list[FileCollection]):
        """Download private collection files in parallel and write to disk."""
        if not collections:
            return

        all_file_metadatas = list(
            self._executor.map(
                self._get_private_file_metadatas_with_new_connection, collections
            )
        )

        all_downloads = [
            (collection, metadata)
            for collection, file_metadatas in zip(collections, all_file_metadatas)
            for metadata in file_metadatas
        ]

        if not all_downloads:
            return

        file_ids = [metadata["file_id"] for _, metadata in all_downloads]
        downloaded_contents = list(
            self._executor.map(self._download_file_with_new_connection, file_ids)
        )

        for (collection, metadata), content in zip(all_downloads, downloaded_contents):
            local_dir = (
                self.syftbox_folder / "private" / "syft_datasets" / collection.tag
            )
            local_dir.mkdir(parents=True, exist_ok=True)
            (local_dir / metadata["file_name"]).write_bytes(content)

        # Fix data_dir in private_metadata.yaml to point to current local path
        for collection in collections:
            self._fix_private_metadata_data_dir(collection.tag)

    def _get_private_file_metadatas_with_new_connection(
        self, collection: FileCollection
    ) -> list:
        """Get file metadatas for a private collection using a new connection."""
        connection = self.connection_router.connection_for_parallel_download()
        return connection.get_private_collection_file_metadatas(
            tag=collection.tag,
            content_hash=collection.content_hash,
            owner_email=self.email,
        )

    def _fix_private_metadata_data_dir(self, dataset_tag: str):
        """Update data_dir in private_metadata.yaml to match the current syftbox path."""
        metadata_path = (
            self.syftbox_folder
            / "private"
            / "syft_datasets"
            / dataset_tag
            / "private_metadata.yaml"
        )
        if not metadata_path.exists():
            return

        import yaml

        data = yaml.safe_load(metadata_path.read_text())
        expected_dir = str(
            self.syftbox_folder / "private" / "syft_datasets" / dataset_tag
        )
        if data.get("data_dir") != expected_dir:
            data["data_dir"] = expected_dir
            metadata_path.write_text(yaml.safe_dump(data, indent=2, sort_keys=False))

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

    def create_incremental_checkpoint(self) -> IncrementalCheckpoint:
        """
        Create an incremental checkpoint from the current rolling state.

        Deduplicates events by path (keeps only latest version per file),
        then converts to an incremental checkpoint, uploads it,
        and deletes the rolling state.

        Returns:
            The created IncrementalCheckpoint object.
        """
        if self._rolling_state is None or self._rolling_state.event_count == 0:
            raise ValueError("No rolling state to create checkpoint from")

        # Get the next sequence number
        seq_number = self.connection_router.get_next_incremental_sequence_number()

        # Deduplicate events: keep only latest version per file path
        # This reduces storage when the same file changes multiple times
        latest_events: dict[str, "FileChangeEvent"] = {}
        for event in self._rolling_state.events:
            path_key = str(event.path_in_datasite)
            latest_events[path_key] = event

        # Create incremental checkpoint with deduplicated events
        deduplicated_events = list(latest_events.values())
        incremental_cp = IncrementalCheckpoint(
            email=self.email,
            sequence_number=seq_number,
            events=deduplicated_events,
        )

        # Upload to Google Drive
        original_count = self._rolling_state.event_count
        deduplicated_count = len(deduplicated_events)
        print(
            f"Creating incremental checkpoint #{seq_number} "
            f"with {deduplicated_count} events "
            f"(deduplicated from {original_count})..."
        )
        self.connection_router.upload_incremental_checkpoint(incremental_cp)

        # Delete rolling state from GDrive and reset in-memory state
        self.connection_router.delete_rolling_state()
        base_timestamp = (
            self._rolling_state.last_event_timestamp or incremental_cp.timestamp
        )
        self._rolling_state = RollingState(
            email=self.email,
            base_checkpoint_timestamp=base_timestamp,
        )
        self._events_since_rolling_state_upload = 0

        print("Incremental checkpoint created, rolling state reset!")

        return incremental_cp

    def create_checkpoint(self) -> Checkpoint:
        """
        Create a full checkpoint from current cache state.

        This creates a full checkpoint and resets the rolling state.
        Used for legacy compatibility and when manually creating checkpoints.

        Returns:
            The created Checkpoint object.
        """
        last_event_timestamp = self.event_cache.get_latest_event_timestamp()
        checkpoint = self.event_cache.create_checkpoint(
            last_event_timestamp=last_event_timestamp
        )
        print(f"Creating full checkpoint with {len(checkpoint.files)} files...")
        self.connection_router.upload_checkpoint(checkpoint)

        # Reset rolling state after checkpoint creation
        self.connection_router.delete_rolling_state()
        base_timestamp = last_event_timestamp or checkpoint.timestamp
        self._rolling_state = RollingState(
            email=self.email,
            base_checkpoint_timestamp=base_timestamp,
        )
        self._events_since_rolling_state_upload = 0

        return checkpoint

    def should_create_checkpoint(
        self, threshold: int = DEFAULT_CHECKPOINT_EVENT_THRESHOLD
    ) -> bool:
        """
        Check if we should create an incremental checkpoint.

        Based on rolling state event count (not GDrive event files).

        Args:
            threshold: Create checkpoint if rolling state has >= threshold events.

        Returns:
            True if checkpoint should be created.
        """
        if self._rolling_state is None:
            return False
        return self._rolling_state.event_count >= threshold

    def should_compact_checkpoints(
        self, threshold: int = DEFAULT_COMPACTING_THRESHOLD
    ) -> bool:
        """
        Check if we should compact incremental checkpoints into a full checkpoint.

        Args:
            threshold: Compact if number of incremental checkpoints >= threshold.

        Returns:
            True if compacting should happen.
        """
        count = self.connection_router.get_incremental_checkpoint_count()
        return count >= threshold

    def compact_checkpoints(self) -> Checkpoint:
        """
        Compact all incremental checkpoints into a single full checkpoint.

        If an existing full checkpoint exists, it is merged with all incremental
        checkpoints to create the new full checkpoint. This ensures no data loss.

        Downloads existing full checkpoint (if any) and all incremental checkpoints,
        merges them, uploads the compacted full checkpoint, and deletes all
        incremental checkpoints.

        Returns:
            The compacted Checkpoint object.
        """
        print("Compacting incremental checkpoints...")

        # Download existing full checkpoint (if exists)
        existing_checkpoint = self.connection_router.get_latest_checkpoint()

        # Download all incremental checkpoints
        incremental_cps = self.connection_router.get_all_incremental_checkpoints()

        if not incremental_cps:
            raise ValueError("No incremental checkpoints to compact")

        print(f"Found {len(incremental_cps)} incremental checkpoints to compact")

        # Start with existing checkpoint files (if any)
        if existing_checkpoint:
            print(
                f"Merging with existing full checkpoint "
                f"({len(existing_checkpoint.files)} files)..."
            )
            # Convert existing checkpoint files to events for merging
            merged_events: dict[str, FileChangeEvent] = {}

            # Add existing checkpoint files as events
            for checkpoint_file in existing_checkpoint.files:
                # Create a FileChangeEvent from CheckpointFile
                event = FileChangeEvent(
                    id=uuid4(),
                    path_in_datasite=Path(checkpoint_file.path),
                    datasite_email=self.email,
                    content=checkpoint_file.content,
                    old_hash=None,
                    new_hash=checkpoint_file.hash,
                    is_deleted=False,
                    submitted_timestamp=existing_checkpoint.timestamp,
                    timestamp=existing_checkpoint.timestamp,
                )
                merged_events[checkpoint_file.path] = event

            # Merge incremental checkpoints on top (later events overwrite)
            for inc_cp in sorted(incremental_cps, key=lambda c: c.sequence_number):
                for event in inc_cp.events:
                    merged_events[str(event.path_in_datasite)] = event

            # Create full checkpoint from merged events
            files = []
            for event in merged_events.values():
                if not event.is_deleted and event.content is not None:
                    files.append(
                        CheckpointFile(
                            path=str(event.path_in_datasite),
                            hash=str(event.new_hash),
                            content=event.content,
                        )
                    )

            # Find latest timestamp
            last_event_timestamp = existing_checkpoint.last_event_timestamp
            for inc_cp in incremental_cps:
                for event in inc_cp.events:
                    if event.timestamp is not None:
                        if (
                            last_event_timestamp is None
                            or event.timestamp > last_event_timestamp
                        ):
                            last_event_timestamp = event.timestamp

            compacted = Checkpoint(
                email=self.email,
                files=files,
                last_event_timestamp=last_event_timestamp,
            )
        else:
            # No existing checkpoint, just merge incremental checkpoints
            compacted = compact_incremental_checkpoints(incremental_cps, self.email)

        # Upload the compacted checkpoint (this deletes old full checkpoints)
        print(f"Uploading compacted checkpoint with {len(compacted.files)} files...")
        self.connection_router.upload_checkpoint(compacted)

        # Delete all incremental checkpoints
        self.connection_router.delete_all_incremental_checkpoints()

        print("Compacting complete!")

        return compacted

    def try_create_checkpoint(
        self,
        threshold: int = DEFAULT_CHECKPOINT_EVENT_THRESHOLD,
        compacting_threshold: int = DEFAULT_COMPACTING_THRESHOLD,
    ) -> IncrementalCheckpoint | Checkpoint | None:
        """
        Try to create incremental checkpoint and/or compact if thresholds exceeded.

        Args:
            threshold: Create incremental checkpoint if rolling state has >= events.
            compacting_threshold: Compact if >= this many incremental checkpoints.

        Returns:
            The created checkpoint (incremental or compacted), or None.
        """
        result = None

        # First, check if we should create an incremental checkpoint
        if self.should_create_checkpoint(threshold):
            result = self.create_incremental_checkpoint()

            # After creating, check if we should compact
            if self.should_compact_checkpoints(compacting_threshold):
                result = self.compact_checkpoints()

        return result
