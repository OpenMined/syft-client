import time
from typing import Any, List
from uuid import UUID, uuid4
from pydantic import BaseModel
from syft_client.syncv2.messages.proposed_filechange import ProposedFileChange
from syft_client.syncv2.syftbox_utils import create_event_timestamp


class FileChangeEvent(BaseModel):
    # can be None for no-op events
    path: str | None = None
    # can be None for no-op events
    content: str | None = None
    id: UUID
    parent_ids: List[UUID]
    timestamp: float

    @classmethod
    def for_now(
        cls,
        path: str | None = None,
        content: str | None = None,
        parent_ids: List[UUID] = [],
    ) -> "FileChangeEvent":
        return cls(
            path=path,
            content=content,
            id=uuid4(),
            parent_ids=parent_ids,
            timestamp=create_event_timestamp(),
        )

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, FileChangeEvent):
            return False
        return self.id == other.id


class FileChangeEventNode(BaseModel):
    event: FileChangeEvent
    parents: List["FileChangeEventNode"]
    is_root: bool = False

    def __eq__(self, other: "FileChangeEventNode") -> bool:
        if not isinstance(other, FileChangeEventNode):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    @classmethod
    def noop_event(
        cls, is_root=False, parents: List["FileChangeEventNode"] = []
    ) -> "FileChangeEventNode":
        parent_ids = [parent.id for parent in parents]
        return cls(
            event=FileChangeEvent.for_now(
                path=None, content=None, parent_ids=parent_ids
            ),
            parents=parents,
            is_root=is_root,
        )

    @classmethod
    def from_proposed_filechange(
        cls, proposed_event: ProposedFileChange, parents: List["FileChangeEventNode"]
    ) -> "FileChangeEventNode":
        event = FileChangeEvent(
            path=proposed_event.path,
            content=proposed_event.content,
            id=proposed_event.id,
            parent_ids=[proposed_event.parent_id],
            timestamp=proposed_event.timestamp,
        )
        return cls(event=event, parents=parents, is_root=False)

    @property
    def id(self) -> UUID:
        return self.event.id

    @property
    def parent_ids(self) -> List[UUID]:
        return self.event.parent_ids

    @property
    def path(self) -> str:
        return self.event.path

    @property
    def content(self) -> str:
        return self.event.content

    def __eq__(self, other: "FileChangeEventNode") -> bool:
        if not isinstance(other, FileChangeEventNode):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
