"""
Base transport interface for sending messages
"""

from abc import ABC, abstractmethod
from typing import Optional


class BaseTransport(ABC):
    """Base interface that all transports should implement"""

    @abstractmethod
    def send_to(
        self, archive_path: str, recipient: str, message_id: Optional[str] = None
    ) -> bool:
        """
        Send a pre-prepared archive to a recipient

        Args:
            archive_path: Path to the prepared .syftmsg archive
            recipient: Email address of the recipient
            message_id: Optional message ID for tracking

        Returns:
            True if send was successful, False otherwise
        """
        pass

    @abstractmethod
    def add_peer(self, email: str, verbose: bool = True) -> bool:
        """
        Add a contact for this transport

        Args:
            email: Email address of the peer to add
            verbose: Whether to print status messages

        Returns:
            True if contact was successfully added, False otherwise
        """
        pass

    @abstractmethod
    def remove_peer(self, email: str, verbose: bool = True) -> bool:
        """
        Remove a peer from this transport

        Args:
            email: Email address of the peer to remove
            verbose: Whether to print status messages

        Returns:
            True if contact was successfully removed, False otherwise
        """
        pass

    @abstractmethod
    def list_peers(self) -> list[str]:
        """
        List all contacts for this transport

        Returns:
            List of email addresses that are contacts on this transport
        """
        pass

    @property
    @abstractmethod
    def transport_name(self) -> str:
        """Get the name of this transport (e.g., 'gdrive_files', 'gsheets')"""
        pass

    def is_available(self) -> bool:
        """Check if this transport is currently available and authenticated"""
        return True

    def check_inbox(
        self,
        sender_email: str,
        download_dir: Optional[str] = None,
        verbose: bool = True,
    ) -> list[dict]:
        """
        Check for incoming messages from a specific sender

        Args:
            sender_email: Email of the sender to check messages from
            download_dir: Directory to download messages to (defaults to SyftBox directory)
            verbose: Whether to print progress

        Returns:
            List of message info dicts with keys: id, timestamp, size, metadata, extracted_to
        """
        # Default implementation - transports should override if they support inbox
        return []

    def get_peer_resource(self, email: str) -> Optional[dict]:
        """
        Get the resource (folder, sheet, etc.) associated with a contact

        This is used by the contact.platforms interface to access transport-specific
        resources for a contact.

        Args:
            email: Email address of the contact

        Returns:
            Dict with resource info that should include at minimum:
            - 'transport': Name of this transport
            - 'available': Whether the resource is available
            And optionally:
            - 'name': Display name of the resource
            - 'url': URL to access the resource
            - 'type': Type of resource ('folder', 'sheet', 'email', etc.)
            - Any other transport-specific fields

            Returns None if no resource exists for this contact.
        """
        # Default implementation - transports should override this
        return {
            "transport": self.transport_name,
            "available": self.is_available(),
            "email": email,
        }
