"""Zoho platform client implementation"""

from typing import Any, Dict, List

from ..base import BasePlatformClient


class ZohoClient(BasePlatformClient):
    """Client for Zoho platform (Zoho Mail)"""

    def __init__(self, email: str):
        super().__init__(email)
        self.platform = "zoho"

    @property
    def login_complexity(self) -> int:
        """
        Return the complexity of the login process.
        Zoho: -1 (not implemented yet)
        """
        return -1

    def get_transport_layers(self) -> List[Any]:
        """Get the transport layers for Zoho (e.g., Zoho WorkDrive)"""
        # TODO: Implement Zoho transport layers
        return []
