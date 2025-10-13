"""Fastmail platform client implementation"""

from typing import Any, Dict, List

from ..base import BasePlatformClient


class FastmailClient(BasePlatformClient):
    """Client for Fastmail platform"""

    def __init__(self, email: str):
        super().__init__(email)
        self.platform = "fastmail"

    @property
    def login_complexity(self) -> int:
        """
        Return the complexity of the login process.
        Fastmail: -1 (not implemented yet)
        """
        return -1

    def get_transport_layers(self) -> List[Any]:
        """Get the transport layers for Fastmail"""
        # TODO: Implement Fastmail transport layers
        return []
