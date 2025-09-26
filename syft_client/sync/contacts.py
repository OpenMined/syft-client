"""
Contact management for sync functionality
"""

import time
import json
from pathlib import Path
from typing import List, Optional, Dict, TYPE_CHECKING
from datetime import datetime

from .contact_model import Contact, TransportEndpoint
from .discovery import ContactDiscovery

if TYPE_CHECKING:
    from ..syft_client import SyftClient


class ContactManager:
    """Manages contacts for bidirectional communication"""
    
    def __init__(self, client: 'SyftClient'):
        self.client = client
        self._contacts_cache: Optional[Dict[str, Contact]] = None
        self._contacts_cache_time: Optional[float] = None
        self._cache_ttl = 3600  # 1 hour cache
        self._contacts_dir = None
        self._discovery = ContactDiscovery(client)
    
    @property
    def contacts(self) -> List[str]:
        """
        List all contacts (people you have set up outgoing channels to)
        
        Returns:
            List of email addresses you've added as contacts
        """
        contacts_dict = self.get_contacts_dict()
        return list(contacts_dict.keys())
    
    def get_contacts_dict(self) -> Dict[str, Contact]:
        """
        Get all contacts as a dictionary mapping emails to Contact objects
        
        Returns:
            Dict of email -> Contact objects
        """
        # Check if we have a valid platform with sync capability
        platform = self._get_sync_platform()
        if not platform:
            return {}
        
        # Check if cache is valid
        current_time = time.time()
        if (self._contacts_cache is not None and 
            self._contacts_cache_time is not None and 
            current_time - self._contacts_cache_time < self._cache_ttl):
            return self._contacts_cache
        
        # Get contacts from the platform
        contacts_list = self._get_contacts_from_platform(platform)
        
        # Load or create Contact objects
        contacts_dict = {}
        for email in contacts_list:
            contact = self._load_or_create_contact(email)
            
            # Re-verify which platforms actually have this contact
            platforms_with_contact = {}
            transports_with_contact = {}
            
            for platform_name, plat in self.client._platforms.items():
                # Check each transport on this platform
                for attr_name in dir(plat):
                    if not attr_name.startswith('_'):
                        transport = getattr(plat, attr_name, None)
                        if transport and hasattr(transport, 'list_contacts'):
                            try:
                                transport_contacts = transport.list_contacts()
                                if email in transport_contacts:
                                    platforms_with_contact[platform_name] = plat
                                    if platform_name not in transports_with_contact:
                                        transports_with_contact[platform_name] = []
                                    transports_with_contact[platform_name].append(attr_name)
                            except:
                                pass
            
            # Update contact based on what we found
            if platforms_with_contact:
                # Determine correct platform
                # If contact already has a platform that's in the list, keep it
                # This prevents switching between google_personal and google_org unnecessarily
                correct_platform = None
                if contact.platform and contact.platform in platforms_with_contact:
                    correct_platform = contact.platform
                else:
                    # Otherwise, prefer the platform where we found more transports
                    max_transports = 0
                    for plat_name, transport_list in transports_with_contact.items():
                        if len(transport_list) > max_transports:
                            max_transports = len(transport_list)
                            correct_platform = plat_name
                    
                    # If tied, prefer google_personal over google_org
                    if not correct_platform:
                        if 'google_personal' in platforms_with_contact:
                            correct_platform = 'google_personal'
                        elif 'google_org' in platforms_with_contact:
                            correct_platform = 'google_org'
                        else:
                            correct_platform = list(platforms_with_contact.keys())[0]
                
                # Update contact if platform changed or no transports
                if contact.platform != correct_platform or not contact.available_transports:
                    contact.platform = correct_platform
                    contact.available_transports.clear()
                    
                    # Add and verify all transports found on the correct platform
                    for transport_name in transports_with_contact.get(correct_platform, []):
                        contact.add_transport(transport_name)
                        contact.verify_transport(transport_name)
                    
                    # For Google platforms, always add gmail if the platform has it
                    if correct_platform in ['google_personal', 'google_org']:
                        platform_obj = platforms_with_contact.get(correct_platform)
                        if platform_obj and hasattr(platform_obj, 'gmail'):
                            gmail_transport = getattr(platform_obj, 'gmail', None)
                            if gmail_transport and hasattr(gmail_transport, 'is_setup') and gmail_transport.is_setup():
                                if 'gmail' not in contact.available_transports:
                                    contact.add_transport('gmail')
                                contact.verify_transport('gmail')
                    
                    contact.capabilities_last_updated = datetime.now()
                    self._save_contact(contact)
                    
                # Also verify any unverified transports
                elif contact.available_transports:
                    updated = False
                    for transport_name in transports_with_contact.get(contact.platform, []):
                        if transport_name in contact.available_transports and not contact.available_transports[transport_name].verified:
                            contact.verify_transport(transport_name)
                            updated = True
                    
                    # For Google platforms, ensure gmail is included and verified
                    if contact.platform in ['google_personal', 'google_org']:
                        platform_obj = platforms_with_contact.get(contact.platform)
                        if platform_obj and hasattr(platform_obj, 'gmail'):
                            gmail_transport = getattr(platform_obj, 'gmail', None)
                            if gmail_transport and hasattr(gmail_transport, 'is_setup') and gmail_transport.is_setup():
                                if 'gmail' not in contact.available_transports:
                                    contact.add_transport('gmail')
                                    updated = True
                                if not contact.available_transports['gmail'].verified:
                                    contact.verify_transport('gmail')
                                    updated = True
                    
                    if updated:
                        self._save_contact(contact)
            
            # If we didn't find the contact in any transports but it was loaded from disk,
            # keep it but note it needs re-discovery
            if not platforms_with_contact and not contact.available_transports:
                self._discover_contact_capabilities(contact, platform)
            
            contacts_dict[email] = contact
        
        # Update cache
        self._contacts_cache = contacts_dict
        self._contacts_cache_time = current_time
        
        return contacts_dict
    
    def get_contact(self, email: str) -> Optional[Contact]:
        """
        Get a specific contact by email
        
        Args:
            email: Email address of the contact
            
        Returns:
            Contact object or None if not found
        """
        contacts_dict = self.get_contacts_dict()
        return contacts_dict.get(email)
    
    def add_contact(self, email: str) -> bool:
        """
        Add a contact for bidirectional communication
        
        This will attempt to add the contact on ALL available transports
        to maximize connectivity options.
        
        Args:
            email: Email address of the contact to add
            
        Returns:
            True if contact was added on at least one transport
        """
        if not email or '@' not in email:
            print(f"❌ Invalid email address: {email}")
            return False
        
        # Check if trying to add self
        if email.lower() == self.client.email.lower():
            print("❌ Cannot add yourself as a contact")
            return False
        
        # Try to add contact on all available transports
        successful_transports = []
        failed_transports = []
        
        # Iterate through all platforms and their transports
        for platform_name, platform in self.client._platforms.items():
            # Get all transport attributes from the platform
            for attr_name in dir(platform):
                if not attr_name.startswith('_'):
                    transport = getattr(platform, attr_name, None)
                    
                    # Check if this is a transport with add_contact method
                    if transport and hasattr(transport, 'add_contact'):
                        try:
                            if self.client.verbose:
                                print(f"🔄 Adding {email} on {platform_name}.{attr_name}...")
                            
                            # Call add_contact on the transport
                            result = transport.add_contact(email, verbose=False)
                            
                            if result:
                                successful_transports.append(f"{platform_name}.{attr_name}")
                                if self.client.verbose:
                                    print(f"   ✅ Added on {platform_name}.{attr_name}")
                            else:
                                failed_transports.append(f"{platform_name}.{attr_name}")
                                if self.client.verbose:
                                    print(f"   ❌ Failed on {platform_name}.{attr_name}")
                                    
                        except Exception as e:
                            failed_transports.append(f"{platform_name}.{attr_name}")
                            if self.client.verbose:
                                print(f"   ❌ Error on {platform_name}.{attr_name}: {e}")
        
        # Summary
        if successful_transports:
            if self.client.verbose:
                print(f"\n✅ Contact {email} added successfully on {len(successful_transports)} transport(s)")
                for transport in successful_transports:
                    print(f"   • {transport}")
            
            # Invalidate cache and force rediscovery
            self._invalidate_contacts_cache()
            
            # Create or update contact object with discovered transports
            contact = self._load_or_create_contact(email)
            
            # Set platform based on successful transports
            platforms_used = set()
            for transport_path in successful_transports:
                platform_name, transport_name = transport_path.split('.')
                platforms_used.add(platform_name)
                contact.add_transport(transport_name)
                contact.verify_transport(transport_name)
            
            # Set the platform if we have a clear winner
            if len(platforms_used) == 1:
                contact.platform = list(platforms_used)[0]
            elif 'google_personal' in platforms_used:
                contact.platform = 'google_personal'  # Prefer personal
            elif 'google_org' in platforms_used:
                contact.platform = 'google_org'
            
            self._save_contact(contact)
            
            return True
        else:
            print(f"❌ Failed to add contact {email} on any transport")
            return False
    
    def remove_contact(self, email: str) -> bool:
        """
        Remove a contact from all transports
        
        Args:
            email: Email address of the contact to remove
            
        Returns:
            True if contact was removed from at least one transport
        """
        # Check if contact exists
        if email not in self.contacts:
            print(f"❌ {email} is not in your contacts list")
            return False
        
        # Try to remove contact from all transports
        successful_removals = []
        failed_removals = []
        
        # Iterate through all platforms and their transports
        for platform_name, platform in self.client._platforms.items():
            # Get all transport attributes from the platform
            for attr_name in dir(platform):
                if not attr_name.startswith('_'):
                    transport = getattr(platform, attr_name, None)
                    
                    # Check if this is a transport with remove_contact method
                    if transport and hasattr(transport, 'remove_contact'):
                        try:
                            if self.client.verbose:
                                print(f"🔄 Removing {email} from {platform_name}.{attr_name}...")
                            
                            # Call remove_contact on the transport
                            result = transport.remove_contact(email, verbose=False)
                            
                            if result:
                                successful_removals.append(f"{platform_name}.{attr_name}")
                                if self.client.verbose:
                                    print(f"   ✅ Removed from {platform_name}.{attr_name}")
                            else:
                                failed_removals.append(f"{platform_name}.{attr_name}")
                                if self.client.verbose:
                                    print(f"   ⚠️  Not found on {platform_name}.{attr_name}")
                                    
                        except Exception as e:
                            failed_removals.append(f"{platform_name}.{attr_name}")
                            if self.client.verbose:
                                print(f"   ❌ Error on {platform_name}.{attr_name}: {e}")
        
        # Summary and cleanup
        if successful_removals:
            if self.client.verbose:
                print(f"\n✅ Contact {email} removed from {len(successful_removals)} transport(s)")
            
            # Remove contact file
            try:
                contacts_dir = self._get_contacts_directory()
                file_name = f"{email.replace('@', '_at_').replace('.', '_')}.json"
                file_path = contacts_dir / file_name
                if file_path.exists():
                    file_path.unlink()
            except:
                pass
            
            # Invalidate cache
            self._invalidate_contacts_cache()
            return True
        else:
            print(f"⚠️  {email} was not found on any transport")
            return False
    
    def _invalidate_contacts_cache(self):
        """Invalidate the contacts cache to force a refresh on next access"""
        self._contacts_cache = None
        self._contacts_cache_time = None
    
    def clear_all_caches(self, verbose: bool = True) -> None:
        """
        Clear all contact caches from disk and memory, forcing re-detection from online sources
        
        This will:
        1. Clear in-memory contacts cache
        2. Delete all saved contact JSON files
        3. Delete all discovery cache files
        4. Force fresh discovery on next access
        
        Args:
            verbose: If True, print detailed progress. If False, operate silently.
        """
        if verbose:
            print("🗑️  Clearing all contact caches...")
        
        # Clear in-memory cache
        self._invalidate_contacts_cache()
        
        files_cleared = 0
        
        # Clear contact JSON files
        try:
            contacts_dir = self._get_contacts_directory()
            if contacts_dir.exists():
                for file_path in contacts_dir.glob("*.json"):
                    try:
                        file_path.unlink()
                        files_cleared += 1
                        if verbose:
                            print(f"   ✓ Deleted contact file: {file_path.name}")
                    except Exception as e:
                        if verbose:
                            print(f"   ⚠️  Could not delete {file_path.name}: {e}")
        except Exception as e:
            if verbose:
                print(f"   ⚠️  Error clearing contact files: {e}")
        
        # Clear discovery cache
        try:
            discovery_cache_dir = self._discovery._get_discovery_cache_dir()
            if discovery_cache_dir.exists():
                for file_path in discovery_cache_dir.glob("*_discovery.json"):
                    try:
                        file_path.unlink()
                        files_cleared += 1
                        if verbose:
                            print(f"   ✓ Deleted discovery cache: {file_path.name}")
                    except Exception as e:
                        if verbose:
                            print(f"   ⚠️  Could not delete {file_path.name}: {e}")
        except Exception as e:
            if verbose:
                print(f"   ⚠️  Error clearing discovery cache: {e}")
        
        if verbose and files_cleared > 0:
            print("✅ All contact caches cleared. Next access will fetch fresh data from online sources.")
        elif verbose:
            print("ℹ️  No contact caches found to clear.")
    
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
        """Get contacts list from all transports across all platforms"""
        all_contacts = set()  # Use set to avoid duplicates
        
        # Iterate through all platforms
        for platform_name, platform in self.client._platforms.items():
            # Get all transport attributes from the platform
            for attr_name in dir(platform):
                if not attr_name.startswith('_'):
                    transport = getattr(platform, attr_name, None)
                    
                    # Check if this is a transport with list_contacts method
                    if transport and hasattr(transport, 'list_contacts'):
                        try:
                            contacts = transport.list_contacts()
                            all_contacts.update(contacts)
                        except:
                            pass
        
        return list(all_contacts)
    
    def _get_contacts_directory(self) -> Path:
        """Get the directory where contact data is stored"""
        if not self._contacts_dir:
            if hasattr(self.client, 'local_syftbox_dir'):
                self._contacts_dir = self.client.local_syftbox_dir / '.syft' / 'contacts'
            else:
                # Fallback to home directory
                self._contacts_dir = Path.home() / '.syft' / 'contacts'
            self._contacts_dir.mkdir(parents=True, exist_ok=True)
        return self._contacts_dir
    
    def _load_or_create_contact(self, email: str) -> Contact:
        """Load contact from disk or create new one"""
        contacts_dir = self._get_contacts_directory()
        file_name = f"{email.replace('@', '_at_').replace('.', '_')}.json"
        file_path = contacts_dir / file_name
        
        if file_path.exists():
            try:
                contact = Contact.load(file_path)
                
                # If contact has no platform but has transports, determine platform
                if not contact.platform and contact.available_transports:
                    # Determine platform from available transports
                    platforms_found = set()
                    
                    # Check which platforms have these transports
                    for platform_name, platform in self.client._platforms.items():
                        platform_has_transports = True
                        for transport_name in contact.available_transports:
                            if not hasattr(platform, transport_name):
                                platform_has_transports = False
                                break
                        if platform_has_transports:
                            platforms_found.add(platform_name)
                    
                    # Set platform if we can determine it
                    if len(platforms_found) == 1:
                        contact.platform = list(platforms_found)[0]
                    elif 'google_org' in platforms_found and email.endswith('@openmined.org'):
                        # For OpenMined emails, prefer google_org
                        contact.platform = 'google_org'
                    elif 'google_personal' in platforms_found:
                        contact.platform = 'google_personal'
                    elif 'google_org' in platforms_found:
                        contact.platform = 'google_org'
                    
                    # Save the updated contact
                    if contact.platform:
                        self._save_contact(contact)
                        
                return contact
            except Exception as e:
                if self.client.verbose:
                    print(f"⚠️  Could not load contact data for {email}: {e}")
        
        # Create new contact
        contact = Contact(email=email)
        
        # Check discovery cache
        cached_discovery = self._discovery.load_discovery_cache(email)
        if cached_discovery:
            # Apply cached discovery data
            contact.platform = cached_discovery.get('platform')
            for transport in cached_discovery.get('transports', []):
                contact.add_transport(transport)
            for transport in cached_discovery.get('verified_transports', []):
                contact.verify_transport(transport)
            if self.client.verbose:
                print(f"📋 Loaded cached capabilities for {email}")
        
        return contact
    
    def _save_contact(self, contact: Contact):
        """Save contact to disk"""
        contacts_dir = self._get_contacts_directory()
        try:
            contact.save(contacts_dir)
        except Exception as e:
            if self.client.verbose:
                print(f"⚠️  Could not save contact data for {contact.email}: {e}")
    
    def _discover_contact_capabilities(self, contact: Contact, platform):
        """Discover what transports a contact has available"""
        # Use the discovery system
        if self._discovery.discover_capabilities(contact):
            # Save discovered capabilities
            self._save_contact(contact)
            self._discovery.save_discovery_cache(contact)
    


__all__ = ['ContactManager']