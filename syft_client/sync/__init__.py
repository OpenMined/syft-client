"""
Sync and messaging functionality for syft_client
"""

from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from ..syft_client import SyftClient


class SyncManager:
    """Main sync coordinator that combines all sync functionality"""

    def __init__(self, client: "SyftClient"):
        self.client = client
        self._peers = None
        self._sender = None
        self._paths = None
        self._services = None

    @property
    def peers_manager(self):
        """Lazy load PeerManager"""
        if self._peers is None:
            from .peers import PeerManager

            self._peers = PeerManager(self.client)
        return self._peers

    @property
    def sender(self):
        """Lazy load MessageSender"""
        if self._sender is None:
            from .sender import MessageSender

            self._sender = MessageSender(self.client)
        return self._sender

    @property
    def paths(self):
        """Lazy load PathResolver"""
        if self._paths is None:
            from ..core.paths import PathResolver

            self._paths = PathResolver(self.client)
        return self._paths

    @property
    def services(self):
        """Lazy load SyncServiceManager"""
        if self._services is None:
            from .sync_services import SyncServiceManager

            self._services = SyncServiceManager(self.client)
        return self._services

    # Peer management
    @property
    def peers(self) -> List[str]:
        """List all peers"""
        return self.peers_manager.peers

    def add_peer(self, email: str) -> bool:
        """Add a peer for bidirectional communication"""
        return self.peers_manager.add_peer(email)

    def remove_peer(self, email: str) -> bool:
        """Remove a peer"""
        return self.peers_manager.remove_peer(email)

    def delete_peer(self, email: str) -> bool:
        """Delete a peer completely, removing all transport objects and local caches"""
        return self.peers_manager.delete_peer(email)

    # Sending functionality
    def send_to_peers(self, path: str) -> Dict[str, bool]:
        """Send file/folder to all peers"""
        return self.sender.send_to_peers(path)

    def send_to(
        self,
        path: str,
        recipient: str,
        requested_latency_ms: Optional[int] = None,
        priority: str = "normal",
        transport: Optional[str] = None,
    ) -> bool:
        """Send file/folder to specific recipient"""
        return self.sender.send_to(
            path, recipient, requested_latency_ms, priority, transport
        )

    def send_deletion_to_peers(self, path: str) -> Dict[str, bool]:
        """Send deletion message to all peers"""
        return self.sender.send_deletion_to_peers(path)

    def send_deletion(self, path: str, recipient: str) -> bool:
        """Send deletion message to specific recipient"""
        return self.sender.send_deletion(path, recipient)

    def send_move_to_peers(self, source_path: str, dest_path: str) -> Dict[str, bool]:
        """Send move message to all peers"""
        return self.sender.send_move_to_peers(source_path, dest_path)

    def send_move(self, source_path: str, dest_path: str, recipient: str) -> bool:
        """Send move message to specific recipient"""
        return self.sender.send_move(source_path, dest_path, recipient)

    # Path resolution
    def resolve_path(self, path: str) -> str:
        """Resolve syft:// URLs to full paths"""
        return self.paths.resolve_syft_path(path)

    # Message preparation (mainly for testing)
    def prepare_message(
        self, path: str, recipient: str, temp_dir: str, sync_from_anywhere: bool = False
    ):
        """
        Prepare a message for sending (exposed for testing)

        Args:
            path: Path to file/folder
            recipient: Recipient email
            temp_dir: Temporary directory for message
            sync_from_anywhere: Allow files from outside SyftBox

        Returns:
            Tuple of (message_id, archive_path, archive_size) or None
        """
        return self.sender.prepare_message(
            path, recipient, temp_dir, sync_from_anywhere
        )


__all__ = ["SyncManager"]
