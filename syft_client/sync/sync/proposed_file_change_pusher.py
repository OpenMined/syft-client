from pathlib import Path
from pydantic import BaseModel, Field
from typing import List
from queue import Queue
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
    syftbox_folder: Path | None = None
    email: str | None = None
    connection_configs: List[ConnectionConfig] = []
    datasite_watcher_cache_config: DataSiteWatcherCacheConfig = Field(
        default_factory=DataSiteWatcherCacheConfig
    )


class ProposedFileChangePusher(BaseModelCallbackMixin):
    class Config:
        arbitrary_types_allowed = True

    syftbox_folder: Path
    email: str
    connection_router: ConnectionRouter
    datasite_watcher_cache: DataSiteWatcherCache
    queue: Queue = Field(default_factory=Queue)

    @classmethod
    def from_config(cls, config: ProposedFileChangePusherConfig):
        return cls(
            syftbox_folder=config.syftbox_folder,
            email=config.email,
            connection_router=ConnectionRouter.from_configs(config.connection_configs),
            datasite_watcher_cache=DataSiteWatcherCache.from_config(
                config.datasite_watcher_cache_config
            ),
        )

    def get_proposed_file_change_object(
        self, relative_path: Path, content: str, datasite_email: str | None = None
    ) -> ProposedFileChange:
        if datasite_email is None:
            datasite_email = self.email
        old_hash = self.datasite_watcher_cache.current_hash_for_file(relative_path)
        return ProposedFileChange(
            datasite_email=datasite_email,
            path_in_datasite=relative_path,
            content=content,
            old_hash=old_hash,
        )

    def process_file_changes_queue(self):
        file_changes = []
        while not self.queue.empty():
            relative_path, content = self.queue.get()

            # for in memory connection we pass content directly
            if content is None:
                with open(self.syftbox_folder / relative_path, "r") as f:
                    content = f.read()

            # splitted = relative_path.split("/")

            datasite_email = relative_path.parts[0]
            path_in_datasite = (
                Path(*relative_path.parts[1:])
                if len(relative_path.parts) > 1
                else Path()
            )

            # TODO: add some better parsing logic here
            recipient = datasite_email
            path_in_datasite = path_in_datasite

            file_change = self.get_proposed_file_change_object(
                path_in_datasite, content, datasite_email=recipient
            )
            file_changes.append(file_change)

        message = ProposedFileChangesMessage(
            sender_email=self.email, proposed_file_changes=file_changes
        )
        self.connection_router.send_proposed_file_changes_message(recipient, message)

    def on_file_change(
        self, relative_path: Path | str, content: str | None = None, process_now=True
    ):
        relative_path = Path(relative_path)
        self.queue.put((relative_path, content))
        if process_now:
            self.process_file_changes_queue()
