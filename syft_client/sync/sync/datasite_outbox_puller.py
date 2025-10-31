from syft_client.sync.connections.connection_router import ConnectionRouter
from syft_client.sync.callback_mixin import BaseModelCallbackMixin
from syft_client.sync.sync.caches.datasite_watcher_cache import DataSiteWatcherCache


class DatasiteOutboxPuller(BaseModelCallbackMixin):
    connection_router: ConnectionRouter
    datasite_watcher_cache: DataSiteWatcherCache

    def sync_down(self, peer_emails: list[str]):
        for peer_email in peer_emails:
            self.datasite_watcher_cache.sync_down(peer_email)
