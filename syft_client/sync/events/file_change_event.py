from typing import Any
from pathlib import Path
from uuid import UUID, uuid4
import base64
from pydantic import (
    BaseModel,
    Field,
    model_validator,
    field_serializer,
    field_validator,
)
from syft_client.sync.messages.proposed_filechange import ProposedFileChange
from syft_client.sync.utils.syftbox_utils import create_event_timestamp
from syft_client.sync.utils.syftbox_utils import compress_data
from syft_client.sync.utils.syftbox_utils import uncompress_data
from typing import List


FILE_CHANGE_FILENAME_PREFIX = "syfteventsmessagev3"
DEFAULT_EVENT_FILENAME_EXTENSION = ".tar.gz"


class FileChangeEventsMessageFileName(BaseModel):
    id: UUID = Field(default_factory=lambda: uuid4())
    timestamp: float = Field(default_factory=lambda: create_event_timestamp())
    extension: str = DEFAULT_EVENT_FILENAME_EXTENSION

    def as_string(self) -> str:
        return f"{FILE_CHANGE_FILENAME_PREFIX}_{self.timestamp}_{self.id}{DEFAULT_EVENT_FILENAME_EXTENSION}"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, FileChangeEventsMessageFileName):
            return False
        return (
            self.id == other.id
            and self.timestamp == other.timestamp
            and self.extension == other.extension
        )

    @classmethod
    def from_string(cls, filename: str) -> "FileChangeEventsMessageFileName":
        try:
            parts = filename.split("_", 2)
            if len(parts) != 3:
                raise ValueError(f"Invalid filename: {filename}")
            timestamp = float(parts[1])

            id_with_ext = parts[2]
            _id = id_with_ext
            if _id.endswith(DEFAULT_EVENT_FILENAME_EXTENSION):
                _id = UUID(_id[: -len(DEFAULT_EVENT_FILENAME_EXTENSION)])
            return cls(id=_id, timestamp=timestamp)
        except Exception as e:
            raise ValueError(f"Invalid filename: {filename}") from e


class FileChangeEvent(BaseModel):
    id: UUID
    path_in_datasite: Path
    datasite_email: str
    content: str | bytes | None = (
        None  # None for deletions, can be str or bytes for binary files
    )
    old_hash: str | None = None
    new_hash: str | None = None  # None for deletions
    is_deleted: bool = False
    submitted_timestamp: float
    timestamp: float

    @field_serializer("content", when_used="json")
    def serialize_content(self, value: str | bytes | None) -> str | None:
        """Serialize bytes as base64-encoded string for JSON."""
        if value is None:
            return None
        if isinstance(value, bytes):
            return base64.b64encode(value).decode("utf-8")
        return value

    @field_validator("content", mode="before")
    @classmethod
    def deserialize_content(cls, value: Any) -> str | bytes | None:
        """Deserialize base64-encoded string back to bytes if needed."""
        if value is None:
            return None
        if isinstance(value, str):
            # Try to decode as base64 if it looks like base64
            # We'll use a simple heuristic: if it's a valid base64 string and not plain text
            try:
                decoded = base64.b64decode(value, validate=True)
                # Only use decoded bytes if the original string was actually base64
                # (not just a regular string that happens to be valid base64)
                # A simple check: if decoded bytes are different from the string's bytes
                if decoded != value.encode("utf-8"):
                    return decoded
            except Exception:
                pass
            return value
        return value

    @property
    def path_in_syftbox(self) -> Path:
        return Path(self.datasite_email) / self.path_in_datasite

    @model_validator(mode="before")
    def pre_init(cls, data):
        # if "event_filepath" not in data:
        #     data["event_filepath"] = FileChangeEventsMessageFileName(
        #         id=data["id"],
        #         file_path_in_datasite=data["path_in_datasite"],
        #         timestamp=data["timestamp"],
        #     )
        return data

    def eventfile_filepath(self) -> str:
        # TODO: remove
        return f"_{self.id}"

    @classmethod
    def from_proposed_filechange(
        cls,
        proposed_filechange: ProposedFileChange,
    ) -> "FileChangeEvent":
        return cls(
            path_in_datasite=proposed_filechange.path_in_datasite,
            content=proposed_filechange.content,
            id=proposed_filechange.id,
            old_hash=proposed_filechange.old_hash,
            new_hash=proposed_filechange.new_hash,
            submitted_timestamp=proposed_filechange.submitted_timestamp,
            timestamp=create_event_timestamp(),
            datasite_email=proposed_filechange.datasite_email,
        )

    def __hash__(self) -> int:
        # this is for comparing locally
        return hash(self.id)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, FileChangeEvent):
            return False
        return self.id == other.id


class FileChangeEventsMessage(BaseModel):
    events: List[FileChangeEvent]
    message_filepath: FileChangeEventsMessageFileName = Field(
        default_factory=lambda: FileChangeEventsMessageFileName()
    )

    @property
    def timestamp(self) -> float:
        return self.message_filepath.timestamp

    def as_compressed_data(self) -> bytes:
        return compress_data(self.model_dump_json().encode("utf-8"))

    @classmethod
    def from_compressed_data(cls, data: bytes) -> "FileChangeEvent":
        uncompressed_data = uncompress_data(data)
        return cls.model_validate_json(uncompressed_data)
