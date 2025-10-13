"""
Path resolution and management utilities
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..syft_client import SyftClient


class PathResolver:
    """Handles path resolution for syft:// URLs and SyftBox directory management"""

    def __init__(self, client: "SyftClient"):
        self.client = client

    def resolve_syft_path(self, path: str) -> str:
        """
        Resolve a syft:// URL to a full file path

        Supports:
        - syft://filename.txt -> /path/to/SyftBox_email/datasites/filename.txt
        - syft://folder/filename.txt -> /path/to/SyftBox_email/datasites/folder/filename.txt
        - Regular paths are returned unchanged

        Args:
            path: Path that may start with syft://

        Returns:
            Resolved full path
        """
        if not path.startswith("syft://"):
            # Not a syft URL, return as-is
            return path

        # Get SyftBox directory
        syftbox_dir = self.get_syftbox_directory()
        if not syftbox_dir:
            raise ValueError("Could not determine SyftBox directory")

        # Extract the relative path after syft://
        relative_path = path[7:]  # Remove "syft://"

        # Build the full path (always in datasites)
        full_path = syftbox_dir / "datasites" / relative_path

        return str(full_path)

    def get_syftbox_directory(self) -> Optional[Path]:
        """Get the local SyftBox directory path"""
        return self.client.get_syftbox_directory()

    def validate_path_ownership(self, path: str) -> bool:
        """
        Ensure path is within user's SyftBox directory

        Args:
            path: Path to validate

        Returns:
            True if path is within user's SyftBox, False otherwise
        """
        abs_path = os.path.abspath(path)
        expected_syftbox = self.get_syftbox_directory()

        if expected_syftbox is None:
            return False

        expected_syftbox_str = str(expected_syftbox)

        # Check if the file is within this specific client's SyftBox
        return abs_path.startswith(expected_syftbox_str + os.sep)

    def get_relative_syftbox_path(self, full_path: str) -> Optional[str]:
        """
        Get the relative path within SyftBox from a full path

        Args:
            full_path: Full file system path

        Returns:
            Relative path from SyftBox root, or None if not within SyftBox
        """
        abs_path = os.path.abspath(full_path)
        expected_syftbox = self.get_syftbox_directory()

        if expected_syftbox is None:
            return None

        expected_syftbox_str = str(expected_syftbox)

        if not abs_path.startswith(expected_syftbox_str + os.sep):
            return None

        # Return relative path from SyftBox root
        return os.path.relpath(abs_path, expected_syftbox_str)


__all__ = ["PathResolver"]
