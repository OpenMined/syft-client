"""Mail.com platform client implementation"""

from typing import Any, Dict, List

from ..base import BasePlatformClient


class MailcomClient(BasePlatformClient):
    """Client for Mail.com platform"""

    def __init__(self, email: str):
        super().__init__(email)
        self.platform = "mailcom"

    @property
    def login_complexity(self) -> int:
        """
        Return the complexity of the login process.
        Mail.com: -1 (not implemented yet)
        """
        return -1

    def get_transport_layers(self) -> List[Any]:
        """Get the transport layers for Mail.com"""
        # TODO: Implement Mail.com transport layers
        return []
