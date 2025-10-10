"""Outlook transport layer implementation"""

from typing import Any, Dict, List

from ...environment import Environment
from ..transport_base import BaseTransportLayer


class OutlookTransport(BaseTransportLayer):
    """Outlook/Office 365 email transport layer"""

    # STATIC Attributes
    is_keystore = True  # Outlook is trusted for storing keys
    is_notification_layer = True  # Users check email regularly
    is_html_compatible = True  # Email supports HTML
    is_reply_compatible = True  # Email has native reply support
    guest_submit = False  # Requires Microsoft account
    guest_read_file = False  # Requires authentication
    guest_read_folder = False  # Requires authentication

    @property
    def api_is_active_by_default(self) -> bool:
        """Outlook API requires app registration"""
        return False

    @property
    def login_complexity(self) -> int:
        """Outlook requires OAuth2 + app registration"""
        if self._cached_credentials:
            return 0  # Already logged in

        # Outlook requires app registration + OAuth2
        return 3  # Complex multi-step process

    def authenticate(self) -> Dict[str, Any]:
        """Authenticate with Microsoft Graph API for Outlook"""
        # TODO: Implement Microsoft OAuth2 authentication
        raise NotImplementedError("Outlook authentication not yet implemented")

    def send(self, recipient: str, data: Any) -> bool:
        """Send email via Outlook/Graph API"""
        # TODO: Implement Outlook send
        raise NotImplementedError("Outlook send not yet implemented")

    def receive(self) -> List[Dict[str, Any]]:
        """Receive emails from Outlook inbox"""
        # TODO: Implement Outlook receive
        raise NotImplementedError("Outlook receive not yet implemented")
