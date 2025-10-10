"""ProtonMail platform client implementation"""

from typing import Any, Dict, List

from ..base import BasePlatformClient


class ProtonClient(BasePlatformClient):
    """Client for ProtonMail platform"""

    def __init__(self, email: str):
        super().__init__(email)
        self.platform = "proton"

    @property
    def login_complexity(self) -> int:
        """
        Return the complexity of the login process.
        Proton: -1 (not implemented yet)
        """
        return -1

    def get_transport_layers(self) -> List[str]:
        """Get list of available transport layers for this platform"""
        return ["ProtonMailTransport", "ProtonDriveTransport"]
