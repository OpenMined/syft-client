from pathlib import Path

from syft_client.sync.syftbox_manager import SyftboxManager


def test_peer_request_blocks_sync_until_approved():
    """
    Test that files don't sync until peer request is approved.

    Workflow:
    1. DS adds DO as peer (creates peer request)
    2. DS submits a job
    3. DO syncs - nothing should sync (peer not approved)
    4. DO approves peer request
    5. DO syncs - job should now sync
    """
    # Create managers with in-memory connection, no auto-add peers
    # Note: email1 becomes DO, email2 becomes DS
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        email1="do@test.com",  # email1 → DO manager
        email2="ds@test.com",  # email2 → DS manager
        add_peers=False,  # Don't auto-add - we'll test the request flow
    )

    # Step 1: DS makes peer request by adding DO
    ds_manager.add_peer(do_manager.email)

    # Verify: DO sees this as a pending request
    do_manager.load_peers()
    assert len(do_manager.version_manager.pending_peers) == 1
    assert len(do_manager.version_manager.approved_peers) == 0
    assert do_manager.version_manager.pending_peers[0].email == ds_manager.email

    # Step 2: DS submits a simple job
    job_file_path = f"{do_manager.email}/test.job"
    job_content = "print('Hello from DS')"
    ds_manager.send_file_change(job_file_path, job_content)

    # Step 3: DO syncs WITHOUT accepting - nothing should sync
    do_manager.sync()

    # Verify: Cache is empty (no messages processed)
    do_cache = do_manager.datasite_owner_syncer.event_cache
    assert len(do_cache.file_hashes) == 0, "Cache should be empty - peer not approved"

    # Step 4: DO approves peer request
    do_manager.approve_peer_request(ds_manager.email)

    # Verify: Peer moved from requests to approved
    assert len(do_manager.version_manager.pending_peers) == 0
    assert len(do_manager.version_manager.approved_peers) == 1
    assert do_manager.version_manager.approved_peers[0].email == ds_manager.email

    # Step 5: DO syncs again - now it should work
    do_manager.sync()

    # Verify: File synced and in cache
    assert len(do_cache.file_hashes) > 0, "Cache should have content after approval"

    # Verify: File is tracked in cache with correct path (stored as PosixPath)
    expected_cache_path = Path("test.job")
    assert expected_cache_path in do_cache.file_hashes, (
        f"File {expected_cache_path} should be in cache"
    )

    # Verify: Content is correct
    assert do_cache.file_hashes[expected_cache_path] is not None, (
        "File should have a hash"
    )


def test_peer_request_rejection():
    """Test that rejected peer requests don't allow syncing"""
    # Note: email1 becomes DO, email2 becomes DS
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        email1="do@test.com",  # email1 → DO manager
        email2="ds@test.com",  # email2 → DS manager
        add_peers=False,
    )

    # DS makes peer request
    ds_manager.add_peer(do_manager.email)
    do_manager.load_peers()

    # DS sends a job
    job_file_path = f"{do_manager.email}/test.job"
    ds_manager.send_file_change(job_file_path, "print('test')")

    # DO rejects the peer request
    do_manager.reject_peer_request(ds_manager.email)

    # DO syncs
    do_manager.sync()

    # Verify: Nothing synced - cache should remain empty
    do_cache = do_manager.datasite_owner_syncer.event_cache
    assert len(do_cache.file_hashes) == 0, "Cache should be empty - peer rejected"
