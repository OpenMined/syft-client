"""Microsoft Forms transport layer implementation"""

from typing import Any, Dict, List

from ...environment import Environment
from ..transport_base import BaseTransportLayer


class MSFormsTransport(BaseTransportLayer):
    """Microsoft Forms transport layer"""

    # STATIC Attributes
    is_keystore = False  # Forms not for storing keys
    is_notification_layer = False  # Users don't check forms regularly
    is_html_compatible = True  # Forms render as HTML
    is_reply_compatible = False  # One-way submission only
    guest_submit = True  # Anonymous users can submit to public forms!
    guest_read_file = False  # Can't read form data without auth
    guest_read_folder = False  # N/A for forms

    @property
    def api_is_active_by_default(self) -> bool:
        """Forms API requires manual activation"""
        return False

    @property
    def login_complexity(self) -> int:
        """Forms setup complexity after platform auth"""
        if self._cached_credentials:
            return 0  # Already set up

        # Assumes platform (Microsoft) is already authenticated
        # But still needs Forms-specific setup
        return 2  # Need to enable API and create forms

    def authenticate(self) -> Dict[str, Any]:
        """Set up Microsoft Forms (assumes platform auth exists)"""
        # TODO: Check for existing platform auth
        # TODO: Enable Forms API if needed
        # TODO: Create initial form resources
        raise NotImplementedError("Microsoft Forms setup not yet implemented")

    def send(self, recipient: str, data: Any) -> bool:
        """Submit data to a Microsoft Form"""
        # TODO: Implement form submission
        raise NotImplementedError("Microsoft Forms send not yet implemented")

    def receive(self) -> List[Dict[str, Any]]:
        """Read form responses"""
        # TODO: Implement reading form responses
        raise NotImplementedError("Microsoft Forms receive not yet implemented")
