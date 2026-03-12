"""PeerStore: merged peer list + encryption key management.

Holds peers, encryption keys, and a use_encryption flag.
Shared between PeerManager and all ConnectionRouter instances.
"""

import json
from pathlib import Path
from typing import List, Optional

import syft_crypto_python as syc
from pydantic import BaseModel, PrivateAttr

from syft_client.sync.peers.peer import Peer


class PeerStore(BaseModel):
    """Manages peers and encryption keys for E2E encryption."""

    model_config = {"arbitrary_types_allowed": True}

    email: str
    use_encryption: bool = False

    _private_keys: syc.SyftPrivateKeys | None = PrivateAttr(default=None)
    _peers: List[Peer] = PrivateAttr(default_factory=list)

    # ========== Peer list methods ==========

    @property
    def approved_peers(self) -> List[Peer]:
        return [p for p in self._peers if p.is_approved]

    @property
    def requested_by_peer_peers(self) -> List[Peer]:
        return [p for p in self._peers if p.is_requested_by_peer]

    @property
    def requested_by_me_peers(self) -> List[Peer]:
        return [p for p in self._peers if p.is_requested_by_me]

    @property
    def syncable_peers(self) -> List[Peer]:
        return [p for p in self._peers if p.is_requested_by_me or p.is_approved]

    def get_cached_peer(self, email: str) -> Optional[Peer]:
        for p in self._peers:
            if p.email == email:
                return p
        return None

    def encrypt_if_needed(self, email: str, data: bytes) -> bytes:
        if self.peer_uses_encryption(email):
            return self.encrypt(email, data)
        return data

    def decrypt_if_needed(self, email: str, data: bytes) -> bytes:
        if self.peer_uses_encryption(email):
            return self.decrypt(email, data)
        return data

    def peer_uses_encryption(self, email: str) -> bool:
        peer = self.get_cached_peer(email)
        return peer is not None and peer.use_encryption

    def set_peer(self, peer: Peer) -> None:
        peer.use_encryption = self.use_encryption
        for i, p in enumerate(self._peers):
            if p.email == peer.email:
                self._peers[i] = peer
                return
        self._peers.append(peer)

    def add_peer(self, peer: Peer) -> None:
        peer.use_encryption = self.use_encryption
        self._peers.append(peer)

    def set_peers(self, peers: List[Peer]) -> None:
        for p in peers:
            p.use_encryption = self.use_encryption
        self._peers = peers

    # ========== Ensure helpers ==========

    def _ensure_private_keys(self) -> syc.SyftPrivateKeys:
        if self._private_keys is None:
            raise ValueError("No private keys — call generate_keys() first")
        return self._private_keys

    def _ensure_peer(self, email: str) -> Peer:
        peer = self.get_cached_peer(email)
        if peer is None:
            raise ValueError(f"No cached peer for {email}")
        return peer

    def _ensure_peer_bundle(self, email: str) -> dict:
        peer = self._ensure_peer(email)
        if peer.public_encryption_bundle is None:
            raise ValueError(f"No public encryption bundle for {email}")
        return peer.public_encryption_bundle

    # ========== Crypto methods ==========

    def generate_keys(self) -> None:
        self._private_keys = syc.SyftRecoveryKey.generate().derive_keys()

    def has_my_keys(self) -> bool:
        return self._private_keys is not None

    @property
    def public_key(self) -> syc.SyftPublicKeyBundle:
        keys = self._ensure_private_keys()
        return keys.to_public_bundle()

    def get_public_bundle(self) -> dict:
        keys = self._ensure_private_keys()
        bundle = keys.to_public_bundle()
        did = f"did:syft:{self.email}"
        did_doc = bundle.to_did_document(did)
        did_doc["identity"] = self.email
        return did_doc

    def set_peer_bundle(self, peer_email: str, bundle: dict) -> None:
        peer = self._ensure_peer(peer_email)
        peer.public_encryption_bundle = bundle

    def has_peer_bundle(self, peer_email: str) -> bool:
        peer = self.get_cached_peer(peer_email)
        return peer is not None and peer.public_encryption_bundle is not None

    def _get_parsed_peer_bundle(
        self, peer_email: str
    ) -> syc.SyftPublicKeyBundle:
        bundle = self._ensure_peer_bundle(peer_email)
        return syc.SyftPublicKeyBundle.from_did_document(bundle)

    def encrypt(self, recipient_email: str, plaintext: bytes) -> bytes:
        keys = self._ensure_private_keys()
        peer_bundle = self._get_parsed_peer_bundle(recipient_email)
        recipient = syc.EncryptionRecipient(recipient_email, peer_bundle)
        return syc.encrypt_message(self.email, keys, [recipient], plaintext)

    def decrypt(self, sender_email: str, envelope: bytes) -> bytes:
        keys = self._ensure_private_keys()
        sender_bundle = self._get_parsed_peer_bundle(sender_email)
        parsed = syc.parse_envelope(envelope)
        return syc.decrypt_message(self.email, keys, sender_bundle, parsed)

    # ========== Persistence ==========

    def save_keys(self, path: Path) -> None:
        keys = self._ensure_private_keys()
        data = {
            "email": self.email,
            "keys_jwk": keys.to_jwks(),
            "peer_bundles": {
                peer.email: peer.public_encryption_bundle
                for peer in self._peers
                if peer.public_encryption_bundle is not None
            },
        }
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load_keys(cls, path: Path) -> "PeerStore":
        data = json.loads(Path(path).read_text())
        store = cls(email=data["email"], use_encryption=True)
        store._private_keys = syc.SyftPrivateKeys.from_jwks(data["keys_jwk"])
        for email, bundle_dict in data.get("peer_bundles", {}).items():
            peer = Peer(
                email=email,
                public_encryption_bundle=bundle_dict,
                use_encryption=True,
            )
            store._peers.append(peer)
        return store

    @classmethod
    def from_keys_data(cls, email: str, keys_data: dict) -> "PeerStore":
        store = cls(email=email, use_encryption=True)
        store._private_keys = syc.SyftPrivateKeys.from_jwks(keys_data["keys_jwk"])
        for peer_email, bundle_dict in keys_data.get("peer_bundles", {}).items():
            peer = Peer(
                email=peer_email,
                public_encryption_bundle=bundle_dict,
                use_encryption=True,
            )
            store._peers.append(peer)
        return store
