from typing import Dict, List
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


class DataSiteWatcherCacheConfig(BaseModel):
    use_in_memory_cache: bool = True
    syftbox_folder: Path | None = None
    events_base_path: Path | None = None
    connection_configs: List[ConnectionConfig] = []

    @model_validator(mode="before")
    def pre_init(cls, data):
        if data.get("events_base_path") is None and data.get("base_path") is not None:
            base_path = data["base_path"]
            base_parent = base_path.parent
            data["events_base_path"] = base_parent / "events"
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

    @classmethod
    def from_config(cls, config: DataSiteWatcherCacheConfig):
        if config.use_in_memory_cache:
            res = cls(
                events_connection=InMemoryCacheFileConnection[FileChangeEvent](),
                file_connection=InMemoryCacheFileConnection[str](),
                connection_router=ConnectionRouter.from_configs(
                    connection_configs=config.connection_configs
                ),
            )
            return res
        else:
            if config.syftbox_folder is None:
                raise ValueError("base_path is required for non-in-memory cache")

            syftbox_folder_name = Path(config.syftbox_folder).name
            syftbox_parent = Path(config.syftbox_folder).parent
            events_folder = syftbox_parent / f"{syftbox_folder_name}-event-messages"

            return cls(
                events_connection=FSFileConnection(
                    base_dir=events_folder, dtype=FileChangeEventsMessage
                ),
                file_connection=FSFileConnection(base_dir=config.syftbox_folder),
                connection_router=ConnectionRouter.from_configs(
                    connection_configs=config.connection_configs
                ),
            )

    def clear_cache(self):
        self.events_connection.clear_cache()
        self.file_connection.clear_cache()
        self.file_hashes = {}
        self.last_sync = None
        self.peers = []
        self.current_check_point = None

    @property
    def last_event_timestamp(self) -> float | None:
        if len(self.events_connection) == 0:
            return None
        return self.events_connection.get_latest().timestamp

    def sync_down(self, peer_email: str):
        new_event_messages = (
            self.connection_router.get_events_messages_for_datasite_watcher(
                peer_email=peer_email,
                since_timestamp=self.last_event_timestamp,
            )
        )
        for event_message in sorted(new_event_messages, key=lambda x: x.timestamp):
            self.apply_event_message(event_message)

        self.last_sync = datetime.now()

    def apply_event_message(self, event_message: FileChangeEventsMessage):
        self.events_connection.write_file(
            event_message.message_filepath.as_string(), event_message
        )

        for event in event_message.events:
            self.file_connection.write_file(event.path_in_syftbox, event.content)
            self.file_hashes[event.path_in_syftbox] = event.new_hash

    def get_cached_events(self) -> List[FileChangeEvent]:
        messages = self.events_connection.get_all()
        return [event for message in messages for event in message.events]

    def sync_down_if_needed(self, peer_email: str):
        if self.last_sync is None:
            self.sync_down(peer_email)

        time_since_last_sync = datetime.now() - self.last_sync
        if time_since_last_sync > timedelta(seconds=SECONDS_BEFORE_SYNCING_DOWN):
            self.sync_down()

    def current_hash_for_file(self, path: str) -> int | None:
        for peer in self.peers:
            self.sync_down_if_needed(peer)
        return self.file_hashes.get(path, None)
