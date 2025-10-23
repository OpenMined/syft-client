from syft_client.syncv2.messages.proposed_filechange import (
    ProposedFileChangesMessage,
)
from syft_client.syncv2.connections.connection_router import ConnectionRouter
from syft_client.syncv2.callback_mixin import BaseModelCallbackMixin


class ProposedFileChangePuller(BaseModelCallbackMixin):
    base_path: str
    connection_router: ConnectionRouter

    def on_proposed_filechange_receive(
        self, proposed_file_change_message: ProposedFileChangesMessage
    ):
        for proposed_file_change in proposed_file_change_message.proposed_file_changes:
            for callback in self.callbacks.get("on_proposed_filechange_receive", []):
                callback(proposed_file_change)
