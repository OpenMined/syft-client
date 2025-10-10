"""
Sync history management for echo prevention
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional


class SyncHistory:
    """Manages sync history to prevent echo loops"""

    def __init__(self, syftbox_dir: Path):
        self.syftbox_dir = syftbox_dir
        self.history_dir = syftbox_dir / ".syft_sync" / "history"
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def compute_file_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of file contents + path from /datasites/ onward"""
        sha256_hash = hashlib.sha256()

        # Normalize the file path
        normalized_path = os.path.normpath(os.path.abspath(file_path))

        # Extract path from /datasites/ onward
        # This ensures the same file has the same hash regardless of which SyftBox it's in
        datasites_marker = os.sep + "datasites" + os.sep
        if datasites_marker in normalized_path:
            # Get everything after /datasites/
            datasites_idx = normalized_path.find(datasites_marker)
            relative_path = normalized_path[
                datasites_idx + 1 :
            ]  # +1 to skip the leading separator
        else:
            # Fallback to path relative to syftbox_dir if not in datasites
            try:
                relative_path = os.path.relpath(normalized_path, self.syftbox_dir)
            except ValueError:
                relative_path = normalized_path

        # Add the datasites-relative path to hash
        sha256_hash.update(relative_path.encode("utf-8"))

        # Add file contents to hash
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def is_recent_sync(
        self,
        file_path: str,
        direction: Optional[str] = None,
        threshold_seconds: int = 60,
        operation: Optional[str] = None,
        verbose: bool = False,
    ) -> bool:
        """Check if a file was recently synced in a specific direction (to prevent echoes)

        Args:
            file_path: Path to the file to check
            direction: Optional direction to check ('incoming' or 'outgoing').
                      If None, checks any recent sync regardless of direction.
            threshold_seconds: Time window to consider as "recent"
            operation: Optional operation type to check ('sync' or 'delete').
                      If None, checks any operation type.

        Returns:
            True if file was recently synced in the specified direction
        """
        try:
            if verbose:
                print(
                    f"   🔍 Checking sync history for: {file_path}, direction={direction}, operation={operation}",
                    flush=True,
                )

            # For deletion checks, we need to look through ALL metadata files
            # since we can't compute the hash of a non-existent file
            if operation == "delete" and not os.path.exists(file_path):
                if verbose:
                    print(
                        f"      File doesn't exist, checking all metadata for deletion history",
                        flush=True,
                    )

                # Get relative path for comparison
                try:
                    relative_path = os.path.relpath(file_path, self.syftbox_dir)
                except ValueError:
                    relative_path = file_path

                # Check all hash directories
                for hash_dir in self.history_dir.iterdir():
                    if not hash_dir.is_dir():
                        continue

                    metadata_path = hash_dir / "metadata.json"
                    if not metadata_path.exists():
                        continue

                    with open(metadata_path, "r") as f:
                        metadata = json.load(f)

                    # Check if this metadata is for our file
                    if (
                        metadata.get("file_path") == file_path
                        or metadata.get("file_path") == relative_path
                    ):
                        if verbose:
                            print(f"      Found metadata for deleted file", flush=True)

                        # Check sync history
                        sync_history = metadata.get("sync_history", [])
                        current_time = time.time()

                        for sync in reversed(sync_history):
                            if direction and sync.get("direction") != direction:
                                continue
                            if sync.get("operation", "sync") != "delete":
                                continue

                            sync_time = sync.get("timestamp", 0)
                            age = current_time - sync_time
                            if verbose:
                                print(
                                    f"      Found {direction} delete, age: {age:.1f}s",
                                    flush=True,
                                )
                            if age < threshold_seconds:
                                return True

                        # Found the file but no recent deletion
                        return False

                # File not found in any metadata
                if verbose:
                    print(f"      No metadata found for deleted file", flush=True)
                return False

            # For non-deletion or existing files, use normal hash lookup
            if not os.path.exists(file_path):
                if verbose:
                    print(
                        f"      File doesn't exist and not checking for deletion",
                        flush=True,
                    )
                return False

            file_hash = self.compute_file_hash(file_path)
            metadata_path = self.history_dir / file_hash / "metadata.json"

            if not metadata_path.exists():
                if verbose:
                    print(f"      No metadata found for hash {file_hash}", flush=True)
                return False

            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            if verbose:
                print(
                    f"      Found metadata with {len(metadata.get('sync_history', []))} sync records",
                    flush=True,
                )

            # If no direction specified, check last sync regardless of direction
            if direction is None:
                last_sync = metadata.get("last_sync", {})
                if not last_sync:
                    return False

                last_sync_time = last_sync.get("timestamp", 0)
                current_time = time.time()
                return (current_time - last_sync_time) < threshold_seconds

            # If direction specified, check sync history for recent syncs in that direction
            sync_history = metadata.get("sync_history", [])
            current_time = time.time()

            # Debug: print all directions found
            directions = [s.get("direction", "unknown") for s in sync_history]
            if verbose:
                print(f"      Directions in history: {directions}", flush=True)

            # Check from most recent to oldest
            for sync in reversed(sync_history):
                # Check direction if specified
                if direction and sync.get("direction") != direction:
                    continue

                # Check operation if specified
                if operation and sync.get("operation", "sync") != operation:
                    continue

                # Found a matching sync
                sync_time = sync.get("timestamp", 0)
                age = current_time - sync_time
                sync_op = sync.get("operation", "sync")
                if verbose:
                    print(
                        f"      Found {direction} {sync_op}, age: {age:.1f}s (threshold: {threshold_seconds}s)",
                        flush=True,
                    )
                if age < threshold_seconds:
                    return True
                else:
                    # If the most recent sync in this direction is old, no need to check further
                    return False

            if verbose:
                print(f"      No {direction} sync found in history", flush=True)
            return False

        except Exception:
            return False

    def record_sync(
        self,
        file_path: str,
        message_id: str,
        peer_email: str,
        transport: str,
        direction: str,
        file_size: int,
        file_hash: Optional[str] = None,
        operation: str = "sync",
        verbose: bool = True,
    ):
        """Record a sync operation in history

        Args:
            file_path: Path to the file
            message_id: Message ID
            peer_email: Email of the peer
            transport: Transport used
            direction: 'incoming' or 'outgoing'
            file_size: Size of the file
            file_hash: Optional pre-computed hash (useful when recording before file exists)
            operation: Type of operation ('sync' or 'delete')
        """
        # Print only in verbose mode
        import sys

        if verbose:
            print(
                f"📝 Recording sync: {file_path} direction={direction} peer={peer_email}",
                file=sys.stderr,
                flush=True,
            )

        # Use provided hash or compute it
        if file_hash is None:
            file_hash = self.compute_file_hash(file_path)

        hash_dir = self.history_dir / file_hash
        hash_dir.mkdir(exist_ok=True)

        metadata_path = hash_dir / "metadata.json"

        # Load existing metadata or create new
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
        else:
            metadata = {
                "file_path": file_path,
                "file_hash": file_hash,
                "sync_history": [],
            }

        # Update with latest sync
        sync_record = {
            "message_id": message_id,
            "timestamp": time.time(),
            "peer": peer_email,
            "transport": transport,
            "direction": direction,
            "file_size": file_size,
            "operation": operation,
        }

        # Always update the stored file path to ensure we can find it later
        try:
            relative_path = os.path.relpath(file_path, self.syftbox_dir)
        except ValueError:
            relative_path = file_path
        metadata["file_path"] = relative_path

        metadata["last_sync"] = sync_record
        metadata["sync_history"].append(sync_record)

        # Keep only last 100 sync records
        metadata["sync_history"] = metadata["sync_history"][-100:]

        # Save metadata
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        # Also save individual sync record
        sync_record_path = hash_dir / f"{message_id}.json"
        with open(sync_record_path, "w") as f:
            json.dump(sync_record, f, indent=2)

    def warm_up_from_directory(
        self, directory: Optional[Path] = None, verbose: bool = False
    ):
        """Scan directory and record all existing files in sync history as 'local' files"""
        scan_dir = directory or self.syftbox_dir

        if verbose:
            print(f"📂 Warming up sync history from: {scan_dir}")

        files_added = 0

        # Walk the directory
        for root, dirs, files in os.walk(scan_dir):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for file in files:
                # Skip hidden files
                if file.startswith("."):
                    continue

                file_path = os.path.join(root, file)

                # Check if already in sync history
                try:
                    file_hash = self.compute_file_hash(file_path)
                    metadata_path = self.history_dir / file_hash / "metadata.json"

                    if not metadata_path.exists():
                        # File not in history, add it as a local file
                        file_size = os.path.getsize(file_path)
                        self.record_sync(
                            file_path,
                            f"warmup_{int(time.time() * 1000)}",
                            "local",  # Mark as local file
                            "warmup",
                            "local",  # Direction is local
                            file_size,
                            file_hash=file_hash,
                            verbose=verbose,
                        )
                        files_added += 1
                except Exception as e:
                    if verbose:
                        print(f"   ⚠️  Could not warm up {file_path}: {e}")

        if verbose:
            print(f"   ✅ Added {files_added} files to sync history")

    def get_history(self, file_path: str, limit: int = 10) -> List[Dict]:
        """Get sync history for a file"""
        try:
            file_hash = self.compute_file_hash(file_path)
            metadata_path = self.history_dir / file_hash / "metadata.json"

            if not metadata_path.exists():
                return []

            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            history = metadata.get("sync_history", [])
            return history[-limit:] if limit else history

        except Exception:
            return []
