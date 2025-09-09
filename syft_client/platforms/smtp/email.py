"""Generic SMTP email transport layer implementation"""

from typing import Any, Dict, List
from ..transport_base import BaseTransportLayer
from ...environment import Environment


class SMTPEmailTransport(BaseTransportLayer):
    """Generic SMTP/IMAP email transport layer"""
    
    # STATIC Attributes
    is_keystore = False  # Generic SMTP less trusted than major providers
    is_notification_layer = True  # Users check email regularly
    is_html_compatible = True  # Email supports HTML
    is_reply_compatible = True  # Email has native reply support
    guest_submit = False  # Requires email account
    guest_read_file = False  # Requires authentication
    guest_read_folder = False  # Requires authentication
    
    @property
    def api_is_active_by_default(self) -> bool:
        """SMTP is a standard protocol"""
        return True  # No API activation needed
        
    @property
    def login_complexity(self) -> int:
        """SMTP requires server details + credentials"""
        if self._cached_credentials:
            return 0  # Already set up
            
        # User needs to provide SMTP server details
        # (host, port, security settings, username, password)
        return 2  # Need server config + credentials
        
    def authenticate(self) -> Dict[str, Any]:
        """Set up SMTP/IMAP connection"""
        # TODO: Get SMTP server details from user
        # TODO: Test SMTP connection
        # TODO: Set up IMAP for receiving
        raise NotImplementedError("Generic SMTP setup not yet implemented")
        
    def send(self, recipient: str, data: Any) -> bool:
        """Send email via SMTP"""
        # TODO: Implement SMTP send
        raise NotImplementedError("SMTP send not yet implemented")
        
    def receive(self) -> List[Dict[str, Any]]:
        """Receive emails via IMAP"""
        # TODO: Implement IMAP receive
        raise NotImplementedError("IMAP receive not yet implemented")