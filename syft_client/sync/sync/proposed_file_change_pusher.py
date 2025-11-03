from pathlib import Path
from pydantic import BaseModel, Field
from typing import List
from syft_client.sync.connections.base_connection import ConnectionConfig
from syft_client.sync.connections.connection_router import ConnectionRouter
from syft_client.sync.callback_mixin import BaseModelCallbackMixin
from syft_client.sync.messages.proposed_filechange import (
    ProposedFileChange,
    ProposedFileChangesMessage,
)
from syft_client.sync.sync.caches.datasite_watcher_cache import (
    DataSiteWatcherCache,
    DataSiteWatcherCacheConfig,
)


class ProposedFileChangePusherConfig(BaseModel):
    base_path: Path | None = None
    email: str | None = None
    connection_configs: List[ConnectionConfig] = []
    datasite_watcher_cache_config: DataSiteWatcherCacheConfig = Field(
        default_factory=DataSiteWatcherCacheConfig
    )


class ProposedFileChangePusher(BaseModelCallbackMixin):
    base_path: Path
    email: str
    connection_router: ConnectionRouter
    datasite_watcher_cache: DataSiteWatcherCache

    @classmethod
    def from_config(cls, config: ProposedFileChangePusherConfig):
        return cls(
            base_path=config.base_path,
            email=config.email,
            connection_router=ConnectionRouter.from_configs(config.connection_configs),
            datasite_watcher_cache=DataSiteWatcherCache.from_config(
                config.datasite_watcher_cache_config
            ),
        )

    def get_proposed_file_change_object(
        self, path: str, content: str
    ) -> ProposedFileChange:
        old_hash = self.datasite_watcher_cache.current_hash_for_file(path)
        return ProposedFileChange(path=path, content=content, old_hash=old_hash)

    def on_file_change(self, path: str, content: str | None = None):
        # for in memory connection we pass content directly
        if content is None:
            with open(self.base_path / path, "r") as f:
                content = f.read()

        splitted = path.split("/")
        # TODO: add some better parsing logic here
        recipient = splitted[0]
        path_in_datasite = path

        file_change = self.get_proposed_file_change_object(path_in_datasite, content)
        message = ProposedFileChangesMessage(
            sender_email=self.email, proposed_file_changes=[file_change]
        )
        self.connection_router.send_proposed_file_changes_message(recipient, message)
