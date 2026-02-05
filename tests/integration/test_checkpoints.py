"""
Integration tests for checkpoint functionality with Google Drive.

Tests checkpoint creation, upload, download, and restore against actual Google Drive.
"""

import os
from time import sleep

import pytest

from syft_client.sync.syftbox_manager import SyftboxManager
from tests.integration.utils import token_path_do, token_path_ds


EMAIL_DO = os.environ.get("BEACH_EMAIL_DO", "")
EMAIL_DS = os.environ.get("BEACH_EMAIL_DS", "")


@pytest.mark.usefixtures("setup_delete_syftboxes")
def test_checkpoint_restore_on_fresh_login():
    """Test that a fresh login restores state from checkpoint instead of downloading all events."""
    # First session: create state and checkpoint
    manager_ds1, manager_do1 = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
    )

    # Send file changes
    manager_ds1.send_file_change(f"{EMAIL_DO}/file1.txt", "File 1 content")
    manager_ds1.send_file_change(f"{EMAIL_DO}/file2.txt", "File 2 content")
    manager_ds1.send_file_change(f"{EMAIL_DO}/file3.txt", "File 3 content")
    sleep(1)

    # DO syncs to receive the files
    manager_do1.sync(auto_checkpoint=False)

    # Create checkpoint
    checkpoint = manager_do1.create_checkpoint()
    assert len(checkpoint.files) == 3
    print(f"Created checkpoint with timestamp: {checkpoint.timestamp}")

    # Second session: fresh login should restore from checkpoint
    manager_ds2, manager_do2 = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        add_peers=False,
        load_peers=True,
        clear_caches=True,  # Clear local caches to simulate fresh login
    )

    # Sync should restore from checkpoint
    manager_do2.sync(auto_checkpoint=False)

    # Verify state was restored
    do_cache = manager_do2.datasite_owner_syncer.event_cache
    assert len(do_cache.file_hashes) == 3, (
        f"Expected 3 files, got {len(do_cache.file_hashes)}"
    )
    print(f"Restored {len(do_cache.file_hashes)} files from checkpoint")


@pytest.mark.usefixtures("setup_delete_syftboxes")
def test_checkpoint_with_incremental_events():
    """Test that full checkpoint + incremental checkpoints + rolling state works correctly."""
    # First session: create initial state and full checkpoint
    manager_ds1, manager_do1 = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
    )

    # Send initial files
    manager_ds1.send_file_change(f"{EMAIL_DO}/initial1.txt", "Initial 1")
    manager_ds1.send_file_change(f"{EMAIL_DO}/initial2.txt", "Initial 2")
    sleep(1)

    manager_do1.sync(auto_checkpoint=False)

    # Create full checkpoint (legacy behavior)
    full_checkpoint = manager_do1.create_checkpoint()
    assert len(full_checkpoint.files) == 2
    checkpoint_timestamp = full_checkpoint.last_event_timestamp
    print(f"Full checkpoint created with last_event_timestamp: {checkpoint_timestamp}")

    # Send more files to create incremental checkpoint
    manager_ds1.send_file_change(f"{EMAIL_DO}/inc1.txt", "Incremental 1")
    manager_ds1.send_file_change(f"{EMAIL_DO}/inc2.txt", "Incremental 2")
    sleep(1)

    manager_do1.sync(auto_checkpoint=False)

    # Create incremental checkpoint (new flow)
    manager_do1.try_create_checkpoint(threshold=2)

    # Verify incremental checkpoint was created
    inc_cps = manager_do1.connection_router.get_all_incremental_checkpoints()
    assert len(inc_cps) >= 1, "Should have at least 1 incremental checkpoint"
    print(f"Created {len(inc_cps)} incremental checkpoint(s)")

    # Send more files for rolling state
    manager_ds1.send_file_change(f"{EMAIL_DO}/rolling1.txt", "Rolling 1")
    sleep(1)

    manager_do1.sync(auto_checkpoint=False)

    # Verify DO1 has all 5 files
    assert len(manager_do1.datasite_owner_syncer.event_cache.file_hashes) == 5

    # Fresh login should restore: full checkpoint + incremental checkpoints + rolling state
    manager_ds2, manager_do2 = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        add_peers=False,
        load_peers=True,
        clear_caches=True,
    )

    manager_do2.sync(auto_checkpoint=False)

    # Should have all 5 files (2 from full checkpoint + 2 from incremental + 1 from rolling state)
    do_cache = manager_do2.datasite_owner_syncer.event_cache
    assert len(do_cache.file_hashes) == 5, (
        f"Expected 5 files, got {len(do_cache.file_hashes)}"
    )
    print(
        f"Restored {len(do_cache.file_hashes)} files (full checkpoint + incremental + rolling state)"
    )


@pytest.mark.usefixtures("setup_delete_syftboxes")
def test_auto_checkpoint_on_sync():
    """Test automatic incremental checkpoint creation and compacting during sync."""
    manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
    )

    # Send enough files to trigger auto-incremental-checkpoint (threshold=5)
    for i in range(6):
        manager_ds.send_file_change(f"{EMAIL_DO}/auto{i}.txt", f"Auto content {i}")
    sleep(1)

    # Sync with auto_checkpoint enabled and low threshold
    manager_do.sync(auto_checkpoint=True, checkpoint_threshold=5)

    # Verify incremental checkpoint was created
    inc_cps = manager_do.connection_router.get_all_incremental_checkpoints()
    assert len(inc_cps) >= 1, "Auto-incremental-checkpoint should have been created"
    print(f"Auto-created {len(inc_cps)} incremental checkpoint(s)")

    # Test compacting: Create more incremental checkpoints
    for i in range(6, 12):
        manager_ds.send_file_change(f"{EMAIL_DO}/auto{i}.txt", f"Auto content {i}")
    sleep(1)

    manager_do.sync(auto_checkpoint=False)
    manager_do.try_create_checkpoint(threshold=5)  # Create 2nd incremental checkpoint

    # Manually compact to test merging
    compacted = manager_do.datasite_owner_syncer.compact_checkpoints()
    assert len(compacted.files) == 12, (
        f"Expected 12 files after compacting, got {len(compacted.files)}"
    )
    print(f"Compacted checkpoint has {len(compacted.files)} files")

    # Verify incremental checkpoints were deleted after compacting
    inc_cps_after = manager_do.connection_router.get_all_incremental_checkpoints()
    assert len(inc_cps_after) == 0, (
        "Incremental checkpoints should be deleted after compacting"
    )

    # Fresh login should restore from compacted checkpoint
    manager_ds2, manager_do2 = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        add_peers=False,
        load_peers=True,
        clear_caches=True,
    )

    manager_do2.sync(auto_checkpoint=False)

    # Should have all 12 files from compacted checkpoint
    do_cache = manager_do2.datasite_owner_syncer.event_cache
    assert len(do_cache.file_hashes) == 12, (
        f"Expected 12 files from compacted checkpoint, got {len(do_cache.file_hashes)}"
    )
    print(f"Restored {len(do_cache.file_hashes)} files from compacted checkpoint")
