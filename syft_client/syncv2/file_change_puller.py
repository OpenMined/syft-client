from pydantic import BaseModel
from syft_client.syncv2.proposed_filechange_handler import (
    ProposedFileChangeHandler,
)
from syft_client.syncv2.proposed_filechange_handler import ProposedFileChangeEvent


class ProposedFileChangePuller(BaseModel):
    base_path: str
    handler: ProposedFileChangeHandler

    def on_proposed_filechange_receive(self, path: str, content: str):
        self.handler.handle_proposed_filechange_event(
            ProposedFileChangeEvent(path=path, content=content)
        )
