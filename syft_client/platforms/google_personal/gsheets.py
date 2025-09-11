"""Google Sheets transport layer implementation"""

from typing import Any, Dict, List
from ..transport_base import BaseTransportLayer
from ...environment import Environment


class GSheetsTransport(BaseTransportLayer):
    """Google Sheets API transport layer"""
    
    # STATIC Attributes
    is_keystore = False  # Sheets not ideal for storing keys
    is_notification_layer = False  # Users don't check sheets regularly
    is_html_compatible = False  # Sheets format, not HTML
    is_reply_compatible = False  # No native reply mechanism
    guest_submit = False  # Requires authentication to write
    guest_read_file = True  # Can make sheets public
    guest_read_folder = False  # N/A for sheets
    
    @property
    def api_is_active_by_default(self) -> bool:
        """Sheets API requires manual activation"""
        return False
        
    @property
    def login_complexity(self) -> int:
        """Sheets requires same auth as GDrive"""
        if self._cached_credentials:
            return 0  # Already logged in
            
        if self.environment == Environment.COLAB:
            return 1  # Can reuse GDrive auth in Colab
        else:
            return 2  # OAuth2 flow required
            
        
    def send(self, recipient: str, data: Any) -> bool:
        """Write data to a Google Sheet and share"""
        # TODO: Implement writing to sheets
        raise NotImplementedError("Google Sheets send not yet implemented")
        
    def receive(self) -> List[Dict[str, Any]]:
        """Read data from shared Google Sheets"""
        # TODO: Implement reading from shared sheets
        raise NotImplementedError("Google Sheets receive not yet implemented")