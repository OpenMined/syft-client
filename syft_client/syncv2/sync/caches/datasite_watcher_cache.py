from typing import List
from pydantic import BaseModel
from datetime import datetime, timedelta
from syft_client.syncv2.events.file_change_event import FileChangeEvent
from syft_client.syncv2.connections.connection_router import ConnectionRouter


SECONDS_BEFORE_SYNCING_DOWN = 3600


class DataSiteWatcherCache(BaseModel):
    events: List[FileChangeEvent] = []
    current_check_point: str = None
    connection_router: ConnectionRouter
    last_sync: datetime | None = None

    def sync_down(self):
        events = self.connection_router.get_events_for_datasite_watcher()
        # TODO, check if we are still in the current checkpoint
        for event in events:
            if event in self.events:
                continue
            self.events.append(event)
        self.events.sort(key=lambda x: x.timestamp)
        self.last_sync = datetime.now()

    def sync_down_if_needed(self):
        if self.last_sync is None:
            self.sync_down()

        time_since_last_sync = datetime.now() - self.last_sync
        if time_since_last_sync > timedelta(seconds=SECONDS_BEFORE_SYNCING_DOWN):
            self.sync_down()

    def head_for_new_event(self) -> FileChangeEvent:
        self.sync_down_if_needed()
        if len(self.events) == 0:
            raise ValueError("No events in cache, did you initialize the cache?")
        return self.events[-1]
