"""
SyftMessage class for creating and managing messages
"""

import json
import os
import shutil
import tarfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class SyftMessage:
    """Represents a message to be sent between SyftBox users"""

    def __init__(
        self,
        message_id: str,
        sender_email: str,
        recipient_email: str,
        message_root: Path,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a SyftMessage

        Args:
            message_id: Unique identifier for the message
            sender_email: Email of the sender
            recipient_email: Email of the recipient
            message_root: Root directory for the message
            metadata: Optional metadata dictionary
        """
        self.message_id = message_id
        self.sender_email = sender_email
        self.recipient_email = recipient_email
        self.message_root = Path(message_root)
        self.metadata = metadata or {}

        # Message directory structure
        self.message_dir = self.message_root / self.message_id
        self.data_dir = self.message_dir / "data"
        self.metadata_file = self.message_dir / f"{self.message_id}.json"

    @classmethod
    def create(
        cls,
        sender_email: str,
        recipient_email: str,
        message_root: Path,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "SyftMessage":
        """
        Create a new SyftMessage with a unique ID

        Args:
            sender_email: Email of the sender
            recipient_email: Email of the recipient
            message_root: Root directory for the message
            metadata: Optional metadata dictionary

        Returns:
            New SyftMessage instance
        """
        # Generate unique message ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        message_id = f"msg_{timestamp}_{unique_id}"

        # Create message instance
        message = cls(message_id, sender_email, recipient_email, message_root, metadata)

        # Create directory structure
        message.message_dir.mkdir(parents=True, exist_ok=True)
        message.data_dir.mkdir(exist_ok=True)

        return message

    def add_file(self, source_path: str, relative_path: Optional[str] = None) -> bool:
        """
        Add a file to the message

        Args:
            source_path: Path to the source file
            relative_path: Optional relative path within the message (defaults to basename)

        Returns:
            True if successful
        """
        source = Path(source_path)

        if not source.exists():
            print(f"❌ Source file not found: {source_path}")
            return False

        # Determine destination path
        if relative_path:
            dest = self.data_dir / relative_path
        else:
            dest = self.data_dir / source.name

        # Create parent directories if needed
        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            if source.is_file():
                shutil.copy2(source, dest)
            else:
                # Copy directory
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(source, dest)
            return True
        except Exception as e:
            print(f"❌ Error adding file: {e}")
            return False

    def add_deletion_marker(self, path: str) -> bool:
        """
        Add a deletion marker for a file/folder

        Args:
            path: Path that was deleted (relative to SyftBox)

        Returns:
            True if successful
        """
        self.metadata["deletion"] = True
        self.metadata["deleted_path"] = path
        self.metadata["deletion_time"] = datetime.now().isoformat()
        return True

    def write_metadata(self) -> bool:
        """
        Write metadata to the message

        Returns:
            True if successful
        """
        try:
            # Add standard metadata
            self.metadata.update(
                {
                    "message_id": self.message_id,
                    "sender": self.sender_email,
                    "recipient": self.recipient_email,
                    "created_at": datetime.now().isoformat(),
                    "syft_version": "0.1.0",  # TODO: Get from package version
                }
            )

            # Write metadata file
            with open(self.metadata_file, "w") as f:
                json.dump(self.metadata, f, indent=2)

            return True

        except Exception as e:
            print(f"❌ Error writing metadata: {e}")
            return False

    def create_archive(self) -> Optional[str]:
        """
        Create a tar.gz archive of the message

        Returns:
            Path to the archive file if successful, None otherwise
        """
        try:
            # Write metadata before archiving
            self.write_metadata()

            # Create archive
            archive_path = self.message_root / f"{self.message_id}.tar.gz"

            with tarfile.open(archive_path, "w:gz") as tar:
                # Add the message directory
                tar.add(self.message_dir, arcname=self.message_id)

            return str(archive_path)

        except Exception as e:
            print(f"❌ Error creating archive: {e}")
            return None

    def get_archive_size(self) -> int:
        """
        Get the size of the archive file

        Returns:
            Size in bytes, or 0 if archive doesn't exist
        """
        archive_path = self.message_root / f"{self.message_id}.tar.gz"
        if archive_path.exists():
            return archive_path.stat().st_size
        return 0

    def cleanup(self):
        """Clean up temporary message files"""
        try:
            # Remove message directory
            if self.message_dir.exists():
                shutil.rmtree(self.message_dir)

            # Remove archive
            archive_path = self.message_root / f"{self.message_id}.tar.gz"
            if archive_path.exists():
                archive_path.unlink()

        except Exception as e:
            print(f"⚠️  Error cleaning up message: {e}")


__all__ = ["SyftMessage"]
