"""
Contact management for sync functionality
"""

import time
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..syft_client import SyftClient


class ContactManager:
    """Manages contacts for bidirectional communication"""
    
    def __init__(self, client: 'SyftClient'):
        self.client = client
        self._contacts_cache: Optional[List[str]] = None
        self._contacts_cache_time: Optional[float] = None
        self._cache_ttl = 3600  # 1 hour cache
    
    @property
    def contacts(self) -> List[str]:
        """
        List all contacts (people you have set up outgoing channels to)
        
        Returns:
            List of email addresses you've added as contacts
        """
        # Check if we have a valid platform with sync capability
        platform = self._get_sync_platform()
        if not platform:
            return []
        
        # Check if cache is valid
        current_time = time.time()
        if (self._contacts_cache is not None and 
            self._contacts_cache_time is not None and 
            current_time - self._contacts_cache_time < self._cache_ttl):
            return self._contacts_cache
        
        # Get contacts from the platform
        contacts_list = self._get_contacts_from_platform(platform)
        
        # Update cache
        self._contacts_cache = contacts_list
        self._contacts_cache_time = current_time
        
        return contacts_list
    
    def add_contact(self, email: str) -> bool:
        """
        Add a contact for bidirectional communication
        
        Args:
            email: Email address of the contact to add
            
        Returns:
            True if successful
        """
        if not email or '@' not in email:
            print(f"❌ Invalid email address: {email}")
            return False
        
        # Check if trying to add self
        if email.lower() == self.client.email.lower():
            print("❌ Cannot add yourself as a contact")
            return False
        
        # Get platform with sync capability
        platform = self._get_sync_platform()
        if not platform:
            print("❌ No platform available with sync capabilities")
            return False
        
        # Use platform-specific method to add contact
        try:
            # Get the gdrive_files transport from the platform
            if hasattr(platform, 'gdrive_files') and hasattr(platform.gdrive_files, 'add_friend'):
                result = platform.gdrive_files.add_friend(email, verbose=True)
            else:
                print(f"❌ Platform {platform.platform} does not support adding contacts")
                return False
            
            # Invalidate cache
            if result:
                self._invalidate_contacts_cache()
            
            return result
            
        except Exception as e:
            print(f"❌ Error adding contact: {e}")
            return False
    
    def remove_contact(self, email: str) -> bool:
        """
        Remove a contact
        
        Args:
            email: Email address of the contact to remove
            
        Returns:
            True if successful
        """
        # Get platform with sync capability
        platform = self._get_sync_platform()
        if not platform:
            print("❌ No platform available with sync capabilities")
            return False
        
        # Check if contact exists
        if email not in self.contacts:
            print(f"❌ {email} is not in your contacts list")
            return False
        
        # Use platform-specific method to remove contact
        try:
            if hasattr(platform, 'gdrive_files') and hasattr(platform.gdrive_files, 'remove_friend'):
                result = platform.gdrive_files.remove_friend(email)
            else:
                print(f"❌ Platform {platform.platform} does not support removing contacts")
                return False
            
            # Invalidate cache
            if result:
                self._invalidate_contacts_cache()
            
            return result
            
        except Exception as e:
            print(f"❌ Error removing contact: {e}")
            return False
    
    def _invalidate_contacts_cache(self):
        """Invalidate the contacts cache to force a refresh on next access"""
        self._contacts_cache = None
        self._contacts_cache_time = None
    
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
    
    def _get_contacts_from_platform(self, platform) -> List[str]:
        """Get contacts list from a specific platform"""
        try:
            # Get contacts from the gdrive_files transport
            if hasattr(platform, 'gdrive_files'):
                gdrive = platform.gdrive_files
                if hasattr(gdrive, 'friends'):
                    # Transport uses 'friends' property (will be mapped to contacts)
                    return gdrive.friends
                elif hasattr(gdrive, 'contacts'):
                    # Transport already uses 'contacts' property
                    return gdrive.contacts
            return []
        except Exception as e:
            print(f"⚠️  Error getting contacts: {e}")
            return []


__all__ = ['ContactManager']