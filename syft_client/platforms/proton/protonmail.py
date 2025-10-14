"""ProtonMail transport layer implementation"""

from typing import Any, Dict, List

from ...environment import Environment
from ..transport_base import BaseTransportLayer


class ProtonMailTransport(BaseTransportLayer):
    """ProtonMail email transport layer"""

    # STATIC Attributes
    is_keystore = True  # ProtonMail is highly secure
    is_notification_layer = True  # Users check email regularly
    is_html_compatible = True  # Email supports HTML
    is_reply_compatible = True  # Email has native reply support
    guest_submit = False  # Requires ProtonMail account
    guest_read_file = False  # Requires authentication
    guest_read_folder = False  # Requires authentication

    @property
    def api_is_active_by_default(self) -> bool:
        """ProtonMail Bridge required for API access"""
        return False

    @property
    def login_complexity(self) -> int:
        """ProtonMail requires Bridge setup"""
        if self._cached_credentials:
            return 0  # Already set up

        # ProtonMail requires Bridge installation + API setup
        # This is complex due to E2E encryption
        return 4  # Very complex setup process

    def authenticate(self) -> Dict[str, Any]:
        """Set up ProtonMail Bridge and API access"""
        # TODO: Check for ProtonMail Bridge
        # TODO: Set up API access through Bridge
        # Note: ProtonMail uses end-to-end encryption
        raise NotImplementedError("ProtonMail authentication not yet implemented")

    def send(self, recipient: str, data: Any) -> bool:
        """Send encrypted email via ProtonMail"""
        # TODO: Implement ProtonMail send
        raise NotImplementedError("ProtonMail send not yet implemented")

    def receive(self) -> List[Dict[str, Any]]:
        """Receive encrypted emails from ProtonMail"""
        # TODO: Implement ProtonMail receive
        raise NotImplementedError("ProtonMail receive not yet implemented")
