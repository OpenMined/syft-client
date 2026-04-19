"""Tests for file-backed cache persistence.

If the cache persistence feature is removed or broken, these tests fail.
"""

from syft_client.sync.syftbox_manager import SyftboxManager


def test_no_duplicate_events_across_processes():
    """Two managers sharing a syftbox_folder must not create duplicate events
    for the same file change.

    Without caching: Process B's file_hashes is stale → re-detects Process A's
    changes → uploads duplicate events to GDrive → peers receive them twice.

    With caching: Process B loads A's file_hashes → sees the file was already
    handled → no duplicate event.
    """
    ds_manager, do_manager = SyftboxManager.pair_with_mock_drive_service_connection(
        use_in_memory_cache=False
    )
    do_manager.datasite_owner_syncer.perm_context.open(".").grant_write_access(
        ds_manager.email
    )

    # Both a local DO change and a peer DS change
    local_file = do_manager.syftbox_folder / do_manager.email / "local.txt"
    local_file.parent.mkdir(parents=True, exist_ok=True)
    local_file.write_text("DO wrote this")
    ds_manager._send_file_change(f"{do_manager.email}/from_peer.txt", "DS wrote this")

    # Process A syncs — detects changes, uploads events, saves cache
    do_manager.sync(auto_checkpoint=False)
    events_after_a = len(
        do_manager.datasite_owner_syncer.connection_router.owner_get_all_accepted_event_file_ids()
    )
    assert events_after_a > 0

    # Process B (syft-bg) syncs — must NOT re-create the same events
    do_manager_b = do_manager._copy()
    do_manager_b.sync(auto_checkpoint=False)
    events_after_b = len(
        do_manager_b.datasite_owner_syncer.connection_router.owner_get_all_accepted_event_file_ids()
    )

    # Verify cache files were created
    cache_dir = do_manager.syftbox_folder / ".cache"
    assert (cache_dir / "owner_file_hashes.json").exists(), (
        "owner_file_hashes.json not created after sync"
    )
    assert (cache_dir / "rolling_state.json").exists(), (
        "rolling_state.json not created after sync"
    )

    assert events_after_b == events_after_a, (
        f"Duplicate events! After A: {events_after_a}, after B: {events_after_b}. "
        f"Process B re-detected changes that A already handled."
    )


def test_rolling_state_not_overwritten_across_processes():
    """Process B must build on Process A's rolling state, not overwrite it.

    Without caching: Process B's rolling state is empty → adds only its own
    events → uploads to GDrive → overwrites A's events → data loss.

    With caching: Process B loads A's rolling state → adds its events on top
    → uploads the merged state → nothing lost.
    """
    ds_manager, do_manager = SyftboxManager.pair_with_mock_drive_service_connection(
        use_in_memory_cache=False
    )
    do_manager.datasite_owner_syncer.perm_context.open(".").grant_write_access(
        ds_manager.email
    )

    # Process A: peer sends events, A syncs → rolling state has them
    ds_manager._send_file_change(f"{do_manager.email}/file1.txt", "content1")
    ds_manager._send_file_change(f"{do_manager.email}/file2.txt", "content2")
    do_manager.sync(auto_checkpoint=False)

    rs_after_a = do_manager.datasite_owner_syncer._rolling_state
    assert rs_after_a is not None
    count_after_a = rs_after_a.event_count
    assert count_after_a >= 2

    # Process B: peer sends more events, B syncs
    ds_manager._send_file_change(f"{do_manager.email}/file3.txt", "content3")
    do_manager_b = do_manager._copy()
    do_manager_b.sync(auto_checkpoint=False)

    rs_after_b = do_manager_b.datasite_owner_syncer._rolling_state
    assert rs_after_b is not None

    # B's rolling state must include A's events + its own
    assert rs_after_b.event_count >= count_after_a + 1, (
        f"Rolling state overwrite! A had {count_after_a} events, "
        f"B should have >= {count_after_a + 1}, got {rs_after_b.event_count}. "
        f"Process B overwrote A's rolling state instead of building on it."
    )

    # Verify A's specific files are still in the rolling state
    paths_in_rs = {str(e.path_in_datasite) for e in rs_after_b.events}
    assert "file1.txt" in paths_in_rs, "file1.txt lost from rolling state"
    assert "file2.txt" in paths_in_rs, "file2.txt lost from rolling state"
    assert "file3.txt" in paths_in_rs, "file3.txt missing from rolling state"
