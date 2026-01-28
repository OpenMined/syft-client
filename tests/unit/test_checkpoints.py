"""
Unit tests for checkpoint functionality.

Tests checkpoint creation, restore, threshold-based creation,
and in-memory checkpoint methods.
"""

from syft_client.sync.syftbox_manager import SyftboxManager
from syft_client.sync.connections.inmemory_connection import (
    InMemoryPlatformConnection,
    InMemoryBackingPlatform,
)
from syft_client.sync.checkpoints.checkpoint import Checkpoint


def test_checkpoint_create_and_restore():
    """Test that checkpoints can be created and restored."""
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=True
    )

    do_email = do_manager.email

    # Send some file changes to build state (path format: email/filename)
    ds_manager.send_file_change(f"{do_email}/test1.txt", "Content 1")
    ds_manager.send_file_change(f"{do_email}/test2.txt", "Content 2")

    # Verify files are in cache
    do_cache = do_manager.datasite_owner_syncer.event_cache
    assert len(do_cache.file_hashes) == 2

    # Create checkpoint
    checkpoint = do_manager.create_checkpoint()

    assert checkpoint is not None
    assert len(checkpoint.files) == 2
    assert checkpoint.email == do_manager.email

    # Verify checkpoint is stored in backing store
    backing_store = do_manager.connection_router.connections[0].backing_store
    assert len(backing_store.checkpoints) == 1

    # Get latest checkpoint
    latest_checkpoint = do_manager.connection_router.get_latest_checkpoint()
    assert latest_checkpoint is not None
    assert latest_checkpoint.timestamp == checkpoint.timestamp


def test_checkpoint_should_create():
    """Test should_create_checkpoint logic."""
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=True
    )

    do_email = do_manager.email

    # No events - should not create checkpoint with low threshold
    assert not do_manager.should_create_checkpoint(threshold=1)

    # Send file changes
    for i in range(5):
        ds_manager.send_file_change(f"{do_email}/test{i}.txt", f"Content {i}")

    # Now we have 5 events - check thresholds
    assert do_manager.should_create_checkpoint(threshold=3)
    assert do_manager.should_create_checkpoint(threshold=5)
    assert not do_manager.should_create_checkpoint(threshold=10)


def test_checkpoint_try_create():
    """Test try_create_checkpoint only creates when threshold exceeded."""
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=True
    )

    do_email = do_manager.email

    # Send 3 file changes
    for i in range(3):
        ds_manager.send_file_change(f"{do_email}/test{i}.txt", f"Content {i}")

    # With high threshold, should not create
    result = do_manager.try_create_checkpoint(threshold=10)
    assert result is None

    backing_store = do_manager.connection_router.connections[0].backing_store
    assert len(backing_store.checkpoints) == 0

    # With low threshold, should create
    result = do_manager.try_create_checkpoint(threshold=2)
    assert result is not None
    assert len(backing_store.checkpoints) == 1


def test_checkpoint_restore_on_sync():
    """Test that sync uses checkpoint for initial state restore."""
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=True,
        sync_automatically=False,
    )

    do_email = do_manager.email

    # Send file changes and create initial state (path format: email/filename)
    ds_manager.send_file_change(f"{do_email}/test1.txt", "Content 1")
    ds_manager.send_file_change(f"{do_email}/test2.txt", "Content 2")
    do_manager.sync(auto_checkpoint=False)

    # Create checkpoint
    checkpoint = do_manager.create_checkpoint()
    assert len(checkpoint.files) == 2

    # Clear cache to simulate fresh login
    do_manager.datasite_owner_syncer.event_cache.clear_cache()
    do_manager.datasite_owner_syncer.initial_sync_done = False

    # Sync should restore from checkpoint
    do_manager.sync(auto_checkpoint=False)

    # Verify state was restored
    do_cache = do_manager.datasite_owner_syncer.event_cache
    assert len(do_cache.file_hashes) == 2


def test_checkpoint_events_since():
    """Test getting events since checkpoint timestamp."""
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=True,
        sync_automatically=False,
    )

    do_email = do_manager.email

    # Send initial files and sync (path format: email/filename)
    ds_manager.send_file_change(f"{do_email}/test1.txt", "Content 1")
    do_manager.sync(auto_checkpoint=False)

    # Create checkpoint
    checkpoint = do_manager.create_checkpoint()

    # Send more files after checkpoint
    ds_manager.send_file_change(f"{do_email}/test2.txt", "Content 2")
    ds_manager.send_file_change(f"{do_email}/test3.txt", "Content 3")
    do_manager.sync(auto_checkpoint=False)

    # Count events since checkpoint
    events_count = do_manager.connection_router.get_events_count_since_checkpoint(
        checkpoint.last_event_timestamp
    )
    # Should have 2 new events (test2.txt and test3.txt)
    assert events_count >= 2

    # Get events since checkpoint
    events_messages = do_manager.connection_router.get_events_messages_since_timestamp(
        checkpoint.last_event_timestamp
    )
    assert len(events_messages) >= 1


def test_inmemory_checkpoint_methods():
    """Test in-memory connection checkpoint methods directly."""
    backing_store = InMemoryBackingPlatform()
    connection = InMemoryPlatformConnection(
        owner_email="test@test.com",
        backing_store=backing_store,
    )

    # Initially no checkpoint
    assert connection.get_latest_checkpoint() is None

    # Create and upload checkpoint
    checkpoint1 = Checkpoint(email="test@test.com", timestamp=100.0)
    connection.upload_checkpoint(checkpoint1)

    # Get latest checkpoint
    latest = connection.get_latest_checkpoint()
    assert latest is not None
    assert latest.timestamp == 100.0

    # Upload another checkpoint with higher timestamp
    checkpoint2 = Checkpoint(email="test@test.com", timestamp=200.0)
    connection.upload_checkpoint(checkpoint2)

    # Get latest should return the newer one
    latest = connection.get_latest_checkpoint()
    assert latest.timestamp == 200.0

    # Test events count
    assert connection.get_events_count_since_checkpoint(None) == 0
    assert connection.get_events_count_since_checkpoint(100.0) == 0
