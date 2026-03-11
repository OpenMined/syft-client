import tempfile
from pathlib import Path

import pytest

from syft_client.sync.peers.peer import Peer
from syft_client.sync.peers.peer_store import PeerStore
from syft_client.sync.syftbox_manager import SyftboxManager


# =========================================================================
# PeerStore unit tests
# =========================================================================


def test_key_generation():
    ps = PeerStore(email="alice@example.com", use_encryption=True)
    assert not ps.has_my_keys()
    ps.generate_keys()
    assert ps.has_my_keys()
    assert ps.public_key is not None
    assert ps.get_public_bundle() is not None


def test_encrypt_decrypt_roundtrip():
    alice = PeerStore(email="alice@example.com", use_encryption=True)
    alice.generate_keys()
    bob = PeerStore(email="bob@example.com", use_encryption=True)
    bob.generate_keys()

    # Add peers so bundles can be stored on Peer objects
    alice.add_peer(Peer(email="bob@example.com"))
    bob.add_peer(Peer(email="alice@example.com"))

    # Exchange bundles
    alice.set_peer_bundle("bob@example.com", bob.get_public_bundle())
    bob.set_peer_bundle("alice@example.com", alice.get_public_bundle())

    plaintext = b"Hello, this is a secret message!"
    envelope = alice.encrypt("bob@example.com", plaintext)
    assert envelope != plaintext

    decrypted = bob.decrypt("alice@example.com", envelope)
    assert decrypted == plaintext


def test_encrypt_without_keys_raises():
    ps = PeerStore(email="alice@example.com", use_encryption=True)
    ps.add_peer(Peer(email="bob@example.com"))
    with pytest.raises(ValueError, match="No private key"):
        ps.encrypt("bob@example.com", b"data")


def test_encrypt_without_peer_bundle_raises():
    ps = PeerStore(email="alice@example.com", use_encryption=True)
    ps.generate_keys()
    ps.add_peer(Peer(email="bob@example.com"))
    with pytest.raises(ValueError, match="No public key for peer"):
        ps.encrypt("bob@example.com", b"data")


def test_try_decrypt_no_keys():
    ps = PeerStore(email="alice@example.com", use_encryption=True)
    data = b"some unencrypted data"
    assert ps.try_decrypt("bob@example.com", data) == data


def test_try_decrypt_no_peer_bundle():
    ps = PeerStore(email="alice@example.com", use_encryption=True)
    ps.generate_keys()
    data = b"some unencrypted data"
    assert ps.try_decrypt("bob@example.com", data) == data


def test_try_decrypt_invalid_envelope():
    alice = PeerStore(email="alice@example.com", use_encryption=True)
    alice.generate_keys()
    bob = PeerStore(email="bob@example.com", use_encryption=True)
    bob.generate_keys()

    alice.add_peer(Peer(email="bob@example.com"))
    bob.add_peer(Peer(email="alice@example.com"))

    alice.set_peer_bundle("bob@example.com", bob.get_public_bundle())
    bob.set_peer_bundle("alice@example.com", alice.get_public_bundle())

    bad_data = b"not encrypted at all"
    result = bob.try_decrypt("alice@example.com", bad_data)
    assert result == bad_data


def test_save_and_load_keys():
    alice = PeerStore(email="alice@example.com", use_encryption=True)
    alice.generate_keys()
    bob = PeerStore(email="bob@example.com", use_encryption=True)
    bob.generate_keys()

    alice.add_peer(Peer(email="bob@example.com"))
    alice.set_peer_bundle("bob@example.com", bob.get_public_bundle())

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)

    alice.save_keys(path)
    loaded = PeerStore.load_keys(path)

    assert loaded.email == "alice@example.com"
    assert loaded.has_my_keys()
    assert loaded.get_public_bundle() is not None
    assert loaded.has_peer_bundle("bob@example.com")
    path.unlink()


def test_from_keys_data():
    alice = PeerStore(email="alice@example.com", use_encryption=True)
    alice.generate_keys()

    keys_data = {"keys_jwk": alice._keys.to_jwks()}
    loaded = PeerStore.from_keys_data("alice@example.com", keys_data)
    assert loaded.has_my_keys()
    assert loaded.get_public_bundle() is not None


def test_peer_use_encryption_inherited():
    """Peers added to PeerStore inherit its use_encryption flag."""
    ps = PeerStore(email="alice@example.com", use_encryption=True)
    peer = Peer(email="bob@example.com")
    assert not peer.use_encryption
    ps.add_peer(peer)
    assert peer.use_encryption

    ps2 = PeerStore(email="alice@example.com", use_encryption=False)
    peer2 = Peer(email="bob@example.com", use_encryption=True)
    ps2.add_peer(peer2)
    assert not peer2.use_encryption


def test_set_peers_inherits_encryption():
    """set_peers propagates use_encryption to all peers."""
    ps = PeerStore(email="alice@example.com", use_encryption=True)
    peers = [Peer(email="bob@example.com"), Peer(email="carol@example.com")]
    ps.set_peers(peers)
    assert all(p.use_encryption for p in peers)


# =========================================================================
# Full DS→DO→DS flow with encryption via mock drive
# =========================================================================


def test_encrypted_message_flow():
    """Full sync flow with encryption: DS sends message, DO receives and decrypts."""
    ds_manager, do_manager = SyftboxManager.pair_with_mock_drive_service_connection(
        encryption=True,
    )

    # Verify peer stores are set with encryption enabled
    assert ds_manager._peer_store is not None
    assert do_manager._peer_store is not None

    # DO has DS's bundle after approval
    do_ps = do_manager._peer_store
    assert do_ps.has_peer_bundle(ds_manager.email)

    # DS needs to load_peers to pick up DO's bundle
    ds_manager.load_peers()
    ds_ps = ds_manager._peer_store
    assert ds_ps.has_peer_bundle(do_manager.email)

    # DS sends a file change (encrypted)
    file_path = f"{do_manager.email}/app_data/job/{ds_manager.email}/my.job"
    ds_manager._send_file_change(file_path, "encrypted content")

    # DO syncs and should receive the decrypted content
    do_manager.sync()

    events = do_manager._get_all_accepted_events_do()
    assert len(events) > 0

    all_events = [e for msg in events for e in msg.events]
    matching = [e for e in all_events if "encrypted content" in str(e.content)]
    assert len(matching) > 0


def test_encrypted_sync_down_ds():
    """DS can pull encrypted events from DO outbox."""
    ds_manager, do_manager = SyftboxManager.pair_with_mock_drive_service_connection(
        encryption=True,
    )

    # DS sends a file
    file_path = f"{do_manager.email}/app_data/job/{ds_manager.email}/test.job"
    ds_manager._send_file_change(file_path, "test data")

    # DO syncs (receives and processes)
    do_manager.sync()

    # DS syncs down (pulls encrypted events from DO outbox)
    ds_manager.sync()

    # DS should have cached events
    cached = (
        ds_manager.datasite_watcher_syncer.datasite_watcher_cache.get_cached_events()
    )
    assert len(cached) > 0


def test_no_encryption_backward_compat():
    """Without encryption, everything works as before."""
    ds_manager, do_manager = SyftboxManager.pair_with_mock_drive_service_connection(
        encryption=False,
    )

    assert ds_manager._peer_store is None
    assert do_manager._peer_store is None

    file_path = f"{do_manager.email}/app_data/job/{ds_manager.email}/my.job"
    ds_manager._send_file_change(file_path, "hello unencrypted")
    do_manager.sync()

    events = do_manager._get_all_accepted_events_do()
    assert len(events) > 0


def test_bundle_exchange_through_peer_approval():
    """Bundles are exchanged during add_peer/approve flow."""
    ds_manager, do_manager = SyftboxManager.pair_with_mock_drive_service_connection(
        encryption=True,
        add_peers=False,
    )

    ds_ps = ds_manager._peer_store
    do_ps = do_manager._peer_store

    # Before peer add, no peer bundles
    assert not ds_ps.has_peer_bundle(do_manager.email)
    assert not do_ps.has_peer_bundle(ds_manager.email)

    # DS adds peer (writes bundle)
    ds_manager.add_peer(do_manager.email)

    # DO loads peers and approves (reads DS bundle, writes own)
    do_manager.load_peers()
    do_manager.approve_peer_request(ds_manager.email)

    # DO should now have DS's bundle
    assert do_ps.has_peer_bundle(ds_manager.email)

    # DS loads peers again to pick up DO's bundle
    ds_manager.load_peers()
    assert ds_ps.has_peer_bundle(do_manager.email)


def test_unencrypted_fallback_when_no_bundles():
    """Messages sent without encryption can be read by encrypted client."""
    ds_no_enc, do_no_enc = SyftboxManager.pair_with_mock_drive_service_connection(
        encryption=False,
    )

    # Send unencrypted message
    file_path = f"{do_no_enc.email}/app_data/job/{ds_no_enc.email}/test.job"
    ds_no_enc._send_file_change(file_path, "plain text")

    # Now enable encryption on DO side for receiving
    from syft_client.sync.peers.peer_store import PeerStore

    ps = PeerStore(email=do_no_enc.email, use_encryption=True)
    ps.generate_keys()
    do_no_enc._set_peer_store(ps)

    # DO syncs - should still be able to read unencrypted message via try_decrypt
    do_no_enc.sync()

    events = do_no_enc._get_all_accepted_events_do()
    assert len(events) > 0
