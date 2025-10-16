from pydantic import BaseModel
from syft_client.syncv2.connection_router import ConnectionRouter


class FileChangePusher(BaseModel):
    base_path: str
    connection_router: ConnectionRouter

    def on_file_change(self, path: str, content: str):
        self.connection_router.propose_file_change(path, content)
