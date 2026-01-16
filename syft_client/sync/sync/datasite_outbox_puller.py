from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel, Field, PrivateAttr

from syft_client.sync.connections.connection_router import ConnectionRouter
from syft_client.sync.callback_mixin import BaseModelCallbackMixin
from syft_client.sync.sync.caches.datasite_watcher_cache import DataSiteWatcherCache
from syft_client.sync.sync.caches.datasite_watcher_cache import (
    DataSiteWatcherCacheConfig,
)
from syft_client.sync.connections.base_connection import ConnectionConfig
from syft_client.sync.events.file_change_event import FileChangeEventsMessage
from typing import List


class DatasiteOutboxPullerConfig(BaseModel):
    connection_configs: List[ConnectionConfig] = []
    datasite_watcher_cache_config: DataSiteWatcherCacheConfig = Field(
        default_factory=DataSiteWatcherCacheConfig
    )


class DatasiteOutboxPuller(BaseModelCallbackMixin):
    connection_router: ConnectionRouter
    datasite_watcher_cache: DataSiteWatcherCache
    _executor: ThreadPoolExecutor = PrivateAttr(
        default_factory=lambda: ThreadPoolExecutor(max_workers=10)
    )

    @classmethod
    def from_config(cls, config: DatasiteOutboxPullerConfig):
        return cls(
            connection_router=ConnectionRouter.from_configs(config.connection_configs),
            datasite_watcher_cache=DataSiteWatcherCache.from_config(
                config.datasite_watcher_cache_config
            ),
        )

    def download_events_message_with_new_connection(
        self, file_id: str
    ) -> FileChangeEventsMessage:
        """Download from outbox using a new connection (thread-safe)."""
        connection = self.connection_router.connection_for_parallel_download()
        return connection.download_events_message_by_id_from_outbox(file_id)

    def sync_down(self, peer_emails: list[str]):
        for peer_email in peer_emails:
            # Sync messages with parallel download
            self.datasite_watcher_cache.sync_down_parallel(
                peer_email,
                self._executor,
                self.download_events_message_with_new_connection,
            )
            # Sync datasets
            self.datasite_watcher_cache.sync_down_datasets(peer_email)
