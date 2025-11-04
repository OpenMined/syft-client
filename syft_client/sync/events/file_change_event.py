from typing import Any
from uuid import UUID
from pydantic import BaseModel, model_validator
from syft_client.sync.messages.proposed_filechange import ProposedFileChange
from syft_client.sync.utils.syftbox_utils import create_event_timestamp
from syft_client.sync.utils.syftbox_utils import compress_data
from syft_client.sync.utils.syftbox_utils import uncompress_data


FILE_CHANGE_FILENAME_PREFIX = "syfteventv2"
DEFAULT_EVENT_FILENAME_EXTENSION = ".tar.gz"


class FileChangeEventFileName(BaseModel):
    id: UUID
    file_path: str
    timestamp: float
    extension: str = DEFAULT_EVENT_FILENAME_EXTENSION

    def as_string(self) -> str:
        return f"{FILE_CHANGE_FILENAME_PREFIX}_{self.timestamp}_{self.id}_{self.file_path}{DEFAULT_EVENT_FILENAME_EXTENSION}"

    @classmethod
    def from_string(cls, filename: str) -> "FileChangeEventFileName":
        try:
            parts = filename.split("_", 3)
            if len(parts) != 4:
                raise ValueError(f"Invalid filename: {filename}")
            timestamp = float(parts[1])
            id = UUID(parts[2])

            file_path_with_ext = parts[3]
            file_path = file_path_with_ext
            if file_path.endswith(DEFAULT_EVENT_FILENAME_EXTENSION):
                file_path = file_path[: -len(DEFAULT_EVENT_FILENAME_EXTENSION)]
            return cls(id=id, file_path=file_path, timestamp=timestamp)
        except Exception:
            raise ValueError(f"Invalid filename: {filename}")


class FileChangeEvent(BaseModel):
    id: UUID
    path: str
    content: str
    old_hash: str | None = None
    new_hash: str
    submitted_timestamp: float
    timestamp: float
    event_filepath: FileChangeEventFileName

    @model_validator(mode="before")
    def pre_init(cls, data):
        if "event_filepath" not in data:
            data["event_filepath"] = FileChangeEventFileName(
                id=data["id"],
                file_path=data["path"],
                timestamp=data["timestamp"],
            )
        return data

    def eventfile_filepath(self) -> str:
        return self.event_filepath.as_string()

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
        # this is for comparing locally
        return hash(self.id)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, FileChangeEvent):
            return False
        return self.id == other.id

    def as_compressed_data(self) -> bytes:
        return compress_data(self.model_dump_json().encode("utf-8"))

    @classmethod
    def from_compressed_data(cls, data: bytes) -> "FileChangeEvent":
        uncompressed_data = uncompress_data(data)
        return cls.model_validate_json(uncompressed_data)
