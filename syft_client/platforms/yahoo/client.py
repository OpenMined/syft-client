"""Yahoo platform client implementation"""

from typing import Any, Dict, List

from ..base import BasePlatformClient


class YahooClient(BasePlatformClient):
    """Client for Yahoo platform (Yahoo Mail)"""

    def __init__(self, email: str):
        super().__init__(email)
        self.platform = "yahoo"

    @property
    def login_complexity(self) -> int:
        """
        Return the complexity of the login process.
        Yahoo: -1 (not implemented yet)
        """
        return -1

    def get_transport_layers(self) -> List[Any]:
        """Get the transport layers for Yahoo"""
        # TODO: Implement Yahoo transport layers
        return []
