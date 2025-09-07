"""Gmail transport layer implementation"""

from typing import Any, Dict, List
from ..transport_base import BaseTransportLayer
from ...environment import Environment


class GmailTransport(BaseTransportLayer):
    """Gmail API transport layer"""
    
    # STATIC Attributes
    is_keystore = True  # Gmail is trusted for storing keys
    is_notification_layer = True  # Users check email regularly
    is_html_compatible = True  # Email supports HTML
    is_reply_compatible = True  # Email has native reply support
    guest_submit = False  # Requires Gmail account
    guest_read_file = False  # Requires authentication
    guest_read_folder = False  # Requires authentication
    
    @property
    def api_is_active_by_default(self) -> bool:
        """Gmail API requires manual activation"""
        return False
        
    @property
    def login_complexity(self) -> int:
        """Gmail requires OAuth2 flow"""
        if self._cached_credentials:
            return 0  # Already logged in
            
        # Gmail always requires OAuth2 flow
        return 2  # Multi-step OAuth process
        
    def authenticate(self) -> Dict[str, Any]:
        """Authenticate with Gmail API using OAuth2"""
        # TODO: Implement Gmail OAuth2 authentication
        raise NotImplementedError("Gmail authentication not yet implemented")
        
    def send(self, recipient: str, data: Any) -> bool:
        """Send email via Gmail API"""
        # TODO: Implement Gmail send
        raise NotImplementedError("Gmail send not yet implemented")
        
    def receive(self) -> List[Dict[str, Any]]:
        """Receive emails from Gmail inbox"""
        # TODO: Implement Gmail receive
        raise NotImplementedError("Gmail receive not yet implemented")