from enum import Enum
from typing import List
from pydantic import BaseModel
from syft_client.sync.platforms.base_platform import BasePlatform


class PeerState(str, Enum):
    ACCEPTED = "accepted"
    PENDING = "pending"
    REJECTED = "rejected"


class Peer(BaseModel):
    email: str
    platforms: List[BasePlatform] = []
    state: PeerState = PeerState.ACCEPTED  # Default for backward compatibility

    @property
    def approved(self) -> bool:
        """Returns True if peer is accepted"""
        return self.state == PeerState.ACCEPTED
