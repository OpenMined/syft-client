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
    """Test that checkpoint + incremental events works correctly."""
    # First session: create initial state and checkpoint
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

    # Create checkpoint
    checkpoint = manager_do1.create_checkpoint()
    assert len(checkpoint.files) == 2
    checkpoint_timestamp = checkpoint.last_event_timestamp
    print(f"Checkpoint created with last_event_timestamp: {checkpoint_timestamp}")

    # Send more files AFTER checkpoint
    manager_ds1.send_file_change(f"{EMAIL_DO}/after1.txt", "After checkpoint 1")
    manager_ds1.send_file_change(f"{EMAIL_DO}/after2.txt", "After checkpoint 2")
    sleep(1)

    manager_do1.sync(auto_checkpoint=False)

    # Verify DO1 has all 4 files
    assert len(manager_do1.datasite_owner_syncer.event_cache.file_hashes) == 4

    # Fresh login should restore checkpoint + incremental events
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

    # Should have all 4 files (2 from checkpoint + 2 from incremental)
    do_cache = manager_do2.datasite_owner_syncer.event_cache
    assert len(do_cache.file_hashes) == 4, (
        f"Expected 4 files, got {len(do_cache.file_hashes)}"
    )
    print(f"Restored {len(do_cache.file_hashes)} files (checkpoint + incremental)")


@pytest.mark.usefixtures("setup_delete_syftboxes")
def test_auto_checkpoint_on_sync():
    """Test automatic checkpoint creation during sync."""
    manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
    )

    # Send enough files to trigger auto-checkpoint (threshold=5)
    for i in range(6):
        manager_ds.send_file_change(f"{EMAIL_DO}/auto{i}.txt", f"Auto content {i}")
    sleep(1)

    # Sync with auto_checkpoint enabled and low threshold
    manager_do.sync(auto_checkpoint=True, checkpoint_threshold=5)

    # Verify checkpoint was created by checking if fresh login can restore
    manager_ds2, manager_do2 = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        add_peers=False,
        load_peers=True,
        clear_caches=True,
    )

    # Get latest checkpoint
    checkpoint = manager_do2.connection_router.get_latest_checkpoint()
    assert checkpoint is not None, "Auto-checkpoint should have been created"
    assert len(checkpoint.files) == 6
    print(f"Auto-checkpoint found with {len(checkpoint.files)} files")
