from typing import List
from pydantic import BaseModel
from syft_client.sync.platforms.base_platform import BasePlatform


class Peer(BaseModel):
    email: str
    platforms: List[BasePlatform] = []
