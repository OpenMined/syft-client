from datetime import datetime
from typing import List
from uuid import UUID, uuid4
import uuid
from pydantic import Field, model_validator
from pydantic.main import BaseModel
from syft_client.syncv2.syftbox_utils import uncompress_data
from syft_client.syncv2.syftbox_utils import create_event_timestamp


class ProposedFileChange(BaseModel):
    id: UUID = Field(default_factory=lambda: uuid4())
    old_hash: int | None = None
    new_hash: int
    # Use UNIX timestamp (seconds since epoch)
    submitted_timestamp: float = Field(default_factory=lambda: create_event_timestamp())
    path: str
    content: str

    @model_validator(mode="before")
    def pre_init(cls, data):
        if "new_hash" not in data:
            data["new_hash"] = hash(data.get("content"))
        return data


def generate_message_filename() -> str:
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = str(uuid.uuid4()).replace("-", "")[:8]
    return f"msgv2_{now}_{uid}.tar.gz"


class ProposedFileChangesMessage(BaseModel):
    filename: str = Field(default_factory=generate_message_filename)
    proposed_file_changes: List[ProposedFileChange]

    @classmethod
    def from_compressed_data(cls, data: bytes) -> "ProposedFileChangesMessage":
        uncompressed_data = uncompress_data(data)
        return cls.model_validate_json(uncompressed_data)
