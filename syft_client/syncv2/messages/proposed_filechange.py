from datetime import datetime
from typing import List
from uuid import UUID, uuid4
import uuid
import time
from pydantic import Field, model_validator
from pydantic.main import BaseModel
from syft_client.syncv2.syftbox_utils import compress_data, uncompress_data
from syft_client.syncv2.syftbox_utils import create_event_timestamp


MESSAGE_FILENAME_PREFIX = "msgv2"
MESSAGE_FILENAME_EXTENSION = ".tar.gz"


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


class FileNameParseError(Exception):
    pass


class MessageFileName(BaseModel):
    submitted_timestamp: float = Field(default_factory=lambda: time.time())
    uid: str = Field(default_factory=lambda: str(uuid.uuid4()))

    def as_string(self) -> str:
        return f"{MESSAGE_FILENAME_PREFIX}_{self.submitted_timestamp}_{self.uid}{MESSAGE_FILENAME_EXTENSION}"

    @classmethod
    def from_string(cls, filename: str) -> "MessageFileName":
        try:
            parts = filename.split("_")
            if len(parts) != 3:
                raise ValueError(f"Invalid filename: {filename}")
            submitted_timestamp = float(parts[1])
            uid = parts[2].replace(MESSAGE_FILENAME_EXTENSION, "")
        except Exception:
            raise FileNameParseError(f"Invalid filename: {filename}")
        return cls(submitted_timestamp=submitted_timestamp, uid=uid)


class ProposedFileChangesMessage(BaseModel):
    id: UUID = Field(default_factory=lambda: uuid4())
    message_filename: MessageFileName = Field(default_factory=lambda: MessageFileName())
    proposed_file_changes: List[ProposedFileChange]

    @classmethod
    def from_compressed_data(cls, data: bytes) -> "ProposedFileChangesMessage":
        uncompressed_data = uncompress_data(data)
        return cls.model_validate_json(uncompressed_data)

    def as_compressed_data(self) -> bytes:
        data = self.model_dump_json(indent=2).encode("utf-8")
        return compress_data(data)
