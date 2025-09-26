"""
Message sending functionality for sync
"""

import os
import tempfile
from typing import Dict, Optional, Tuple, TYPE_CHECKING
from pathlib import Path

from .message import SyftMessage
from .contacts import ContactManager
from ..core.paths import PathResolver

if TYPE_CHECKING:
    from ..syft_client import SyftClient


class MessageSender:
    """Handles sending messages to contacts"""
    
    def __init__(self, client: 'SyftClient'):
        self.client = client
        self.contacts = ContactManager(client)
        self.paths = PathResolver(client)
    
    def send_to_contacts(self, path: str) -> Dict[str, bool]:
        """
        Send file/folder to all contacts
        
        Args:
            path: Path to the file or folder to send (supports syft:// URLs)
            
        Returns:
            Dict mapping contact emails to success status
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
        contacts_list = self.contacts.contacts
        if not contacts_list:
            print("❌ No contacts to send to. Add contacts first with add_contact()")
            return {}
        
        verbose = getattr(self.client, 'verbose', True)
        if verbose:
            print(f"📤 Sending {os.path.basename(resolved_path)} to {len(contacts_list)} contact(s)...")
        
        results = {}
        successful = 0
        failed = 0
        
        for i, contact_email in enumerate(contacts_list, 1):
            if verbose:
                print(f"\n[{i}/{len(contacts_list)}] Sending to {contact_email}...")
            
            try:
                # Use auto method to choose best transport
                success = self.send_to(resolved_path, contact_email)
                results[contact_email] = success
                
                if success:
                    if verbose:
                        print(f"   ✅ Successfully sent to {contact_email}")
                    successful += 1
                else:
                    if verbose:
                        print(f"   ❌ Failed to send to {contact_email}")
                    failed += 1
                    
            except Exception as e:
                if verbose:
                    print(f"   ❌ Error sending to {contact_email}: {str(e)}")
                results[contact_email] = False
                failed += 1
        
        # Summary
        if verbose:
            print(f"\n📊 Summary:")
            print(f"   ✅ Successful: {successful}")
            print(f"   ❌ Failed: {failed}")
            print(f"   📨 Total: {len(contacts_list)}")
        
        return results
    
    def send_to(self, path: str, recipient: str) -> bool:
        """
        Send file/folder to specific recipient
        
        Args:
            path: Path to the file or folder to send (supports syft:// URLs)
            recipient: Email address of the recipient
            
        Returns:
            True if successful, False otherwise
        """
        # Check if recipient is in contacts list
        if recipient not in self.contacts.contacts:
            print(f"❌ {recipient} is not in your contacts. Add them first with add_contact()")
            return False
        
        # Get platform with sync capability
        platform = self._get_sync_platform()
        if not platform:
            print("❌ No platform available with sync capabilities")
            return False
        
        # Check if platform has send_auto method
        if hasattr(platform, 'send_auto'):
            return platform.send_auto(path, recipient)
        else:
            print(f"❌ Platform {platform.platform} does not support automatic sending")
            print("   Platform needs to implement send_auto(path, recipient) method")
            return False
    
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
    
    def send_deletion_to_contacts(self, path: str) -> Dict[str, bool]:
        """
        Send deletion message to all contacts
        
        Args:
            path: Path to the deleted file (supports syft:// URLs)
            
        Returns:
            Dict mapping contact emails to success status
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


__all__ = ['MessageSender']