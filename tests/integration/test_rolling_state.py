"""
Integration tests for rolling state functionality with Google Drive.

Tests rolling state creation, upload, download, and restore against actual Google Drive.
"""

import os
from time import sleep

import pytest

from syft_client.sync.syftbox_manager import SyftboxManager
from tests.integration.utils import token_path_do, token_path_ds


EMAIL_DO = os.environ.get("BEACH_EMAIL_DO", "")
EMAIL_DS = os.environ.get("BEACH_EMAIL_DS", "")


@pytest.mark.usefixtures("setup_delete_syftboxes")
def test_rolling_state_created_after_checkpoint():
    """Test that rolling state is accumulated after checkpoint creation."""
    manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
    )

    # Send some events
    manager_ds.send_file_change(f"{EMAIL_DO}/file1.txt", "content1")
    manager_ds.send_file_change(f"{EMAIL_DO}/file2.txt", "content2")
    sleep(1)

    # DO syncs and creates checkpoint
    manager_do.sync(auto_checkpoint=False)
    manager_do.create_checkpoint()

    # Send more events after checkpoint
    manager_ds.send_file_change(f"{EMAIL_DO}/file3.txt", "content3")
    manager_ds.send_file_change(f"{EMAIL_DO}/file4.txt", "content4")
    sleep(1)

    # DO syncs again
    manager_do.sync(auto_checkpoint=False)

    # Verify rolling state exists and has the new events
    rs = manager_do.connection_router.get_rolling_state()
    assert rs is not None
    assert rs.event_count == 2  # file3 and file4
    print(f"Rolling state has {rs.event_count} events after checkpoint")


@pytest.mark.usefixtures("setup_delete_syftboxes")
def test_fresh_login_uses_checkpoint_and_rolling_state():
    """Test that fresh login downloads checkpoint + rolling state instead of all events."""
    manager_ds1, manager_do1 = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
    )

    # Send events and create checkpoint
    manager_ds1.send_file_change(f"{EMAIL_DO}/file1.txt", "content1")
    manager_ds1.send_file_change(f"{EMAIL_DO}/file2.txt", "content2")
    sleep(1)
    manager_do1.sync(auto_checkpoint=False)
    manager_do1.create_checkpoint()

    # Send more events after checkpoint
    manager_ds1.send_file_change(f"{EMAIL_DO}/file3.txt", "content3")
    sleep(1)
    manager_do1.sync(auto_checkpoint=False)

    # Verify rolling state exists
    rs = manager_do1.connection_router.get_rolling_state()
    assert rs is not None
    assert rs.event_count >= 1
    print(f"Rolling state has {rs.event_count} events")

    # Fresh login
    _, manager_do2 = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        add_peers=False,
        load_peers=True,
        clear_caches=True,
    )

    # Sync should use checkpoint + rolling state
    manager_do2.sync(auto_checkpoint=False)

    # Verify state was restored
    do_cache = manager_do2.datasite_owner_syncer.event_cache
    assert len(do_cache.file_hashes) >= 3, (
        f"Expected at least 3 files, got {len(do_cache.file_hashes)}"
    )
    print(f"Restored {len(do_cache.file_hashes)} files from checkpoint + rolling state")


@pytest.mark.usefixtures("setup_delete_syftboxes")
def test_checkpoint_resets_rolling_state():
    """Test that creating a new checkpoint resets the rolling state."""
    manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
    )

    # Send events and create checkpoint
    manager_ds.send_file_change(f"{EMAIL_DO}/file1.txt", "content1")
    sleep(1)
    manager_do.sync(auto_checkpoint=False)
    manager_do.create_checkpoint()

    # Send more events
    manager_ds.send_file_change(f"{EMAIL_DO}/file2.txt", "content2")
    manager_ds.send_file_change(f"{EMAIL_DO}/file3.txt", "content3")
    sleep(1)
    manager_do.sync(auto_checkpoint=False)

    # Verify rolling state has 2 events
    rs = manager_do.connection_router.get_rolling_state()
    assert rs is not None
    assert rs.event_count == 2
    print(f"Rolling state has {rs.event_count} events before new checkpoint")

    # Create another checkpoint
    manager_do.create_checkpoint()

    # Rolling state should be deleted/reset
    rs = manager_do.connection_router.get_rolling_state()
    assert rs is None or rs.event_count == 0
    print("Rolling state was reset after new checkpoint")
