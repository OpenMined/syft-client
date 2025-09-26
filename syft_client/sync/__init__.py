"""
Sync and messaging functionality for syft_client
"""

from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..syft_client import SyftClient


class SyncManager:
    """Main sync coordinator that combines all sync functionality"""
    
    def __init__(self, client: 'SyftClient'):
        self.client = client
        self._contacts = None
        self._sender = None
        self._transport = None
        self._paths = None
    
    @property
    def contacts_manager(self):
        """Lazy load ContactManager"""
        if self._contacts is None:
            from .contacts import ContactManager
            self._contacts = ContactManager(self.client)
        return self._contacts
    
    @property
    def sender(self):
        """Lazy load MessageSender"""
        if self._sender is None:
            from .sender import MessageSender
            self._sender = MessageSender(self.client)
        return self._sender
    
    @property
    def transport(self):
        """Lazy load TransportSelector"""
        if self._transport is None:
            from .transport import TransportSelector
            self._transport = TransportSelector(self.client)
        return self._transport
    
    @property
    def paths(self):
        """Lazy load PathResolver"""
        if self._paths is None:
            from ..core.paths import PathResolver
            self._paths = PathResolver(self.client)
        return self._paths
    
    # Contact management
    @property
    def contacts(self) -> List[str]:
        """List all contacts"""
        return self.contacts_manager.contacts
    
    def add_contact(self, email: str) -> bool:
        """Add a contact for bidirectional communication"""
        return self.contacts_manager.add_contact(email)
    
    def remove_contact(self, email: str) -> bool:
        """Remove a contact"""
        return self.contacts_manager.remove_contact(email)
    
    # Sending functionality
    def send_to_contacts(self, path: str) -> Dict[str, bool]:
        """Send file/folder to all contacts"""
        return self.sender.send_to_contacts(path)
    
    def send_to(self, path: str, recipient: str) -> bool:
        """Send file/folder to specific recipient"""
        return self.sender.send_to(path, recipient)
    
    # Path resolution
    def resolve_path(self, path: str) -> str:
        """Resolve syft:// URLs to full paths"""
        return self.paths.resolve_syft_path(path)


__all__ = ['SyncManager']