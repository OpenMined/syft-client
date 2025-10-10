"""
File index for tracking all files and their hashes in the SyftBox
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional, Set


class FileIndex:
    """Maintains an index of all files in the SyftBox with their hashes"""

    def __init__(self, syftbox_dir: Path):
        self.syftbox_dir = syftbox_dir
        self.index_file = syftbox_dir / ".syft_sync" / "file_index.json"
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        self.index: Dict[str, Dict] = {}
        self._load_index()

    def _load_index(self):
        """Load the index from disk"""
        if self.index_file.exists():
            try:
                with open(self.index_file, "r") as f:
                    self.index = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load file index: {e}")
                self.index = {}

    def _save_index(self):
        """Save the index to disk"""
        try:
            with open(self.index_file, "w") as f:
                json.dump(self.index, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save file index: {e}")

    def compute_file_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of file contents + path"""
        sha256_hash = hashlib.sha256()

        # Include relative path in hash
        try:
            relative_path = os.path.relpath(file_path, self.syftbox_dir)
        except ValueError:
            relative_path = file_path

        sha256_hash.update(relative_path.encode("utf-8"))

        # Add file contents
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        return sha256_hash.hexdigest()

    def add_file(self, file_path: str, source: str = "local"):
        """Add or update a file in the index

        Args:
            file_path: Path to the file
            source: Where the file came from ('local' or peer email)
        """
        if not os.path.exists(file_path):
            return

        try:
            relative_path = os.path.relpath(file_path, self.syftbox_dir)
        except ValueError:
            relative_path = file_path

        try:
            file_hash = self.compute_file_hash(file_path)
            stat = os.stat(file_path)

            self.index[relative_path] = {
                "hash": file_hash,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "source": source,
                "last_seen": time.time(),
            }

            self._save_index()

        except Exception as e:
            print(f"Warning: Could not index file {file_path}: {e}")

    def remove_file(self, file_path: str):
        """Remove a file from the index"""
        try:
            relative_path = os.path.relpath(file_path, self.syftbox_dir)
        except ValueError:
            relative_path = file_path

        if relative_path in self.index:
            del self.index[relative_path]
            self._save_index()

    def get_file_info(self, file_path: str) -> Optional[Dict]:
        """Get info about a file from the index"""
        try:
            relative_path = os.path.relpath(file_path, self.syftbox_dir)
        except ValueError:
            relative_path = file_path

        return self.index.get(relative_path)

    def get_file_source(self, file_path: str) -> Optional[str]:
        """Get the source of a file (who created/sent it)"""
        info = self.get_file_info(file_path)
        return info.get("source") if info else None

    def scan_directory(self, directory: Optional[Path] = None):
        """Scan directory and update index with all files"""
        scan_dir = directory or self.syftbox_dir

        # First, mark all existing entries as "not seen"
        seen_files = set()

        # Walk the directory
        for root, dirs, files in os.walk(scan_dir):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for file in files:
                # Skip hidden files
                if file.startswith("."):
                    continue

                file_path = os.path.join(root, file)
                try:
                    relative_path = os.path.relpath(file_path, self.syftbox_dir)
                except ValueError:
                    relative_path = file_path

                seen_files.add(relative_path)

                # Check if file needs updating
                if relative_path in self.index:
                    # Check if file has changed
                    try:
                        stat = os.stat(file_path)
                        if stat.st_mtime > self.index[relative_path].get("mtime", 0):
                            # File has been modified, re-index
                            self.add_file(
                                file_path,
                                source=self.index[relative_path].get("source", "local"),
                            )
                    except:
                        pass
                else:
                    # New file, add to index
                    self.add_file(file_path, source="local")

        # Remove files that no longer exist
        files_to_remove = set(self.index.keys()) - seen_files
        for file_path in files_to_remove:
            del self.index[file_path]

        if files_to_remove:
            self._save_index()

    def mark_as_received(self, file_path: str, sender: str):
        """Mark a file as received from a specific sender"""
        self.add_file(file_path, source=sender)
