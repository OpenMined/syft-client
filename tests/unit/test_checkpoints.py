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
    assert len(backing_store.incremental_checkpoints) == 0

    # With low threshold, should create incremental checkpoint
    result = do_manager.try_create_checkpoint(threshold=2)
    assert result is not None
    assert len(backing_store.incremental_checkpoints) == 1


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


def test_checkpoint_excludes_datasets():
    """Test that checkpoints do not include files under syft_datasets folder."""
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=True
    )

    do_email = do_manager.email

    # Send regular file changes
    ds_manager.send_file_change(
        f"{do_email}/public/regular_file.txt", "Regular content"
    )
    ds_manager.send_file_change(
        f"{do_email}/public/another_file.txt", "Another content"
    )

    # Manually write dataset files directly to the file_connection
    # to simulate dataset files in the syft_datasets folder
    do_cache = do_manager.datasite_owner_syncer.event_cache
    do_cache.file_connection.write_file(
        "public/syft_datasets/my_dataset/data.csv", "dataset,content\n1,2"
    )
    do_cache.file_connection.write_file(
        "public/syft_datasets/my_dataset/metadata.json", '{"name": "test"}'
    )

    # Verify regular files are in cache (from events)
    assert len(do_cache.file_hashes) == 2

    # Create checkpoint
    checkpoint = do_manager.create_checkpoint()

    # Verify checkpoint only contains regular files, NOT dataset files
    assert checkpoint is not None
    checkpoint_paths = [f.path for f in checkpoint.files]

    # Should have 2 regular files
    assert len(checkpoint.files) == 2

    # Regular files should be in checkpoint
    assert any("regular_file.txt" in p for p in checkpoint_paths)
    assert any("another_file.txt" in p for p in checkpoint_paths)

    # Dataset files should NOT be in checkpoint
    assert not any("syft_datasets" in p for p in checkpoint_paths)
    assert not any("data.csv" in p for p in checkpoint_paths)
    assert not any("metadata.json" in p for p in checkpoint_paths)


def test_compact_with_existing_full_checkpoint():
    """Test that compacting merges existing full checkpoint with incremental checkpoints."""
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=True,
        sync_automatically=False,
    )

    do_email = do_manager.email
    backing_store = do_manager.connection_router.connections[0].backing_store

    # Step 1: Create initial files and make a full checkpoint
    ds_manager.send_file_change(f"{do_email}/file1.txt", "content1")
    ds_manager.send_file_change(f"{do_email}/file2.txt", "content2")
    do_manager.sync(auto_checkpoint=False)

    # Create full checkpoint (contains file1 and file2)
    full_checkpoint = do_manager.create_checkpoint()
    assert len(full_checkpoint.files) == 2
    assert len(backing_store.checkpoints) == 1

    # Step 2: Create new files and make incremental checkpoints
    # Send 3 new files (file3, file4, file5)
    ds_manager.send_file_change(f"{do_email}/file3.txt", "content3")
    ds_manager.send_file_change(f"{do_email}/file4.txt", "content4")
    ds_manager.send_file_change(f"{do_email}/file5.txt", "content5")
    do_manager.sync(auto_checkpoint=False)

    # Create first incremental checkpoint (should have 3 files)
    do_manager.try_create_checkpoint(threshold=3)
    assert len(backing_store.incremental_checkpoints) == 1

    # Send 3 more files (file6, file7, file8)
    ds_manager.send_file_change(f"{do_email}/file6.txt", "content6")
    ds_manager.send_file_change(f"{do_email}/file7.txt", "content7")
    ds_manager.send_file_change(f"{do_email}/file8.txt", "content8")
    do_manager.sync(auto_checkpoint=False)

    # Create second incremental checkpoint
    do_manager.try_create_checkpoint(threshold=3)
    assert len(backing_store.incremental_checkpoints) == 2

    # Step 3: Manually call compact_checkpoints
    # This should merge:
    # - Full checkpoint (file1, file2)
    # - Incremental checkpoint #1 (file3, file4, file5)
    # - Incremental checkpoint #2 (file6, file7, file8)
    # = New full checkpoint with all 8 files
    compacted = do_manager.datasite_owner_syncer.compact_checkpoints()

    # Verify compacted checkpoint has all 8 files
    assert len(compacted.files) == 8
    checkpoint_paths = {f.path for f in compacted.files}

    # All files should be present (paths don't include email prefix in checkpoint)
    assert "file1.txt" in checkpoint_paths
    assert "file2.txt" in checkpoint_paths
    assert "file3.txt" in checkpoint_paths
    assert "file4.txt" in checkpoint_paths
    assert "file5.txt" in checkpoint_paths
    assert "file6.txt" in checkpoint_paths
    assert "file7.txt" in checkpoint_paths
    assert "file8.txt" in checkpoint_paths

    # Verify incremental checkpoints are deleted
    assert len(backing_store.incremental_checkpoints) == 0

    # Verify full checkpoint is updated (still 1 checkpoint, but newer)
    assert len(backing_store.checkpoints) == 1


def test_compact_with_no_existing_full_checkpoint():
    """Test that compacting works when there's no existing full checkpoint."""
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=True,
        sync_automatically=False,
    )

    do_email = do_manager.email
    backing_store = do_manager.connection_router.connections[0].backing_store

    # Create incremental checkpoints WITHOUT a full checkpoint first
    # First incremental checkpoint
    ds_manager.send_file_change(f"{do_email}/file1.txt", "content1")
    ds_manager.send_file_change(f"{do_email}/file2.txt", "content2")
    do_manager.sync(auto_checkpoint=False)
    do_manager.try_create_checkpoint(threshold=2)
    assert len(backing_store.incremental_checkpoints) == 1

    # Second incremental checkpoint
    ds_manager.send_file_change(f"{do_email}/file3.txt", "content3")
    ds_manager.send_file_change(f"{do_email}/file4.txt", "content4")
    do_manager.sync(auto_checkpoint=False)
    do_manager.try_create_checkpoint(threshold=2)
    assert len(backing_store.incremental_checkpoints) == 2

    # Compact (without existing full checkpoint)
    compacted = do_manager.datasite_owner_syncer.compact_checkpoints()

    # Verify compacted checkpoint has all 4 files
    assert len(compacted.files) == 4
    checkpoint_paths = {f.path for f in compacted.files}
    assert "file1.txt" in checkpoint_paths
    assert "file2.txt" in checkpoint_paths
    assert "file3.txt" in checkpoint_paths
    assert "file4.txt" in checkpoint_paths

    # Verify incremental checkpoints are deleted
    assert len(backing_store.incremental_checkpoints) == 0
