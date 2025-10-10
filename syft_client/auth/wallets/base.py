"""Base wallet interface for token storage"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseWallet(ABC):
    """Abstract base class for all wallet implementations"""

    def __init__(self, config: Dict[str, Any]):
        """Initialize with wallet-specific configuration"""
        self.config = config

    @abstractmethod
    def store_token(self, service: str, account: str, token_data: Dict) -> bool:
        """
        Store a token in the wallet.

        Args:
            service: Service name (e.g., 'google_personal')
            account: Account identifier (e.g., email)
            token_data: Token data to store

        Returns:
            True if successful, False otherwise
        """
        raise NotImplementedError

    @abstractmethod
    def retrieve_token(self, service: str, account: str) -> Optional[Dict]:
        """
        Retrieve a token from the wallet.

        Args:
            service: Service name
            account: Account identifier

        Returns:
            Token data if found, None otherwise
        """
        raise NotImplementedError

    @abstractmethod
    def delete_token(self, service: str, account: str) -> bool:
        """
        Delete a token from the wallet.

        Args:
            service: Service name
            account: Account identifier

        Returns:
            True if successful, False otherwise
        """
        raise NotImplementedError

    @abstractmethod
    def list_tokens(self, service: Optional[str] = None) -> List[str]:
        """
        List available tokens.

        Args:
            service: Optional service filter

        Returns:
            List of token identifiers (format: "service:account")
        """
        raise NotImplementedError

    def get_token_metadata(self, service: str, account: str) -> Optional[Dict]:
        """
        Retrieve token metadata without loading the token itself.
        Default implementation returns None. Subclasses can override.

        Args:
            service: Service name
            account: Account identifier

        Returns:
            Metadata dictionary if found, None otherwise
        """
        return None

    def update_token_metadata(
        self, service: str, account: str, metadata_updates: Dict
    ) -> bool:
        """
        Update token metadata without modifying the token itself.
        Default implementation returns False. Subclasses can override.

        Args:
            service: Service name
            account: Account identifier
            metadata_updates: Dictionary of metadata fields to update

        Returns:
            True if successful, False otherwise
        """
        return False

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test if wallet is accessible.

        Returns:
            True if wallet is accessible, False otherwise
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable wallet name"""
        raise NotImplementedError

    @property
    def requires_setup(self) -> bool:
        """Whether wallet needs initial configuration"""
        return False

    def setup_wizard(self) -> Dict[str, Any]:
        """Interactive setup for wallet configuration"""
        return {}
