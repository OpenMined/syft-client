from google.oauth2.credentials import Credentials
from abc import ABC


class BaseStorage(ABC):
    """Base class for all storage backends."""

    def load_client_secret(self) -> dict:
        """Load client secret."""
        raise NotImplementedError

    def save_client_secret(self, client_secret: dict):
        """Save client secret."""
        raise NotImplementedError

    def save_credentials(self, credentials: Credentials):
        """Save credentials."""
        raise NotImplementedError

    def load_credentials(self) -> Credentials:
        """Load credentials."""
        raise NotImplementedError
