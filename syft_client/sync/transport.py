"""
Transport selection and management for sync functionality
"""

import os
import tempfile
from typing import Optional, Tuple, TYPE_CHECKING
from pathlib import Path

from .message import SyftMessage
from ..core.paths import PathResolver

if TYPE_CHECKING:
    from ..syft_client import SyftClient


class TransportSelector:
    """
    Selects appropriate transport method based on file characteristics
    
    Architecture notes:
    - Platforms should have separate transports (gdrive_files, gsheets, etc.)
    - Each transport handles its own sending logic
    - Platform can optionally provide send_auto() to handle transport selection
    - This class provides fallback transport selection if platform doesn't have send_auto
    """
    
    # Google Sheets has a 50,000 character limit per cell
    # Base64 encoding increases size by ~33% (4/3 ratio)
    # So max raw size = 50,000 / (4/3) = 37,500 bytes
    MAX_SHEETS_SIZE = 37_500  # Conservative limit to stay under 50k chars
    
    def __init__(self, client: 'SyftClient'):
        self.client = client
        self.paths = PathResolver(client)
    
    def select_transport(self, archive_size: int) -> str:
        """
        Determine best transport method based on archive size
        
        Args:
            archive_size: Size of the prepared message archive in bytes
            
        Returns:
            Transport method name: 'sheets' or 'drive'
        """
        # Select based on size
        if archive_size <= self.MAX_SHEETS_SIZE:
            return 'sheets'
        else:
            return 'drive'
    
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
    
    def send_auto(self, path: str, recipient: str) -> bool:
        """
        Send using auto-selected transport
        
        Args:
            path: Path to file/folder to send
            recipient: Recipient email address
            
        Returns:
            True if successful
        """
        # Get platform with sync capability
        platform = self._get_sync_platform()
        if not platform:
            print("❌ No platform available with sync capabilities")
            return False
        
        # Create a temporary directory for message preparation
        with tempfile.TemporaryDirectory() as temp_dir:
            # Prepare the message to check size
            result = self.prepare_message(path, recipient, temp_dir)
            if not result:
                return False
            
            message_id, archive_path, archive_size = result
            
            # Select transport based on size
            transport_method = self.select_transport(archive_size)
            
            # Check if platform has send_auto method (preferred)
            if hasattr(platform, 'send_auto'):
                # Let the platform handle transport selection
                return platform.send_auto(path, recipient, archive_size)
            
            # Fallback: manually select transport
            if transport_method == 'sheets' and hasattr(platform, 'gsheets'):
                if self.client.verbose:
                    print(f"📊 Using sheets transport (size: {archive_size:,} bytes)")
                # Use gsheets transport for small files
                if hasattr(platform.gsheets, 'send_file_or_folder'):
                    return platform.gsheets.send_file_or_folder(path, recipient)
                else:
                    # Fall back to drive if sheets doesn't have the method
                    if self.client.verbose:
                        print("⚠️  Sheets send method not available, falling back to drive")
                    transport_method = 'drive'
            
            if transport_method == 'drive' and hasattr(platform, 'gdrive_files'):
                if self.client.verbose:
                    if archive_size < 1024 * 1024:
                        print(f"📦 Using direct upload (size: {archive_size:,} bytes)")
                    else:
                        print(f"📦 Using direct upload (size: {archive_size / (1024*1024):.1f}MB)")
                # Use gdrive_files transport for large files
                if hasattr(platform.gdrive_files, 'send_file_or_folder'):
                    return platform.gdrive_files.send_file_or_folder(path, recipient)
            
            print(f"❌ Platform {platform.platform} does not support sending files")
            return False
    
    def _get_sync_platform(self):
        """Get a platform that supports sync functionality"""
        # Look for platforms with sync capabilities
        # Priority order: google_org, google_personal
        for platform_name in ['google_org', 'google_personal']:
            if platform_name in self.client._platforms:
                platform = self.client._platforms[platform_name]
                return platform
        
        return None


__all__ = ['TransportSelector']