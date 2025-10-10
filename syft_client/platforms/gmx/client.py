"""GMX platform client implementation"""

from typing import Any, Dict, List

from ..base import BasePlatformClient


class GMXClient(BasePlatformClient):
    """Client for GMX platform (GMX Mail)"""

    def __init__(self, email: str):
        super().__init__(email)
        self.platform = "gmx"

    @property
    def login_complexity(self) -> int:
        """
        Return the complexity of the login process.
        GMX: -1 (not implemented yet)
        """
        return -1

    def get_transport_layers(self) -> List[Any]:
        """Get the transport layers for GMX"""
        # TODO: Implement GMX transport layers
        return []
