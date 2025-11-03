from syft_client.sync.connections.connection_router import ConnectionRouter
from syft_client.sync.callback_mixin import BaseModelCallbackMixin
from syft_client.sync.sync.caches.datasite_watcher_cache import DataSiteWatcherCache
from syft_client.sync.sync.caches.datasite_watcher_cache import (
    DataSiteWatcherCacheConfig,
)
from syft_client.sync.connections.base_connection import ConnectionConfig
from typing import List
from pydantic import BaseModel, Field


class DatasiteOutboxPullerConfig(BaseModel):
    connection_configs: List[ConnectionConfig] = []
    datasite_watcher_cache_config: DataSiteWatcherCacheConfig = Field(
        default_factory=DataSiteWatcherCacheConfig
    )


class DatasiteOutboxPuller(BaseModelCallbackMixin):
    connection_router: ConnectionRouter
    datasite_watcher_cache: DataSiteWatcherCache

    @classmethod
    def from_config(cls, config: DatasiteOutboxPullerConfig):
        return cls(
            connection_router=ConnectionRouter.from_configs(config.connection_configs),
            datasite_watcher_cache=DataSiteWatcherCache.from_config(
                config.datasite_watcher_cache_config
            ),
        )

    def sync_down(self, peer_emails: list[str]):
        for peer_email in peer_emails:
            self.datasite_watcher_cache.sync_down(peer_email)
