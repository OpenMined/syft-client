"""OneDrive Files transport layer implementation"""

from typing import Any, Dict, List

from ...environment import Environment
from ..transport_base import BaseTransportLayer


class OneDriveFilesTransport(BaseTransportLayer):
    """OneDrive Files API transport layer"""

    # STATIC Attributes
    is_keystore = True  # OneDrive can store auth keys
    is_notification_layer = False  # Users don't regularly check OneDrive
    is_html_compatible = False  # File storage, not rendering
    is_reply_compatible = False  # No native reply mechanism
    guest_submit = False  # Requires Microsoft account
    guest_read_file = True  # Can share files publicly
    guest_read_folder = True  # Can share folders publicly

    @property
    def api_is_active_by_default(self) -> bool:
        """OneDrive API requires app registration"""
        return False

    @property
    def login_complexity(self) -> int:
        """OneDrive requires OAuth2 + app registration"""
        if self._cached_credentials:
            return 0  # Already logged in

        # OneDrive requires app registration + OAuth2
        return 3  # Complex multi-step process

    def authenticate(self) -> Dict[str, Any]:
        """Authenticate with Microsoft Graph API for OneDrive"""
        # TODO: Implement OneDrive authentication
        raise NotImplementedError("OneDrive Files authentication not yet implemented")

    def send(self, recipient: str, data: Any) -> bool:
        """Upload file to OneDrive and share with recipient"""
        # TODO: Implement OneDrive file upload and sharing
        raise NotImplementedError("OneDrive Files send not yet implemented")

    def receive(self) -> List[Dict[str, Any]]:
        """Check for new shared files in OneDrive"""
        # TODO: Implement checking for newly shared files
        raise NotImplementedError("OneDrive Files receive not yet implemented")
