from pydantic import BaseModel
from typing import List
from syft_client.syncv2.connections import SyftboxPlatformConnection


class ConnectionRouter(BaseModel):
    connections: List[SyftboxPlatformConnection]

    def propose_file_change(self, path: str, content: str):
        # TODO: Implement connection routing logic
        self.connections[0].propose_file_change(path, content)
