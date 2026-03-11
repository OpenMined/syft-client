"""Backward compatibility alias — use PeerStore from syft_client.sync.peers.peer_store."""

from syft_client.sync.peers.peer_store import PeerStore as LocalPeerKeyStore

__all__ = ["LocalPeerKeyStore"]
