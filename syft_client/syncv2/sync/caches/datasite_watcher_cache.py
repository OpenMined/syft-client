from typing import Dict, List
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from syft_client.syncv2.events.file_change_event import FileChangeEvent
from syft_client.syncv2.connections.connection_router import ConnectionRouter

from syft_client.syncv2.sync.caches.cache_file_writer_connection import (
    CacheFileConnection,
    InMemoryCacheFileConnection,
)

SECONDS_BEFORE_SYNCING_DOWN = 0


class DataSiteWatcherCache(BaseModel):
    events_connection: CacheFileConnection[FileChangeEvent] = Field(
        default_factory=lambda: InMemoryCacheFileConnection[FileChangeEvent]()
    )
    file_hashes: Dict[str, int] = {}
    current_check_point: str = None
    connection_router: ConnectionRouter
    file_connection: CacheFileConnection[str] = Field(
        default_factory=lambda: InMemoryCacheFileConnection[str]()
    )
    last_sync: datetime | None = None
    seconds_before_syncing_down: int = SECONDS_BEFORE_SYNCING_DOWN

    @property
    def last_event_timestamp(self) -> float | None:
        if len(self.events_connection) == 0:
            return None
        return self.events_connection.get_latest().timestamp

    def sync_down(self):
        new_events = self.connection_router.get_events_for_datasite_watcher(
            since_timestamp=self.last_event_timestamp,
        )
        for event in sorted(new_events, key=lambda x: x.timestamp):
            self.apply_event(event)

        self.last_sync = datetime.now()

    def apply_event(self, event: FileChangeEvent):
        self.file_connection.write_file(event.path, event.content)
        self.file_hashes[event.path] = event.new_hash

        self.events_connection.write_file(event.eventfile_filepath(), event)

    def get_all_events(self) -> List[FileChangeEvent]:
        return self.events_connection.get_all()

    def sync_down_if_needed(self):
        if self.last_sync is None:
            self.sync_down()

        time_since_last_sync = datetime.now() - self.last_sync
        if time_since_last_sync > timedelta(seconds=SECONDS_BEFORE_SYNCING_DOWN):
            self.sync_down()

    def current_hash_for_file(self, path: str) -> int | None:
        self.sync_down_if_needed()
        return self.file_hashes.get(path, None)
