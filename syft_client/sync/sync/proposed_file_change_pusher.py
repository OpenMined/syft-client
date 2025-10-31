from pathlib import Path

from syft_client.sync.connections.connection_router import ConnectionRouter
from syft_client.sync.callback_mixin import BaseModelCallbackMixin
from syft_client.sync.messages.proposed_filechange import (
    ProposedFileChange,
    ProposedFileChangesMessage,
)
from syft_client.sync.sync.caches.datasite_watcher_cache import DataSiteWatcherCache


class ProposedFileChangePusher(BaseModelCallbackMixin):
    base_path: Path
    email: str
    connection_router: ConnectionRouter
    datasite_watcher_cache: DataSiteWatcherCache

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
        path_in_datasite = splitted[1]

        file_change = self.get_proposed_file_change_object(path_in_datasite, content)
        message = ProposedFileChangesMessage(
            sender_email=self.email, proposed_file_changes=[file_change]
        )
        self.connection_router.send_proposed_file_changes_message(recipient, message)
