"""
Message sending functionality for sync
"""

import os
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional, Tuple

from ..core.paths import PathResolver
from .message import SyftMessage
from .peers import PeerManager
from .transport_negotiator import TransportNegotiator

if TYPE_CHECKING:
    from ..syft_client import SyftClient


class MessageSender:
    """Handles sending messages to contacts"""

    def __init__(self, client: "SyftClient"):
        self.client = client
        self.peers = PeerManager(client)
        self.paths = PathResolver(client)
        self.negotiator = TransportNegotiator(client)

    def send_to_peers(self, path: str) -> Dict[str, bool]:
        """
        Send file/folder to all contacts

        Args:
            path: Path to the file or folder to send (supports syft:// URLs)

        Returns:
            Dict mapping peer emails to success status
        """
        # Resolve syft:// URLs
        resolved_path = self.paths.resolve_syft_path(path)

        # Check if path exists
        if not os.path.exists(resolved_path):
            print(f"❌ Path not found: {resolved_path}")
            if path.startswith("syft://"):
                print(f"   (resolved from: {path})")
            return {}

        # Get list of contacts
        peers_list = self.peers.peers
        if not peers_list:
            print("❌ No peers to send to. Add peers first with add_peer()")
            return {}

        verbose = getattr(self.client, "verbose", True)
        if verbose:
            print(
                f"📤 Sending {os.path.basename(resolved_path)} to {len(peers_list)} peer(s)..."
            )

        results = {}
        successful = 0
        failed = 0

        for i, peer_email in enumerate(peers_list, 1):
            if verbose:
                print(f"\n[{i}/{len(peers_list)}] Sending to {peer_email}...")

            try:
                # Use negotiator to choose best transport
                success = self.send_to(resolved_path, peer_email)
                results[peer_email] = success

                if success:
                    if verbose:
                        print(f"   ✅ Successfully sent to {peer_email}")
                    successful += 1
                else:
                    if verbose:
                        print(f"   ❌ Failed to send to {peer_email}")
                    failed += 1

            except Exception as e:
                if verbose:
                    print(f"   ❌ Error sending to {peer_email}: {str(e)}")
                results[peer_email] = False
                failed += 1

        # Summary
        if verbose:
            print(f"\n📊 Summary:")
            print(f"   ✅ Successful: {successful}")
            print(f"   ❌ Failed: {failed}")
            print(f"   📨 Total: {len(peers_list)}")

        return results

    def send_to(
        self,
        path: str,
        recipient: str,
        requested_latency_ms: Optional[int] = None,
        priority: str = "normal",
        transport: Optional[str] = None,
    ) -> bool:
        """
        Send file/folder to specific recipient

        Args:
            path: Path to the file or folder to send (supports syft:// URLs)
            recipient: Email address of the recipient
            requested_latency_ms: Desired latency in milliseconds (optional)
            priority: "urgent", "normal", or "background" (default: "normal")
            transport: Specific transport to use (e.g., "gdrive_files", "gsheets", "gmail").
                      If None, automatically selects best transport.

        Returns:
            True if successful, False otherwise
        """
        # Check if recipient is in contacts list
        if recipient not in self.peers.peers:
            print(
                f"❌ {recipient} is not in your peers. Add them first with add_peer()"
            )
            return False

        # Get peer object
        peer = self.peers.get_peer(recipient)
        if not peer:
            print(f"❌ Could not load peer information for {recipient}")
            return False

        # Create temporary directory that persists for the whole send operation
        temp_dir = tempfile.mkdtemp()
        try:
            # Prepare message to get actual compressed size
            message_info = self.prepare_message(path, recipient, temp_dir)
            if not message_info:
                return False

            message_id, archive_path, archive_size = message_info

            # If user specified a transport, validate and use it
            if transport:
                # Validate that the transport is available for this peer
                if transport not in peer.available_transports:
                    print(
                        f"❌ Transport '{transport}' is not available for {recipient}"
                    )
                    print(
                        f"   Available transports: {list(peer.available_transports.keys())}"
                    )
                    return False

                if not peer.available_transports[transport].verified:
                    print(f"⚠️  Transport '{transport}' is not verified for {recipient}")

                # Get transport instance
                transport_obj = self._get_transport_instance(transport)
                if not transport_obj:
                    print(f"❌ Transport {transport} is not available")
                    return False

                # Send directly with specified transport
                if self.client.verbose:
                    print(f"📤 Using specified transport: {transport}")
                return transport_obj.send_to(archive_path, recipient, message_id)
            else:
                # Use the generic send method that selects best transport
                return self._send_prepared_archive(
                    archive_path, recipient, archive_size, message_id
                )
        finally:
            # Clean up temp directory
            import shutil

            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def prepare_message(
        self, path: str, recipient: str, temp_dir: str, sync_from_anywhere: bool = False
    ) -> Optional[Tuple[str, str, int]]:
        """
        Prepare a SyftMessage archive for sending

        Args:
            path: Path to the file or folder to send
            recipient: Email address of the recipient
            temp_dir: Temporary directory to create the message in
            sync_from_anywhere: If True, allow sending files from outside SyftBox (default: False)

        Returns:
            Tuple of (message_id, archive_path, archive_size) if successful, None otherwise
        """
        # Resolve path
        resolved_path = self.paths.resolve_syft_path(path)

        # Check if path exists
        if not os.path.exists(resolved_path):
            print(f"❌ Path not found: {resolved_path}")
            if path.startswith("syft://"):
                print(f"   (resolved from: {path})")
            return None

        # Validate that the file is within THIS client's SyftBox folder (unless override is set)
        if not sync_from_anywhere and not self.paths.validate_path_ownership(
            resolved_path
        ):
            syftbox_dir = self.paths.get_syftbox_directory()
            print(f"❌ Error: Files must be within YOUR SyftBox folder to be sent")
            print(f"   Your SyftBox: {syftbox_dir}")
            print(f"   File path: {resolved_path}")
            print(
                f"   Tip: Move your file to {syftbox_dir}/datasites/ or use syft:// URLs"
            )
            print(f"   Example: syft://filename.txt")
            return None

        try:
            # Create SyftMessage
            message = SyftMessage.create(
                sender_email=self.client.email,
                recipient_email=recipient,
                message_root=Path(temp_dir),
            )

            # Get relative path from SyftBox root or use basename if sync_from_anywhere
            if sync_from_anywhere:
                # If syncing from anywhere, use a simple path structure
                source_path = Path(resolved_path)
                if source_path.is_file():
                    relative_path = f"external/{source_path.name}"
                else:
                    relative_path = f"external/{source_path.name}"
                if self.client.verbose:
                    print(
                        f"⚠️  Syncing from outside SyftBox - file will be placed in: {relative_path}"
                    )
            else:
                relative_path = self.paths.get_relative_syftbox_path(resolved_path)
                if not relative_path:
                    print(f"❌ Could not determine relative path within SyftBox")
                    return None

            # Add file/folder to message
            if not message.add_file(resolved_path, relative_path):
                return None

            # Create archive
            archive_path = message.create_archive()
            if not archive_path:
                return None

            # Get archive size
            archive_size = message.get_archive_size()

            return (message.message_id, archive_path, archive_size)

        except Exception as e:
            print(f"❌ Error preparing message: {e}")
            return None

    def prepare_deletion_message(
        self, path: str, recipient: str, temp_dir: str
    ) -> Optional[Tuple[str, str, int]]:
        """
        Prepare a SyftMessage archive for deletion

        Args:
            path: Path to the deleted file (supports syft:// URLs)
            recipient: Email address of the recipient
            temp_dir: Temporary directory to create the message in

        Returns:
            Tuple of (message_id, archive_path, archive_size) if successful, None otherwise
        """
        # Resolve path
        resolved_path = self.paths.resolve_syft_path(path)

        # Get relative path from SyftBox root
        relative_path = self.paths.get_relative_syftbox_path(resolved_path)
        if not relative_path:
            # If file is not in SyftBox, use the full path as relative
            # This can happen if file was already deleted
            relative_path = resolved_path

        try:
            # Create SyftMessage
            message = SyftMessage.create(
                sender_email=self.client.email,
                recipient_email=recipient,
                message_root=Path(temp_dir),
            )

            # Create deletion manifest
            deletion_manifest = {
                "operation": "delete",
                "items": [
                    {
                        "path": relative_path,
                        "timestamp": time.time(),
                        "deleted_by": self.client.email,
                    }
                ],
            }

            # Write deletion manifest to message directory
            manifest_path = (
                Path(temp_dir) / message.message_id / "deletion_manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)

            import json

            with open(manifest_path, "w") as f:
                json.dump(deletion_manifest, f, indent=2)

            # Create archive
            archive_path = message.create_archive()
            if not archive_path:
                return None

            # Get archive size
            archive_size = message.get_archive_size()

            return (message.message_id, archive_path, archive_size)

        except Exception as e:
            print(f"❌ Error preparing deletion message: {e}")
            return None

    def send_deletion(self, path: str, recipient: str) -> bool:
        """
        Send a deletion message for a file to a specific recipient

        Args:
            path: Path to the deleted file (supports syft:// URLs)
            recipient: Email address of the recipient

        Returns:
            True if successful, False otherwise
        """
        # Create temporary directory for the deletion message
        temp_dir = tempfile.mkdtemp()
        try:
            # Prepare deletion message
            message_info = self.prepare_deletion_message(path, recipient, temp_dir)
            if not message_info:
                return False

            message_id, archive_path, archive_size = message_info

            # Send the prepared archive
            return self._send_prepared_archive(archive_path, recipient, archive_size)

        finally:
            # Clean up temp directory
            import shutil

            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def prepare_move_message(
        self, source_path: str, dest_path: str, recipient: str, temp_dir: str
    ) -> Optional[Tuple[str, str, int]]:
        """
        Prepare a SyftMessage archive for move operation

        Args:
            source_path: Path to the source file/directory (supports syft:// URLs)
            dest_path: Path to the destination file/directory (supports syft:// URLs)
            recipient: Email address of the recipient
            temp_dir: Temporary directory to create the message in

        Returns:
            Tuple of (message_id, archive_path, archive_size) if successful, None otherwise
        """
        # Resolve paths
        resolved_source = self.paths.resolve_syft_path(source_path)
        resolved_dest = self.paths.resolve_syft_path(dest_path)

        # Get relative paths from SyftBox root
        relative_source = self.paths.get_relative_syftbox_path(resolved_source)
        relative_dest = self.paths.get_relative_syftbox_path(resolved_dest)

        if not relative_source:
            # If file is not in SyftBox, use the full path as relative
            relative_source = resolved_source

        if not relative_dest:
            relative_dest = resolved_dest

        try:
            # Create SyftMessage
            message = SyftMessage.create(
                sender_email=self.client.email,
                recipient_email=recipient,
                message_root=Path(temp_dir),
            )

            # Create move manifest
            move_manifest = {
                "operation": "move",
                "items": [
                    {
                        "source_path": relative_source,
                        "dest_path": relative_dest,
                        "timestamp": time.time(),
                        "moved_by": self.client.email,
                    }
                ],
            }

            # Write move manifest to message directory
            manifest_path = Path(temp_dir) / message.message_id / "move_manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)

            import json

            with open(manifest_path, "w") as f:
                json.dump(move_manifest, f, indent=2)

            # Create archive
            archive_path = message.create_archive()
            if not archive_path:
                return None

            # Get archive size
            archive_size = message.get_archive_size()

            return (message.message_id, archive_path, archive_size)

        except Exception as e:
            print(f"❌ Error preparing move message: {e}")
            return None

    def send_move(self, source_path: str, dest_path: str, recipient: str) -> bool:
        """
        Send a move message for a file/directory to a specific recipient

        Args:
            source_path: Path to the source file/directory (supports syft:// URLs)
            dest_path: Path to the destination file/directory (supports syft:// URLs)
            recipient: Email address of the recipient

        Returns:
            True if successful, False otherwise
        """
        # Create temporary directory for the move message
        temp_dir = tempfile.mkdtemp()
        try:
            # Prepare move message
            message_info = self.prepare_move_message(
                source_path, dest_path, recipient, temp_dir
            )
            if not message_info:
                return False

            message_id, archive_path, archive_size = message_info

            # Send the prepared archive
            return self._send_prepared_archive(archive_path, recipient, archive_size)

        finally:
            # Clean up temp directory
            import shutil

            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def send_move_to_peers(self, source_path: str, dest_path: str) -> Dict[str, bool]:
        """
        Send move message to all peers

        Args:
            source_path: Path to the source file/directory (supports syft:// URLs)
            dest_path: Path to the destination file/directory (supports syft:// URLs)

        Returns:
            Dict mapping peer emails to success status
        """
        # Get list of peers
        peers_list = self.peers.peers
        if not peers_list:
            print("❌ No peers to send move to")
            return {}

        verbose = getattr(self.client, "verbose", True)
        if verbose:
            # Resolve paths for display
            resolved_source = self.paths.resolve_syft_path(source_path)
            resolved_dest = self.paths.resolve_syft_path(dest_path)
            print(
                f"🚚 Sending move of {os.path.basename(resolved_source)} → {os.path.basename(resolved_dest)} to {len(peers_list)} peer(s)..."
            )

        results = {}
        successful = 0
        failed = 0

        for i, peer_email in enumerate(peers_list, 1):
            if verbose:
                print(f"\n[{i}/{len(peers_list)}] Sending move to {peer_email}...")

            try:
                success = self.send_move(source_path, dest_path, peer_email)
                results[peer_email] = success

                if success:
                    if verbose:
                        print(f"   ✅ Successfully sent move to {peer_email}")
                    successful += 1
                else:
                    if verbose:
                        print(f"   ❌ Failed to send move to {peer_email}")
                    failed += 1

            except Exception as e:
                if verbose:
                    print(f"   ❌ Error sending move to {peer_email}: {str(e)}")
                results[peer_email] = False
                failed += 1

        # Summary
        if verbose:
            print(f"\n📊 Summary:")
            print(f"   ✅ Successful: {successful}")
            print(f"   ❌ Failed: {failed}")
            print(f"   🚚 Total: {len(peers_list)}")

        return results

    def send_deletion_to_peers(self, path: str) -> Dict[str, bool]:
        """
        Send deletion message to all peers

        Args:
            path: Path to the deleted file (supports syft:// URLs)

        Returns:
            Dict mapping peer emails to success status
        """
        # Get list of peers
        peers_list = self.peers.peers
        if not peers_list:
            print("❌ No peers to send deletion to")
            return {}

        verbose = getattr(self.client, "verbose", True)
        if verbose:
            # Resolve path for display
            resolved_path = self.paths.resolve_syft_path(path)
            print(
                f"🗑️  Sending deletion of {os.path.basename(resolved_path)} to {len(peers_list)} peer(s)..."
            )

        results = {}
        successful = 0
        failed = 0

        for i, peer_email in enumerate(peers_list, 1):
            if verbose:
                print(f"\n[{i}/{len(peers_list)}] Sending deletion to {peer_email}...")

            try:
                success = self.send_deletion(path, peer_email)
                results[peer_email] = success

                if success:
                    if verbose:
                        print(f"   ✅ Successfully sent deletion to {peer_email}")
                    successful += 1
                else:
                    if verbose:
                        print(f"   ❌ Failed to send deletion to {peer_email}")
                    failed += 1

            except Exception as e:
                if verbose:
                    print(f"   ❌ Error sending deletion to {peer_email}: {str(e)}")
                results[peer_email] = False
                failed += 1

        # Summary
        if verbose:
            print(f"\n📊 Summary:")
            print(f"   ✅ Successful: {successful}")
            print(f"   ❌ Failed: {failed}")
            print(f"   🗑️  Total: {len(peers_list)}")

        return results

    def _get_sync_platform(self):
        """Get a platform that supports sync functionality"""
        # Look for platforms with sync capabilities
        # Priority order: google_org, google_personal
        for platform_name in ["google_org", "google_personal"]:
            if platform_name in self.client._platforms:
                platform = self.client._platforms[platform_name]
                # Check if it has the required transport
                if hasattr(platform, "gdrive_files"):
                    return platform

        return None

    def _send_prepared_archive(
        self,
        archive_path: str,
        recipient: str,
        archive_size: int,
        message_id: Optional[str] = None,
    ) -> bool:
        """
        Send a pre-prepared archive to a recipient

        Args:
            archive_path: Path to the prepared archive
            recipient: Email address of the recipient
            archive_size: Size of the archive in bytes
            message_id: Optional message ID from the archive

        Returns:
            True if successful, False otherwise
        """
        # Check if recipient is in contacts list
        if recipient not in self.peers.peers:
            print(
                f"❌ {recipient} is not in your peers. Add them first with add_peer()"
            )
            return False

        # Get peer object
        peer = self.peers.get_peer(recipient)
        if not peer:
            print(f"❌ Could not load peer information for {recipient}")
            return False

        # Extract message_id from archive filename if not provided
        if not message_id:
            archive_name = os.path.basename(archive_path)
            # Archive name format: msg_YYYYMMDD_HHMMSS_hash.tar.gz
            if archive_name.startswith("msg_") and ".tar.gz" in archive_name:
                # Extract everything before .tar.gz
                message_id = archive_name.split(".tar.gz")[0]

        # Select transport
        transport_name = self.negotiator.select_transport(
            peer=peer, file_size=archive_size, priority="normal"
        )

        if not transport_name:
            print(f"❌ No suitable transport found for sending to {recipient}")
            return False

        # Get transport instance
        transport = self._get_transport_instance(transport_name)
        if not transport:
            print(f"❌ Transport {transport_name} is not available")
            return False

        if self.client.verbose:
            print(
                f"   📍 Using transport from platform: {transport.__class__.__module__}",
                flush=True,
            )

        # Send the archive directly via transport
        if hasattr(transport, "send_to"):
            if self.client.verbose:
                print(f"   📤 Sending via {transport_name}")
            try:
                result = transport.send_to(archive_path, recipient, message_id)
                if not result and self.client.verbose:
                    print(f"   ⚠️  Transport returned False for {recipient}")
                return result
            except Exception as e:
                print(f"   ❌ Error in transport.send_to: {e}")
                return False
        else:
            print(f"❌ Transport {transport_name} does not implement send_to() method")
            return False

    def _get_transport_instance(self, transport_name: str):
        """Get transport instance by name"""
        for platform_name, platform in self.client._platforms.items():
            if hasattr(platform, transport_name):
                return getattr(platform, transport_name)
        return None


__all__ = ["MessageSender"]
