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


class PusherManager(BaseModel):
    def __init__(self, in_process):
        self.logs_subfolder = logs_subfolder
        self.folder_to_watch = folder_to_watch
        if in_process:
            pusher = ProposedFileChangePusher(
                base_path=base_path,
                connection_router=connection_router,
            )

            self.pid = launch(pusher, logs_subfolder, folder_to_watch)
        elif in_memory:
            self.pusher = ProposedFileChangePusher(
                base_path=base_path,
                connection_router=connection_router,
            )


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

    def get_event_parent_id(self) -> UUID:
        parent_event = self.datasite_watcher_cache.head_for_new_event()
        return parent_event.id

    def on_file_change(self, path: str, content: str | None = None):
        # for in memory connection we pass content directly
        if content is None:
            with open(self.base_path / path, "r") as f:
                content = f.read()

        file_change = ProposedFileChange(
            path=path, content=content, parent_id=self.get_event_parent_id()
        )
        message = ProposedFileChangesMessage(proposed_file_changes=[file_change])
        self.connection_router.send_proposed_filechange_message(message)
