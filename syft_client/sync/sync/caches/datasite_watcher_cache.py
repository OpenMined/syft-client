from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List
from syft_client.sync.sync.caches.cache_file_writer_connection import FSFileConnection
from pathlib import Path
from pydantic import BaseModel, Field, model_validator
from datetime import datetime, timedelta
from syft_client.sync.events.file_change_event import (
    FileChangeEvent,
    FileChangeEventsMessage,
)
from syft_client.sync.connections.connection_router import ConnectionRouter
from syft_client.sync.connections.base_connection import ConnectionConfig
from syft_client.sync.sync.caches.cache_file_writer_connection import (
    CacheFileConnection,
    InMemoryCacheFileConnection,
)

SECONDS_BEFORE_SYNCING_DOWN = 0
COLLECTIONS_FOLDER_NAME = "syft_datasets"


class DataSiteWatcherCacheConfig(BaseModel):
    use_in_memory_cache: bool = True
    syftbox_folder: Path | None = None
    events_base_path: Path | None = None
    connection_configs: List[ConnectionConfig] = []
    # Base folder containing all owners' collections (the syftbox_folder)
    collections_folder: Path | None = None

    @model_validator(mode="before")
    def pre_init(cls, data):
        if data.get("events_base_path") is None and data.get("base_path") is not None:
            base_path = data["base_path"]
            base_parent = base_path.parent
            data["events_base_path"] = base_parent / "events"
        # Set collections_folder to syftbox_folder if not provided
        if data.get("collections_folder") is None and data.get("syftbox_folder"):
            data["collections_folder"] = Path(data["syftbox_folder"])
        return data


class DataSiteWatcherCache(BaseModel):
    events_connection: CacheFileConnection = Field(
        default_factory=InMemoryCacheFileConnection
    )

    file_connection: CacheFileConnection = Field(
        default_factory=InMemoryCacheFileConnection
    )

    file_hashes: Dict[str, int] = {}
    current_check_point: str = None
    connection_router: ConnectionRouter
    last_sync: datetime | None = None
    seconds_before_syncing_down: int = SECONDS_BEFORE_SYNCING_DOWN
    peers: List[str] = []
    last_event_timestamp_per_peer: Dict[str, float] = {}
    # Base folder containing all owners' collections (the syftbox_folder)
    collections_folder: Path | None = None
    # Cache of dataset collection hashes: "{owner_email}/{tag}" -> content_hash
    dataset_collection_hashes: Dict[str, str] = {}

    @classmethod
    def from_config(cls, config: DataSiteWatcherCacheConfig):
        if config.use_in_memory_cache:
            res = cls(
                events_connection=InMemoryCacheFileConnection[FileChangeEvent](),
                file_connection=InMemoryCacheFileConnection[str](),
                connection_router=ConnectionRouter.from_configs(
                    connection_configs=config.connection_configs
                ),
                collections_folder=config.collections_folder,
            )
            return res
        else:
            if config.syftbox_folder is None:
                raise ValueError("base_path is required for non-in-memory cache")

            syftbox_folder_name = Path(config.syftbox_folder).name
            syftbox_parent = Path(config.syftbox_folder).parent
            events_folder = syftbox_parent / f"{syftbox_folder_name}-event-messages"

            cache = cls(
                events_connection=FSFileConnection(
                    base_dir=events_folder, dtype=FileChangeEventsMessage
                ),
                file_connection=FSFileConnection(base_dir=config.syftbox_folder),
                connection_router=ConnectionRouter.from_configs(
                    connection_configs=config.connection_configs
                ),
                collections_folder=config.collections_folder,
            )
            cache._load_cached_state()
            return cache

    def _load_cached_state(self):
        """Load existing events from disk cache and populate last_event_timestamp_per_peer and file_hashes."""
        try:
            cached_messages = self.events_connection.get_all()
        except Exception:
            cached_messages = []

        if cached_messages:
            sorted_messages = sorted(cached_messages, key=lambda m: m.timestamp)

            for events_message in sorted_messages:
                for event in events_message.events:
                    # Update last_event_timestamp_per_peer
                    peer_email = event.datasite_email
                    current_ts = self.last_event_timestamp_per_peer.get(peer_email)
                    if current_ts is None or events_message.timestamp > current_ts:
                        self.last_event_timestamp_per_peer[peer_email] = (
                            events_message.timestamp
                        )

                    # Update file_hashes
                    path_key = Path(event.path_in_syftbox)
                    if event.is_deleted:
                        if path_key in self.file_hashes:
                            del self.file_hashes[path_key]
                    else:
                        self.file_hashes[path_key] = event.new_hash

        self._load_dataset_hashes_from_disk()

    def _load_dataset_hashes_from_disk(self):
        """Scan local dataset directories and compute hashes to populate dataset_collection_hashes."""
        for owner_email, tag in self._get_local_dataset_folders():
            content_hash = self._compute_local_dataset_hash(owner_email, tag)
            if content_hash:
                cache_key = f"{owner_email}/{tag}"
                self.dataset_collection_hashes[cache_key] = content_hash

    def get_collection_path(self, owner_email: str, tag: str) -> Path | None:
        """Get the full path to a collection for a given owner and tag."""
        if self.collections_folder is None:
            return None
        return (
            self.collections_folder
            / owner_email
            / "public"
            / COLLECTIONS_FOLDER_NAME
            / tag
        )

    def _get_local_dataset_folders(self):
        """Yield (owner_email, tag) tuples for all local dataset folders."""
        if self.collections_folder is None or not self.collections_folder.exists():
            return

        for email_dir in self.collections_folder.iterdir():
            if not email_dir.is_dir() or "@" not in email_dir.name:
                continue
            datasets_dir = email_dir / "public" / COLLECTIONS_FOLDER_NAME
            if not datasets_dir.exists():
                continue
            for tag_dir in datasets_dir.iterdir():
                if tag_dir.is_dir():
                    yield email_dir.name, tag_dir.name

    def _compute_local_dataset_hash(self, owner_email: str, tag: str) -> str | None:
        """Compute content hash from local dataset files on disk."""
        from syft_client.sync.file_utils import compute_directory_hash

        dataset_dir = self.get_collection_path(owner_email, tag)
        if dataset_dir is None:
            return None
        return compute_directory_hash(dataset_dir)

    def get_collection_hash(self, owner_email: str, tag: str) -> str | None:
        """Get the cached hash for a collection."""
        cache_key = f"{owner_email}/{tag}"
        return self.dataset_collection_hashes.get(cache_key)

    def set_collection_hash(self, owner_email: str, tag: str, content_hash: str):
        """Set the cached hash for a collection."""
        cache_key = f"{owner_email}/{tag}"
        self.dataset_collection_hashes[cache_key] = content_hash

    def clear_cache(self):
        self.events_connection.clear_cache()
        self.file_connection.clear_cache()
        self.file_hashes = {}
        self.last_sync = None
        self.peers = []
        self.current_check_point = None
        self.last_event_timestamp_per_peer = {}
        self.dataset_collection_hashes = {}

    @property
    def last_event_timestamp(self) -> float | None:
        if len(self.events_connection) == 0:
            return None
        return self.events_connection.get_latest().timestamp

    def sync_down(self, peer_email: str):
        # Use per-peer timestamp to avoid filtering out events from other peers
        peer_timestamp = self.last_event_timestamp_per_peer.get(peer_email)

        new_event_messages = (
            self.connection_router.get_events_messages_for_datasite_watcher(
                peer_email=peer_email,
                since_timestamp=peer_timestamp,
            )
        )
        for event_message in sorted(new_event_messages, key=lambda x: x.timestamp):
            self.apply_event_message(event_message)
            self.last_event_timestamp_per_peer[peer_email] = event_message.timestamp

        self.last_sync = datetime.now()

    def sync_down_parallel(
        self,
        peer_email: str,
        executor: ThreadPoolExecutor,
        download_fn: Callable[[str], FileChangeEventsMessage],
    ):
        """Sync with parallel file downloads."""
        peer_timestamp = self.last_event_timestamp_per_peer.get(peer_email)

        # Get file metadata (no download yet)
        file_metadatas = self.connection_router.get_outbox_file_metadatas_for_ds(
            peer_email=peer_email,
            since_timestamp=peer_timestamp,
        )

        if not file_metadatas:
            # No new messages to download
            self.last_sync = datetime.now()
            return

        # Download all files in parallel
        file_ids = [m["file_id"] for m in file_metadatas]
        downloaded_messages = list(executor.map(download_fn, file_ids))

        # Apply in timestamp order
        for event_message in sorted(downloaded_messages, key=lambda x: x.timestamp):
            self.apply_event_message(event_message)
            self.last_event_timestamp_per_peer[peer_email] = event_message.timestamp

        self.last_sync = datetime.now()

    def apply_event_message(self, event_message: FileChangeEventsMessage):
        self.events_connection.write_file(
            event_message.message_filepath.as_string(), event_message
        )

        for event in event_message.events:
            # Normalize path to Path object for consistency in file_hashes dict
            path_key = Path(event.path_in_syftbox)

            if event.is_deleted:
                # Handle deletion
                self.file_connection.delete_file(str(event.path_in_syftbox))
                if path_key in self.file_hashes:
                    del self.file_hashes[path_key]
            else:
                # Handle create/update
                self.file_connection.write_file(
                    str(event.path_in_syftbox), event.content
                )
                self.file_hashes[path_key] = event.new_hash

    def get_cached_events(self) -> List[FileChangeEvent]:
        messages = self.events_connection.get_all()
        return [event for message in messages for event in message.events]

    def sync_down_if_needed(self, peer_email: str):
        if self.last_sync is None:
            self.sync_down(peer_email)

        time_since_last_sync = datetime.now() - self.last_sync
        if time_since_last_sync > timedelta(seconds=SECONDS_BEFORE_SYNCING_DOWN):
            self.sync_down(peer_email)

    def current_hash_for_file(self, path: str) -> int | None:
        for peer in self.peers:
            self.sync_down_if_needed(peer)
        return self.file_hashes.get(path, None)

    def sync_down_datasets(self, peer_email: str):
        """
        Sync dataset collections from peer.
        Separate from message sync. Uses hash to skip unchanged collections.
        """
        # Get list of collections shared with us (now returns list of dicts)
        collections = self.connection_router.list_dataset_collections_as_ds()

        # Filter by peer
        peer_collections = [c for c in collections if c["owner_email"] == peer_email]

        for collection in peer_collections:
            owner_email = collection["owner_email"]
            tag = collection["tag"]
            content_hash = collection["content_hash"]

            # Check if hash changed - skip download if unchanged
            cache_key = f"{owner_email}/{tag}"
            cached_hash = self.dataset_collection_hashes.get(cache_key)
            if cached_hash == content_hash:
                continue

            # Download collection files
            files = self.connection_router.download_dataset_collection(
                tag, content_hash, owner_email
            )

            # Write files to local cache
            for file_name, content in files.items():
                file_path = (
                    f"{owner_email}/public/{COLLECTIONS_FOLDER_NAME}/{tag}/{file_name}"
                )
                self.file_connection.write_file(file_path, content)

            # Update hash cache
            self.dataset_collection_hashes[cache_key] = content_hash

    def sync_down_datasets_parallel(
        self,
        peer_email: str,
        executor: ThreadPoolExecutor,
        download_fn: Callable[[str], bytes],
    ):
        """
        Sync dataset collections from peer with parallel file downloads.
        Downloads all files from all collections in a single parallel batch.
        """
        collections = self.connection_router.list_dataset_collections_as_ds()
        peer_collections = [c for c in collections if c["owner_email"] == peer_email]

        # Gather all files to download across all collections
        all_downloads = []  # List of (collection_info, file_metadata)
        collections_to_update = []

        for collection in peer_collections:
            owner_email = collection["owner_email"]
            tag = collection["tag"]
            content_hash = collection["content_hash"]

            # Check if hash changed - skip download if unchanged
            cache_key = f"{owner_email}/{tag}"
            cached_hash = self.dataset_collection_hashes.get(cache_key)
            if cached_hash == content_hash:
                continue

            # Get file metadata (no download yet)
            file_metadatas = (
                self.connection_router.get_dataset_collection_file_metadatas(
                    tag, content_hash, owner_email
                )
            )

            if not file_metadatas:
                continue

            collections_to_update.append(collection)
            for metadata in file_metadatas:
                all_downloads.append((collection, metadata))

        if not all_downloads:
            return

        # Download all files from all collections in parallel
        file_ids = [metadata["file_id"] for _, metadata in all_downloads]
        downloaded_contents = list(executor.map(download_fn, file_ids))

        # Write files to local cache
        for (collection, metadata), content in zip(all_downloads, downloaded_contents):
            owner_email = collection["owner_email"]
            tag = collection["tag"]
            file_name = metadata["file_name"]
            file_path = (
                f"{owner_email}/public/{COLLECTIONS_FOLDER_NAME}/{tag}/{file_name}"
            )
            self.file_connection.write_file(file_path, content)

        # Update hash cache for all collections
        for collection in collections_to_update:
            cache_key = f"{collection['owner_email']}/{collection['tag']}"
            self.dataset_collection_hashes[cache_key] = collection["content_hash"]
