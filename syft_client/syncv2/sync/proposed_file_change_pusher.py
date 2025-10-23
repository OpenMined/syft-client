from pathlib import Path
from typing import Self
from uuid import UUID

from pydantic import Field, model_validator
from syft_client.syncv2.connections.connection_router import ConnectionRouter
from syft_client.syncv2.callback_mixin import BaseModelCallbackMixin
from syft_client.syncv2.messages.proposed_filechange import (
    ProposedFileChange,
    ProposedFileChangesMessage,
)
from syft_client.syncv2.sync.caches.datasite_watcher_cache import DataSiteWatcherCache


class ProposedFileChangePusher(BaseModelCallbackMixin):
    base_path: Path
    connection_router: ConnectionRouter
    datasite_watcher_cache: DataSiteWatcherCache = Field(default=None, init=False)

    @model_validator(mode="after")
    def _initialize_cache(self) -> Self:
        if self.datasite_watcher_cache is None:
            self.datasite_watcher_cache = DataSiteWatcherCache(
                connection_router=self.connection_router
            )
        return self

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

        file_change = self.get_proposed_file_change_object(path, content)
        message = ProposedFileChangesMessage(proposed_file_changes=[file_change])
        self.connection_router.send_proposed_filechange_message(message)
