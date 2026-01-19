from enum import Enum
from typing import List, Optional
from pydantic import BaseModel
from syft_client.sync.platforms.base_platform import BasePlatform
from syft_client.sync.version.version_info import VersionInfo


class PeerState(str, Enum):
    ACCEPTED = "accepted"
    PENDING = "pending"
    REJECTED = "rejected"
    OUTSTANDING = "outstanding"  # DS's view of their outgoing requests


class Peer(BaseModel):
    email: str
    platforms: List[BasePlatform] = []
    state: PeerState = PeerState.ACCEPTED  # Default for backward compatibility
    version: Optional[VersionInfo] = None

    @property
    def is_approved(self) -> bool:
        """Returns True if peer is accepted"""
        return self.state == PeerState.ACCEPTED

    @property
    def is_pending(self) -> bool:
        """Returns True if peer request is pending"""
        return self.state == PeerState.PENDING

    @property
    def is_outstanding(self) -> bool:
        """Returns True if this is an outstanding outgoing request (DS side)"""
        return self.state == PeerState.OUTSTANDING
