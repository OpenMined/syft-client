"""
Checkpoint data models for syft-client.

A checkpoint is a snapshot of the current state (all files + their hashes)
saved as a single compressed file on Google Drive.
"""

from typing import List, Dict
from pydantic import BaseModel, Field
from pathlib import Path
from syft_client.sync.utils.syftbox_utils import (
    create_event_timestamp,
    compress_data,
    uncompress_data,
)


CHECKPOINT_FILENAME_PREFIX = "checkpoint"
CHECKPOINT_VERSION = 1


class CheckpointFile(BaseModel):
    """Represents a single file in the checkpoint."""

    path: str  # Relative path in datasite (e.g., "public/syft_datasets/data.csv")
    hash: str  # Hash of the content (SHA256 hex string)
    content: str  # File content


class Checkpoint(BaseModel):
    """
    A checkpoint is a complete snapshot of the current state.

    Contains all files and their hashes at a specific point in time.
    Used to speed up initial sync by avoiding downloading all historical events.
    """

    version: int = CHECKPOINT_VERSION
    timestamp: float = Field(default_factory=create_event_timestamp)
    email: str
    last_event_timestamp: float | None = None  # Timestamp of last event included
    files: List[CheckpointFile] = []

    @property
    def filename(self) -> str:
        """Generate filename for this checkpoint."""
        return f"{CHECKPOINT_FILENAME_PREFIX}_{self.timestamp}.tar.gz"

    @classmethod
    def filename_to_timestamp(cls, filename: str) -> float | None:
        """Extract timestamp from checkpoint filename."""
        try:
            # Format: checkpoint_<timestamp>.tar.gz
            if not filename.startswith(CHECKPOINT_FILENAME_PREFIX):
                return None
            parts = filename.replace(".tar.gz", "").split("_")
            if len(parts) >= 2:
                return float(parts[1])
            return None
        except (ValueError, IndexError):
            return None

    @classmethod
    def from_file_hashes_and_contents(
        cls,
        email: str,
        file_hashes: Dict[str, str],
        file_contents: Dict[str, str],
        last_event_timestamp: float | None = None,
    ) -> "Checkpoint":
        """
        Create a checkpoint from file_hashes dict and file contents.

        Args:
            email: Data owner email
            file_hashes: Dict mapping path -> hash
            file_contents: Dict mapping path -> content
            last_event_timestamp: Timestamp of last event included in this checkpoint
        """
        files = []
        for path, hash_value in file_hashes.items():
            path_str = str(path)
            content = file_contents.get(path_str) or file_contents.get(path)
            if content is not None:
                files.append(
                    CheckpointFile(
                        path=path_str,
                        hash=hash_value,
                        content=content,
                    )
                )
        return cls(
            email=email,
            files=files,
            last_event_timestamp=last_event_timestamp,
        )

    def to_file_hashes(self) -> Dict[Path, str]:
        """Convert checkpoint files to file_hashes dict."""
        return {Path(f.path): f.hash for f in self.files}

    def to_file_contents(self) -> Dict[str, str]:
        """Convert checkpoint files to file_contents dict."""
        return {f.path: f.content for f in self.files}

    def as_compressed_data(self) -> bytes:
        """Compress checkpoint for storage."""
        return compress_data(self.model_dump_json().encode("utf-8"))

    @classmethod
    def from_compressed_data(cls, data: bytes) -> "Checkpoint":
        """Load checkpoint from compressed data."""
        uncompressed_data = uncompress_data(data)
        return cls.model_validate_json(uncompressed_data)
