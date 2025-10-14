"""ProtonDrive transport layer implementation"""

from typing import Any, Dict, List

from ...environment import Environment
from ..transport_base import BaseTransportLayer


class ProtonDriveTransport(BaseTransportLayer):
    """ProtonDrive file storage transport layer"""

    # STATIC Attributes
    is_keystore = True  # ProtonDrive is highly secure
    is_notification_layer = False  # Users don't regularly check Drive
    is_html_compatible = False  # File storage, not rendering
    is_reply_compatible = False  # No native reply mechanism
    guest_submit = False  # Requires ProtonDrive account
    guest_read_file = True  # Can share files with links
    guest_read_folder = False  # Folder sharing limited

    @property
    def api_is_active_by_default(self) -> bool:
        """ProtonDrive API in beta"""
        return False

    @property
    def login_complexity(self) -> int:
        """ProtonDrive API setup complexity"""
        if self._cached_credentials:
            return 0  # Already set up

        # ProtonDrive API is still in development
        # Currently very limited
        return -1  # Not yet fully implemented

    def authenticate(self) -> Dict[str, Any]:
        """Set up ProtonDrive API access"""
        # TODO: ProtonDrive API is still in beta
        raise NotImplementedError("ProtonDrive API not yet available")

    def send(self, recipient: str, data: Any) -> bool:
        """Upload encrypted file to ProtonDrive and share"""
        # TODO: Implement ProtonDrive upload and sharing
        raise NotImplementedError("ProtonDrive send not yet implemented")

    def receive(self) -> List[Dict[str, Any]]:
        """Check for shared files in ProtonDrive"""
        # TODO: Implement checking for shared files
        raise NotImplementedError("ProtonDrive receive not yet implemented")
