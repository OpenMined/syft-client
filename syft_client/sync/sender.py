"""
Message sending functionality for sync
"""

import os
import tempfile
import time
from typing import Dict, Optional, Tuple, TYPE_CHECKING
from pathlib import Path

from .message import SyftMessage
from .peers import PeerManager
from ..core.paths import PathResolver
from .transport_negotiator import TransportNegotiator

if TYPE_CHECKING:
    from ..syft_client import SyftClient


class MessageSender:
    """Handles sending messages to contacts"""
    
    def __init__(self, client: 'SyftClient'):
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
        
        verbose = getattr(self.client, 'verbose', True)
        if verbose:
            print(f"📤 Sending {os.path.basename(resolved_path)} to {len(peers_list)} peer(s)...")
        
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
    
    def send_to(self, path: str, recipient: str, requested_latency_ms: Optional[int] = None, 
                priority: str = "normal", transport: Optional[str] = None) -> bool:
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
            print(f"❌ {recipient} is not in your peers. Add them first with add_peer()")
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
            
            # Determine which transport to use
            if transport:
                # Use the specified transport
                transport_name = transport
                
                # Validate that the transport is available for this peer
                if transport_name not in peer.available_transports:
                    print(f"❌ Transport '{transport_name}' is not available for {recipient}")
                    print(f"   Available transports: {list(peer.available_transports.keys())}")
                    return False
                    
                if not peer.available_transports[transport_name].verified:
                    print(f"⚠️  Transport '{transport_name}' is not verified for {recipient}")
                    
                if self.client.verbose:
                    print(f"📤 Using specified transport: {transport_name}")
            else:
                # Use negotiator to select best transport based on actual archive size
                transport_name = self.negotiator.select_transport(
                    peer=peer,
                    file_size=archive_size,  # Use actual compressed size
                    requested_latency_ms=requested_latency_ms,
                    priority=priority
                )
            
                if not transport_name:
                    print(f"❌ No suitable transport found for sending to {recipient}")
                    return False
            
            # Get transport instance
            transport = self._get_transport_instance(transport_name)
            if not transport:
                print(f"❌ Transport {transport_name} is not available")
                return False
            
            # Send using the selected transport
            start_time = time.time()
            try:
                # Call generic send_to method with prepared archive
                if hasattr(transport, 'send_to'):
                    result = transport.send_to(archive_path, recipient, message_id=message_id)
                else:
                    print(f"❌ Transport {transport_name} does not implement send_to() method")
                    return False
                
                # Record result
                elapsed_ms = (time.time() - start_time) * 1000
                if result:
                    if self.client.verbose:
                        print(f"✅ Successfully sent via {transport_name} in {elapsed_ms:.0f}ms")
                
                return result
                
            except Exception as e:
                print(f"❌ Error sending via {transport_name}: {e}")
                return False
        finally:
            # Clean up temp directory
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    
    def prepare_message(self, path: str, recipient: str, temp_dir: str, sync_from_anywhere: bool = False) -> Optional[Tuple[str, str, int]]:
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
        if not sync_from_anywhere and not self.paths.validate_path_ownership(resolved_path):
            syftbox_dir = self.paths.get_syftbox_directory()
            print(f"❌ Error: Files must be within YOUR SyftBox folder to be sent")
            print(f"   Your SyftBox: {syftbox_dir}")
            print(f"   File path: {resolved_path}")
            print(f"   Tip: Move your file to {syftbox_dir}/datasites/ or use syft:// URLs")
            print(f"   Example: syft://filename.txt")
            return None
        
        try:
            # Create SyftMessage
            message = SyftMessage.create(
                sender_email=self.client.email,
                recipient_email=recipient,
                message_root=Path(temp_dir)
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
                    print(f"⚠️  Syncing from outside SyftBox - file will be placed in: {relative_path}")
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
    
    def send_deletion(self, path: str, recipient: str) -> bool:
        """
        Send a deletion message for a file to a specific recipient
        
        Args:
            path: Path to the deleted file (supports syft:// URLs)
            recipient: Email address of the recipient
            
        Returns:
            True if successful, False otherwise
        """
        # Get platform with sync capability
        platform = self._get_sync_platform()
        if not platform:
            print("❌ No platform available with sync capabilities")
            return False
        
        # Use platform-specific method if available
        if hasattr(platform, 'gdrive_files') and hasattr(platform.gdrive_files, 'send_deletion'):
            return platform.gdrive_files.send_deletion(path, recipient)
        else:
            print("❌ Platform does not support sending deletion messages")
            return False
    
    def send_deletion_to_peers(self, path: str) -> Dict[str, bool]:
        """
        Send deletion message to all peers
        
        Args:
            path: Path to the deleted file (supports syft:// URLs)
            
        Returns:
            Dict mapping peer emails to success status
        """
        # Get platform with sync capability
        platform = self._get_sync_platform()
        if not platform:
            print("❌ No platform available with sync capabilities")
            return {}
        
        # Use platform-specific method if available
        if hasattr(platform, 'gdrive_files') and hasattr(platform.gdrive_files, 'send_deletion_to_friends'):
            # Platform still uses 'friends' terminology internally
            return platform.gdrive_files.send_deletion_to_friends(path)
        else:
            print("❌ Platform does not support sending deletion messages")
            return {}
    
    def _get_sync_platform(self):
        """Get a platform that supports sync functionality"""
        # Look for platforms with sync capabilities
        # Priority order: google_org, google_personal
        for platform_name in ['google_org', 'google_personal']:
            if platform_name in self.client._platforms:
                platform = self.client._platforms[platform_name]
                # Check if it has the required transport
                if hasattr(platform, 'gdrive_files'):
                    return platform
        
        return None
    
    def _get_transport_instance(self, transport_name: str):
        """Get transport instance by name"""
        for platform_name, platform in self.client._platforms.items():
            if hasattr(platform, transport_name):
                return getattr(platform, transport_name)
        return None


__all__ = ['MessageSender']