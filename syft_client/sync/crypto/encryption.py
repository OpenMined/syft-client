"""End-to-end encryption for peer-to-peer message exchange.

Uses syft-crypto-python (Rust-based) for key generation, encryption, and decryption.
Each peer generates identity keys via SyftRecoveryKey. Public bundles (DID documents)
are exchanged during peer approval. Encryption uses the Double Ratchet protocol.
"""

import json
from pathlib import Path

import syft_crypto_python as syc


class KeyManager:
    """Manages encryption keys and peer public bundles for E2E encryption."""

    def __init__(self, email: str):
        self.email = email
        self._keys: syc.SyftPrivateKeys | None = None
        self._peer_bundles: dict[str, syc.SyftPublicKeyBundle] = {}

    def generate_keys(self) -> None:
        self._keys = syc.SyftRecoveryKey.generate().derive_keys()

    def has_keys(self) -> bool:
        return self._keys is not None

    @property
    def public_key(self) -> syc.SyftPublicKeyBundle | None:
        if self._keys is None:
            return None
        return self._keys.to_public_bundle()

    def get_public_bundle(self) -> dict | None:
        """Return the public bundle as a DID document dict."""
        if self._keys is None:
            return None
        bundle = self._keys.to_public_bundle()
        did = f"did:syft:{self.email}"
        did_doc = bundle.to_did_document(did)
        did_doc["identity"] = self.email
        return did_doc

    def set_peer_bundle(self, peer_email: str, bundle: dict) -> None:
        """Store a peer's public bundle (DID document dict)."""
        self._peer_bundles[peer_email] = syc.SyftPublicKeyBundle.from_did_document(
            bundle
        )

    def get_peer_bundle(self, peer_email: str) -> dict | None:
        """Get a peer's stored public bundle as DID document dict."""
        bundle = self._peer_bundles.get(peer_email)
        if bundle is None:
            return None
        did = f"did:syft:{peer_email}"
        did_doc = bundle.to_did_document(did)
        did_doc["identity"] = peer_email
        return did_doc

    def has_peer_bundle(self, peer_email: str) -> bool:
        return peer_email in self._peer_bundles

    def encrypt(self, recipient_email: str, plaintext: bytes) -> bytes:
        if self._keys is None:
            raise ValueError("No private key — call generate_keys() first")
        peer_bundle = self._peer_bundles.get(recipient_email)
        if peer_bundle is None:
            raise ValueError(f"No public key for peer {recipient_email}")

        recipient = syc.EncryptionRecipient(recipient_email, peer_bundle)
        return syc.encrypt_message(self.email, self._keys, [recipient], plaintext)

    def decrypt(self, sender_email: str, envelope: bytes) -> bytes:
        if self._keys is None:
            raise ValueError("No private key — call generate_keys() first")
        sender_bundle = self._peer_bundles.get(sender_email)
        if sender_bundle is None:
            raise ValueError(f"No public key for peer {sender_email}")

        parsed = syc.parse_envelope(envelope)
        return syc.decrypt_message(self.email, self._keys, sender_bundle, parsed)

    def try_decrypt(self, sender_email: str, data: bytes) -> bytes:
        """Try to decrypt; return data as-is if not possible or fails."""
        if not self.has_keys() or not self.has_peer_bundle(sender_email):
            return data
        try:
            return self.decrypt(sender_email, data)
        except Exception:
            return data

    # ===== Persistence =====

    def save_keys(self, path: Path) -> None:
        """Save private keys and peer bundles to a JSON file."""
        if self._keys is None:
            raise ValueError("No keys to save")

        data = {
            "email": self.email,
            "keys_jwk": self._keys.to_jwks(),
            "peer_bundles": {
                email: self._bundle_to_dict(email, bundle)
                for email, bundle in self._peer_bundles.items()
            },
        }

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load_keys(cls, path: Path) -> "KeyManager":
        """Load a KeyManager from a saved JSON file."""
        data = json.loads(Path(path).read_text())
        km = cls(email=data["email"])
        km._keys = syc.SyftPrivateKeys.from_jwks(data["keys_jwk"])
        for email, bundle_dict in data.get("peer_bundles", {}).items():
            km._peer_bundles[email] = syc.SyftPublicKeyBundle.from_did_document(
                bundle_dict
            )
        return km

    @classmethod
    def from_keys_data(cls, email: str, keys_data: dict) -> "KeyManager":
        """Create a KeyManager from a dict with keys_jwk."""
        km = cls(email=email)
        km._keys = syc.SyftPrivateKeys.from_jwks(keys_data["keys_jwk"])
        for peer_email, bundle_dict in keys_data.get("peer_bundles", {}).items():
            km._peer_bundles[peer_email] = syc.SyftPublicKeyBundle.from_did_document(
                bundle_dict
            )
        return km

    @staticmethod
    def _bundle_to_dict(email: str, bundle: syc.SyftPublicKeyBundle) -> dict:
        did = f"did:syft:{email}"
        did_doc = bundle.to_did_document(did)
        did_doc["identity"] = email
        return did_doc
