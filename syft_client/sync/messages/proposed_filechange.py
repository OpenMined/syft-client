from typing import List
from uuid import UUID, uuid4
from pathlib import Path
import uuid
import time
from pydantic import Field, model_validator
from pydantic.main import BaseModel
from syft_client.sync.utils.syftbox_utils import compress_data, uncompress_data
from syft_client.sync.utils.syftbox_utils import create_event_timestamp
from syft_client.sync.utils.syftbox_utils import get_event_hash_from_content


MESSAGE_FILENAME_PREFIX = "msgv2"
MESSAGE_FILENAME_EXTENSION = ".tar.gz"


class ProposedFileChange(BaseModel):
    id: UUID = Field(default_factory=lambda: uuid4())
    old_hash: str | None = None
    new_hash: str
    # Use UNIX timestamp (seconds since epoch)
    submitted_timestamp: float = Field(default_factory=lambda: create_event_timestamp())
    path_in_datasite: Path
    content: str
    datasite_email: str

    @model_validator(mode="before")
    def pre_init(cls, data):
        if "new_hash" not in data:
            content = data.get("content")
            data["new_hash"] = get_event_hash_from_content(content)

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
    sender_email: str
    message_filename: MessageFileName = Field(default_factory=lambda: MessageFileName())
    proposed_file_changes: List[ProposedFileChange]

    @classmethod
    def from_compressed_data(cls, data: bytes) -> "ProposedFileChangesMessage":
        uncompressed_data = uncompress_data(data)
        return cls.model_validate_json(uncompressed_data)

    def as_compressed_data(self) -> bytes:
        data = self.model_dump_json(indent=2).encode("utf-8")
        return compress_data(data)
