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

    _keys: syc.SyftPrivateKeys | None = PrivateAttr(default=None)
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

    def add_peer(self, peer: Peer) -> None:
        peer.use_encryption = self.use_encryption
        self._peers.append(peer)

    def set_peers(self, peers: List[Peer]) -> None:
        for p in peers:
            p.use_encryption = self.use_encryption
        self._peers = peers

    # ========== Crypto methods ==========

    def generate_keys(self) -> None:
        self._keys = syc.SyftRecoveryKey.generate().derive_keys()

    def has_my_keys(self) -> bool:
        return self._keys is not None

    @property
    def public_key(self) -> syc.SyftPublicKeyBundle | None:
        if self._keys is None:
            return None
        return self._keys.to_public_bundle()

    def get_public_bundle(self) -> dict | None:
        if self._keys is None:
            return None
        bundle = self._keys.to_public_bundle()
        did = f"did:syft:{self.email}"
        did_doc = bundle.to_did_document(did)
        did_doc["identity"] = self.email
        return did_doc

    def set_peer_bundle(self, peer_email: str, bundle: dict) -> None:
        peer = self.get_cached_peer(peer_email)
        if peer:
            peer.public_bundle = bundle

    def has_peer_bundle(self, peer_email: str) -> bool:
        peer = self.get_cached_peer(peer_email)
        return peer is not None and peer.public_bundle is not None

    def _get_parsed_peer_bundle(
        self, peer_email: str
    ) -> syc.SyftPublicKeyBundle | None:
        peer = self.get_cached_peer(peer_email)
        if not peer or not peer.public_bundle:
            return None
        return syc.SyftPublicKeyBundle.from_did_document(peer.public_bundle)

    def encrypt(self, recipient_email: str, plaintext: bytes) -> bytes:
        if self._keys is None:
            raise ValueError("No private key — call generate_keys() first")
        peer_bundle = self._get_parsed_peer_bundle(recipient_email)
        if peer_bundle is None:
            raise ValueError(f"No public key for peer {recipient_email}")
        recipient = syc.EncryptionRecipient(recipient_email, peer_bundle)
        return syc.encrypt_message(
            self.email, self._keys, [recipient], plaintext
        )

    def decrypt(self, sender_email: str, envelope: bytes) -> bytes:
        if self._keys is None:
            raise ValueError("No private key — call generate_keys() first")
        sender_bundle = self._get_parsed_peer_bundle(sender_email)
        if sender_bundle is None:
            raise ValueError(f"No public key for peer {sender_email}")
        parsed = syc.parse_envelope(envelope)
        return syc.decrypt_message(
            self.email, self._keys, sender_bundle, parsed
        )

    def try_decrypt(self, sender_email: str, data: bytes) -> bytes:
        if not self.has_my_keys() or not self.has_peer_bundle(sender_email):
            return data
        try:
            return self.decrypt(sender_email, data)
        except Exception:
            return data

    # ========== Persistence ==========

    def save_keys(self, path: Path) -> None:
        if self._keys is None:
            raise ValueError("No keys to save")
        data = {
            "email": self.email,
            "keys_jwk": self._keys.to_jwks(),
            "peer_bundles": {
                peer.email: self._bundle_to_dict(peer.email, peer.public_bundle)
                for peer in self._peers
                if peer.public_bundle is not None
            },
        }
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load_keys(cls, path: Path) -> "PeerStore":
        data = json.loads(Path(path).read_text())
        store = cls(email=data["email"], use_encryption=True)
        store._keys = syc.SyftPrivateKeys.from_jwks(data["keys_jwk"])
        for email, bundle_dict in data.get("peer_bundles", {}).items():
            peer = Peer(email=email, public_bundle=bundle_dict, use_encryption=True)
            store._peers.append(peer)
        return store

    @classmethod
    def from_keys_data(cls, email: str, keys_data: dict) -> "PeerStore":
        store = cls(email=email, use_encryption=True)
        store._keys = syc.SyftPrivateKeys.from_jwks(keys_data["keys_jwk"])
        for peer_email, bundle_dict in keys_data.get("peer_bundles", {}).items():
            peer = Peer(
                email=peer_email, public_bundle=bundle_dict, use_encryption=True
            )
            store._peers.append(peer)
        return store

    @staticmethod
    def _bundle_to_dict(email: str, bundle: dict) -> dict:
        """Peer bundles are already stored as dicts, just return as-is."""
        return bundle
