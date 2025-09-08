"""Google Drive Files transport layer implementation"""

from typing import Any, Dict, List
from ..transport_base import BaseTransportLayer
from ...environment import Environment


class GDriveFilesTransport(BaseTransportLayer):
    """Google Drive Files API transport layer"""
    
    # STATIC Attributes
    is_keystore = True  # GDrive can store auth keys
    is_notification_layer = False  # Users don't regularly check Drive
    is_html_compatible = False  # File storage, not rendering
    is_reply_compatible = False  # No native reply mechanism
    guest_submit = False  # Requires Google account
    guest_read_file = True  # Can share files publicly
    guest_read_folder = True  # Can share folders publicly
    
    @property
    def api_is_active_by_default(self) -> bool:
        """GDrive API active by default in Colab"""
        return self.environment == Environment.COLAB
        
    @property
    def login_complexity(self) -> int:
        """Additional GDrive setup complexity (after Google auth)"""
        if self.api_is_active:
            return 0  # No additional setup
            
        # In Colab, Drive API is pre-enabled
        if self.environment == Environment.COLAB:
            return 0  # No additional setup needed
        else:
            # Need to enable Drive API in Console
            return 1  # One additional step
            
    def authenticate(self) -> Dict[str, Any]:
        """Authenticate with Google Drive API"""
        # TODO: Implement GDrive authentication
        # In Colab: from google.colab import auth; auth.authenticate_user()
        # Elsewhere: OAuth2 flow
        raise NotImplementedError("GDrive Files authentication not yet implemented")
        
    def send(self, recipient: str, data: Any) -> bool:
        """Upload file to GDrive and share with recipient"""
        # TODO: Implement GDrive file upload and sharing
        raise NotImplementedError("GDrive Files send not yet implemented")
        
    def receive(self) -> List[Dict[str, Any]]:
        """Check for new shared files in GDrive"""
        # TODO: Implement checking for newly shared files
        raise NotImplementedError("GDrive Files receive not yet implemented")