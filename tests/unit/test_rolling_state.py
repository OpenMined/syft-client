"""Tests for RollingState functionality.

Tests verify that:
1. RollingState is uploaded and retrieved correctly
2. RollingState can be deleted
3. Uploading replaces existing rolling state
"""

import time
from syft_client.sync.syftbox_manager import SyftboxManager
from syft_client.sync.checkpoints.rolling_state import RollingState
from tests.unit.utils import get_mock_event
from syft_client.sync.syftbox_manager import SyftboxManagerConfig
from syft_client.sync.connections.inmemory_connection import (
    InMemoryPlatformConnection,
    InMemoryBackingPlatform,
)


def test_upload_and_get_rolling_state():
    """Test uploading and retrieving rolling state from in-memory store."""
    _, do_manager = SyftboxManager._pair_with_in_memory_connection()

    # Create a rolling state
    rs = RollingState(
        email=do_manager.email,
        base_checkpoint_timestamp=time.time(),
    )
    event = get_mock_event(f"{do_manager.email}/file1.txt")
    rs.add_event(event)

    # Upload
    do_manager._connection_router.upload_rolling_state(rs)

    # Retrieve
    retrieved = do_manager._connection_router.get_rolling_state()
    assert retrieved is not None
    assert retrieved.email == rs.email
    assert retrieved.event_count == rs.event_count


def test_delete_rolling_state():
    """Test deleting rolling state from in-memory store."""
    _, do_manager = SyftboxManager._pair_with_in_memory_connection()

    # Create and upload a rolling state
    rs = RollingState(
        email=do_manager.email,
        base_checkpoint_timestamp=time.time(),
    )
    do_manager._connection_router.upload_rolling_state(rs)

    # Verify it exists
    assert do_manager._connection_router.get_rolling_state() is not None

    # Delete
    do_manager._connection_router.delete_rolling_state()

    # Verify it's gone
    assert do_manager._connection_router.get_rolling_state() is None


def test_upload_replaces_existing_rolling_state():
    """Test that uploading rolling state replaces existing one."""
    _, do_manager = SyftboxManager._pair_with_in_memory_connection()

    # Create and upload first rolling state
    rs1 = RollingState(
        email=do_manager.email,
        base_checkpoint_timestamp=1000.0,
    )
    do_manager._connection_router.upload_rolling_state(rs1)

    # Create and upload second rolling state
    rs2 = RollingState(
        email=do_manager.email,
        base_checkpoint_timestamp=2000.0,
    )
    do_manager._connection_router.upload_rolling_state(rs2)

    # Verify only one exists and it's the second one
    retrieved = do_manager._connection_router.get_rolling_state()
    assert retrieved is not None
    assert retrieved.base_checkpoint_timestamp == 2000.0


def test_rolling_state_created_after_checkpoint():
    """Test that rolling state is accumulated after checkpoint creation."""
    ds_manager, do_manager = SyftboxManager._pair_with_in_memory_connection()

    # Send some events
    ds_manager._send_file_change(f"{do_manager.email}/file1.txt", "content1")
    ds_manager._send_file_change(f"{do_manager.email}/file2.txt", "content2")

    # DO syncs and creates checkpoint
    do_manager.sync(auto_checkpoint=False)
    do_manager.create_checkpoint()

    # Send more events after checkpoint
    ds_manager._send_file_change(f"{do_manager.email}/file3.txt", "content3")
    ds_manager._send_file_change(f"{do_manager.email}/file4.txt", "content4")

    # DO syncs again
    do_manager.sync(auto_checkpoint=False)

    # Verify rolling state exists and has the new events
    rs = do_manager._connection_router.get_rolling_state()
    assert rs is not None
    assert rs.event_count == 2  # file3 and file4


def test_fresh_login_uses_checkpoint_and_rolling_state():
    """Test that fresh login downloads checkpoint + rolling state instead of all events."""

    ds_manager, do_manager = SyftboxManager._pair_with_in_memory_connection()
    store: InMemoryBackingPlatform = do_manager._connection_router.connections[
        0
    ].backing_store
    do_email = do_manager.email

    # Send events and create checkpoint
    ds_manager._send_file_change(f"{do_manager.email}/file1.txt", "content1")
    ds_manager._send_file_change(f"{do_manager.email}/file2.txt", "content2")
    do_manager.sync(auto_checkpoint=False)
    do_manager.create_checkpoint()

    # Verify checkpoint exists with 2 files
    checkpoint = store.checkpoints[-1]
    assert len(checkpoint.files) == 2

    # Send more events after checkpoint
    ds_manager._send_file_change(f"{do_manager.email}/file3.txt", "content3")
    do_manager.sync(auto_checkpoint=False)

    # Verify rolling state exists
    rolling_state = do_manager._connection_router.get_rolling_state()
    assert rolling_state is not None
    assert rolling_state.event_count >= 1

    # Create a fresh DO manager (simulating fresh login)
    fresh_do_config = SyftboxManagerConfig.base_config_for_in_memory_connection(
        email=do_email,
        only_ds=False,
        only_datasite_owner=True,
        use_in_memory_cache=True,
        check_versions=False,
    )
    fresh_do = SyftboxManager.from_config(fresh_do_config)

    # Connect to the same backing store
    fresh_do_connection = InMemoryPlatformConnection(
        receiver_function=None,
        backing_store=store,
        owner_email=do_email,
    )
    fresh_do._add_connection(fresh_do_connection)

    # Track how many individual events are downloaded
    download_count = 0
    original_download = (
        fresh_do.datasite_owner_syncer.download_events_message_by_id_with_connection
    )

    def counted_download(event_id):
        nonlocal download_count
        download_count += 1
        return original_download(event_id)

    fresh_do.datasite_owner_syncer.download_events_message_by_id_with_connection = (
        counted_download
    )

    # Sync should use checkpoint + rolling state
    fresh_do.sync(auto_checkpoint=False)

    # With rolling state, we shouldn't need to download individual events
    assert download_count == 0, (
        f"Expected 0 individual event downloads, but got {download_count}"
    )

    # Verify checkpoint files are in the cache (at minimum)
    cache = fresh_do.datasite_owner_syncer.event_cache
    assert len(cache.file_hashes) >= 2, (
        f"Expected at least 2 files from checkpoint, got {len(cache.file_hashes)}"
    )


def test_checkpoint_resets_rolling_state():
    """Test that creating a new checkpoint resets the rolling state."""
    ds_manager, do_manager = SyftboxManager._pair_with_in_memory_connection()

    # Send events and create checkpoint
    ds_manager._send_file_change(f"{do_manager.email}/file1.txt", "content1")
    do_manager.sync(auto_checkpoint=False)
    do_manager.create_checkpoint()

    # Send more events
    ds_manager._send_file_change(f"{do_manager.email}/file2.txt", "content2")
    ds_manager._send_file_change(f"{do_manager.email}/file3.txt", "content3")
    do_manager.sync(auto_checkpoint=False)

    # Verify rolling state has 2 events
    rs = do_manager._connection_router.get_rolling_state()
    assert rs is not None
    assert rs.event_count == 2

    # Create another checkpoint
    do_manager.create_checkpoint()

    # Rolling state should be deleted/reset
    rs = do_manager._connection_router.get_rolling_state()
    assert rs is None or rs.event_count == 0


def test_rolling_state_deduplicates_by_path():
    """Test that rolling state only keeps the latest event per file path."""
    rs = RollingState(
        email="test@test.com",
        base_checkpoint_timestamp=1000.0,
    )

    # Add multiple events for the same file
    event1 = get_mock_event("test@test.com/file.txt")
    event1.content = "version1"
    rs.add_event(event1)
    assert rs.event_count == 1

    event2 = get_mock_event("test@test.com/file.txt")
    event2.content = "version2"
    rs.add_event(event2)

    # Should still be 1 event (replaced, not appended)
    assert rs.event_count == 1
    assert rs.events[0].content == "version2"

    # Add a different file
    event3 = get_mock_event("test@test.com/other.txt")
    rs.add_event(event3)
    assert rs.event_count == 2


def test_rolling_state_clear_resets_base_timestamp():
    """Test that clear() resets events and updates base_checkpoint_timestamp."""
    rs = RollingState(
        email="test@test.com",
        base_checkpoint_timestamp=1000.0,
    )

    event = get_mock_event("test@test.com/file.txt")
    rs.add_event(event)
    assert rs.event_count == 1
    assert rs.base_checkpoint_timestamp == 1000.0

    # Clear with new timestamp
    rs.clear(new_base_checkpoint_timestamp=2000.0)

    assert rs.event_count == 0
    assert rs.base_checkpoint_timestamp == 2000.0
    assert rs.last_event_timestamp is None
