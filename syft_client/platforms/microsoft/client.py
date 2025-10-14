"""Microsoft platform client implementation"""

from typing import Any, Dict, List

from ..base import BasePlatformClient


class MicrosoftClient(BasePlatformClient):
    """Client for Microsoft platform (Outlook, Hotmail, Office 365)"""

    def __init__(self, email: str):
        super().__init__(email)
        self.platform = "microsoft"

    @property
    def login_complexity(self) -> int:
        """
        Return the complexity of the login process.
        Microsoft: 3 (requires app registration + OAuth2 flow with consent screens)
        """
        return 3

    def authenticate(self) -> Dict[str, Any]:
        """Authenticate with Microsoft"""
        # TODO: Implement Microsoft OAuth2 authentication
        raise NotImplementedError("Microsoft authentication not yet implemented")

    def get_transport_layers(self) -> List[str]:
        """Get list of available transport layers for this platform"""
        return ["OutlookTransport", "OneDriveFilesTransport", "MSFormsTransport"]
