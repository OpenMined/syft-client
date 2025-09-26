"""
Message sending functionality for sync
"""

import os
from typing import Dict, TYPE_CHECKING

from .transport import TransportSelector
from .contacts import ContactManager
from ..core.paths import PathResolver

if TYPE_CHECKING:
    from ..syft_client import SyftClient


class MessageSender:
    """Handles sending messages to contacts"""
    
    def __init__(self, client: 'SyftClient'):
        self.client = client
        self.transport = TransportSelector(client)
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
        
        # Use transport selector to send
        return self.transport.send_auto(path, recipient)
    
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
        if hasattr(platform, 'send_deletion'):
            return platform.send_deletion(path, recipient)
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
        if hasattr(platform, 'send_deletion_to_friends'):
            # Platform still uses 'friends' terminology internally
            return platform.send_deletion_to_friends(path)
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
                    return platform.gdrive_files
        
        return None


__all__ = ['MessageSender']