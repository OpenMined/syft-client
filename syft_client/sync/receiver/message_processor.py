"""
Message processing and merging for the receiver
"""

import json
import os
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional


class MessageProcessor:
    """Processes downloaded messages and merges them into SyftBox"""

    def __init__(self, syftbox_dir: Path, verbose: bool = True):
        """
        Initialize message processor

        Args:
            syftbox_dir: Path to SyftBox directory
            verbose: Whether to print status messages
        """
        self.syftbox_dir = Path(syftbox_dir)
        self.verbose = verbose
        self.inbox_dir = self.syftbox_dir / "inbox"
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

        # Archive directory for processed messages
        self.archive_dir = self.syftbox_dir / ".syft_archive"
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def process_messages(
        self, messages: Dict[str, List[Dict]], peer_email: str
    ) -> Dict[str, int]:
        """
        Process messages from a peer

        Args:
            messages: Dict mapping transport names to message lists
            peer_email: Email of the peer who sent messages

        Returns:
            Dict with counts of processed, failed, and skipped messages
        """
        stats = {"processed": 0, "failed": 0, "skipped": 0}

        for transport, msg_list in messages.items():
            if self.verbose:
                print(
                    f"Processing {len(msg_list)} messages from {peer_email} via {transport}"
                )

            for msg in msg_list:
                try:
                    if self._process_single_message(msg, peer_email, transport):
                        stats["processed"] += 1
                    else:
                        stats["skipped"] += 1
                except Exception as e:
                    if self.verbose:
                        print(f"Error processing message: {e}")
                    stats["failed"] += 1

        return stats

    def approve_inbox_files(self, auto_approve: bool = True) -> Dict[str, int]:
        """
        Approve files from inbox and move them to their final destination

        Args:
            auto_approve: If True, approve all files. If False, would require manual approval (future feature)

        Returns:
            Dict with counts of approved, failed files
        """
        stats = {"approved": 0, "failed": 0, "skipped": 0}

        if not auto_approve:
            # Future: implement manual approval process
            if self.verbose:
                print("Manual approval not yet implemented")
            return stats

        # Look for files in inbox/datasites/
        inbox_datasites = self.inbox_dir / "datasites"
        if not inbox_datasites.exists():
            return stats

        # Process each peer's folder
        for peer_folder in inbox_datasites.iterdir():
            if not peer_folder.is_dir():
                continue

            peer_email = peer_folder.name

            # Destination in main datasites
            dest_folder = self.syftbox_dir / "datasites" / peer_email
            dest_folder.mkdir(parents=True, exist_ok=True)

            # Move all files from inbox to destination
            for item in peer_folder.iterdir():
                try:
                    dest = dest_folder / item.name

                    if self.verbose:
                        print(f"Approving: {item.name} from {peer_email}")

                    # Move the file/directory
                    if item.is_dir():
                        if dest.exists():
                            import shutil

                            shutil.rmtree(dest)
                        item.rename(dest)
                    else:
                        if dest.exists():
                            dest.unlink()
                        item.rename(dest)

                    stats["approved"] += 1

                    if self.verbose:
                        print(f"   ✓ Moved to: {dest}")

                except Exception as e:
                    if self.verbose:
                        print(f"   ✗ Failed to approve {item.name}: {e}")
                    stats["failed"] += 1

        return stats

    def _process_single_message(
        self, message: Dict, peer_email: str, transport: str
    ) -> bool:
        """
        Process a single message

        Returns:
            True if processed, False if skipped
        """
        # Check if message was already extracted (e.g., by gsheets)
        if message.get("extracted_to"):
            # Message was already processed during download
            if self.verbose:
                print(f"   ✓ Message {message.get('id', 'unknown')} already extracted")
            return True

        # Extract message info for non-extracted messages
        file_path = message.get("file_path") or message.get("downloaded_to")
        if file_path and message.get("name"):
            # Construct full path if needed
            file_path = os.path.join(file_path, message.get("name"))
        message_id = message.get("message_id") or message.get("id", "unknown")

        if not file_path or not os.path.exists(file_path):
            if self.verbose:
                print(f"Message file not found: {file_path}")
            return False

        # Check if it's an archive
        if file_path.endswith(".tar.gz"):
            return self._process_archive_message(file_path, message_id, peer_email)
        else:
            return self._process_direct_message(file_path, message_id, peer_email)

    def _process_archive_message(
        self, archive_path: str, message_id: str, peer_email: str
    ) -> bool:
        """Process a tar.gz archive message"""
        try:
            # Extract to temp directory
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Extract archive
                with tarfile.open(archive_path, "r:gz") as tar:
                    tar.extractall(temp_path)

                # Look for metadata
                metadata_path = temp_path / "metadata.json"
                if metadata_path.exists():
                    with open(metadata_path, "r") as f:
                        metadata = json.load(f)
                else:
                    metadata = {"sender": peer_email}

                # Process extracted files
                files_processed = 0
                for item in temp_path.iterdir():
                    if item.name == "metadata.json":
                        continue

                    # Determine target location
                    target_path = self._determine_target_path(item, metadata)

                    # Copy to target
                    if item.is_file():
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, target_path)
                        files_processed += 1
                        if self.verbose:
                            print(f"  Extracted: {target_path.name}")
                    elif item.is_dir():
                        shutil.copytree(item, target_path, dirs_exist_ok=True)
                        files_processed += 1
                        if self.verbose:
                            print(f"  Extracted directory: {target_path.name}")

                # Archive the original message
                if files_processed > 0:
                    self._archive_message(archive_path, message_id, peer_email)
                    return True

        except Exception as e:
            if self.verbose:
                print(f"Error processing archive: {e}")
            return False

        return False

    def _process_direct_message(
        self, file_path: str, message_id: str, peer_email: str
    ) -> bool:
        """Process a direct file message"""
        try:
            file_path = Path(file_path)

            # Determine target location
            # For now, place in datasites/peer_email/
            target_dir = self.syftbox_dir / "datasites" / peer_email
            target_dir.mkdir(parents=True, exist_ok=True)

            target_path = target_dir / file_path.name

            # Copy file
            shutil.copy2(file_path, target_path)

            if self.verbose:
                print(f"  Copied: {target_path.name}")

            # Archive the original
            self._archive_message(str(file_path), message_id, peer_email)

            return True

        except Exception as e:
            if self.verbose:
                print(f"Error processing direct message: {e}")
            return False

    def _determine_target_path(self, source_path: Path, metadata: Dict) -> Path:
        """Determine where to place an extracted file"""
        # Check if metadata specifies a target path
        if "target_path" in metadata:
            return self.syftbox_dir / metadata["target_path"] / source_path.name

        # Check if it's a datasite file
        if "datasite" in metadata:
            return (
                self.syftbox_dir / "datasites" / metadata["datasite"] / source_path.name
            )

        # Default: place in sender's datasite
        sender = metadata.get("sender", "unknown")
        return self.syftbox_dir / "datasites" / sender / source_path.name

    def _archive_message(self, file_path: str, message_id: str, peer_email: str):
        """Move processed message to archive"""
        try:
            source = Path(file_path)
            peer_archive = self.archive_dir / peer_email
            peer_archive.mkdir(exist_ok=True)

            # Create unique archive name
            archive_name = f"{message_id}_{source.name}"
            target = peer_archive / archive_name

            # Move to archive
            if source.exists():
                shutil.move(str(source), str(target))

        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not archive message: {e}")
