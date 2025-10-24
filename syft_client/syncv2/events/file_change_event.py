import time
from typing import Any, List
from uuid import UUID, uuid4
from pydantic import BaseModel
from syft_client.syncv2.messages.proposed_filechange import ProposedFileChange
from syft_client.syncv2.syftbox_utils import create_event_timestamp


class FileChangeEvent(BaseModel):
    id: UUID
    path: str
    content: str
    old_hash: int | None = None
    new_hash: int
    submitted_timestamp: float
    timestamp: float

    def to_json(self) -> str:
        return self.model_dump_json()

    def eventfile_filepath(self) -> str:
        f"{self.timestamp}__syftfile__{self.path}.{self.id}.json"

    @classmethod
    def from_proposed_filechange(
        cls,
        proposed_filechange: ProposedFileChange,
    ) -> "FileChangeEvent":
        return cls(
            path=proposed_filechange.path,
            content=proposed_filechange.content,
            id=proposed_filechange.id,
            old_hash=proposed_filechange.old_hash,
            new_hash=proposed_filechange.new_hash,
            submitted_timestamp=proposed_filechange.submitted_timestamp,
            timestamp=create_event_timestamp(),
        )

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, FileChangeEvent):
            return False
        return self.id == other.id
