"""Dropbox Files transport layer implementation"""

from typing import Any, Dict, List

from ...environment import Environment
from ..transport_base import BaseTransportLayer


class DropboxFilesTransport(BaseTransportLayer):
    """Dropbox file storage transport layer"""

    # STATIC Attributes
    is_keystore = True  # Dropbox can store auth keys
    is_notification_layer = False  # Users don't regularly check Dropbox
    is_html_compatible = False  # File storage, not rendering
    is_reply_compatible = False  # No native reply mechanism
    guest_submit = False  # Requires Dropbox account
    guest_read_file = True  # Can share files publicly
    guest_read_folder = True  # Can share folders publicly

    @property
    def api_is_active_by_default(self) -> bool:
        """Dropbox API requires app creation"""
        return False

    @property
    def login_complexity(self) -> int:
        """Dropbox requires OAuth2 + app creation"""
        if self._cached_credentials:
            return 0  # Already set up

        # Dropbox requires creating an app + OAuth2
        return 3  # Multi-step process

    def authenticate(self) -> Dict[str, Any]:
        """Set up Dropbox API access"""
        # TODO: Create Dropbox app
        # TODO: Implement Dropbox OAuth2
        raise NotImplementedError("Dropbox authentication not yet implemented")

    def send(self, recipient: str, data: Any) -> bool:
        """Upload file to Dropbox and share with recipient"""
        # TODO: Implement Dropbox upload and sharing
        raise NotImplementedError("Dropbox send not yet implemented")

    def receive(self) -> List[Dict[str, Any]]:
        """Check for new shared files in Dropbox"""
        # TODO: Implement checking for shared files
        raise NotImplementedError("Dropbox receive not yet implemented")
