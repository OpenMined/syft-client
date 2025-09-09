"""Dropbox platform client implementation"""

from typing import Any, Dict, List
from ..base import BasePlatformClient


class DropboxClient(BasePlatformClient):
    """Client for Dropbox platform"""
    
    def __init__(self, email: str):
        super().__init__(email)
        self.platform = "dropbox"
        
    def authenticate(self) -> Dict[str, Any]:
        """Authenticate with Dropbox using OAuth2"""
        # TODO: Implement Dropbox OAuth2 authentication
        raise NotImplementedError("Dropbox authentication not yet implemented")
        
    def get_transport_layers(self) -> List[str]:
        """Get list of available transport layers for this platform"""
        return ['DropboxFilesTransport']