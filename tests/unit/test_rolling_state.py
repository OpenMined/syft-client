"""Tests for RollingState functionality.

Tests verify that:
1. RollingState data model works correctly
2. RollingState is accumulated after checkpoint
3. Fresh login uses checkpoint + rolling state for fast sync
4. Rolling state is reset when new checkpoint is created
"""

import time
from syft_client.sync.syftbox_manager import SyftboxManager
from syft_client.sync.connections.inmemory_connection import InMemoryBackingPlatform
from syft_client.sync.checkpoints.rolling_state import (
    RollingState,
    ROLLING_STATE_FILENAME_PREFIX,
)
from tests.unit.utils import get_mock_event, get_mock_events_messages


class TestRollingStateModel:
    """Tests for the RollingState data model."""

    def test_rolling_state_creation(self):
        """Test basic RollingState creation."""
        rs = RollingState(
            email="test@test.com",
            base_checkpoint_timestamp=1234567890.0,
        )
        assert rs.email == "test@test.com"
        assert rs.base_checkpoint_timestamp == 1234567890.0
        assert rs.event_count == 0
        assert rs.last_event_timestamp is None

    def test_rolling_state_add_event(self):
        """Test adding events to rolling state."""
        rs = RollingState(
            email="test@test.com",
            base_checkpoint_timestamp=1234567890.0,
        )
        event = get_mock_event("test@test.com/file1.txt")
        rs.add_event(event)

        assert rs.event_count == 1
        assert rs.last_event_timestamp == event.timestamp
        assert rs.events[0] == event

    def test_rolling_state_add_events_message(self):
        """Test adding an events message to rolling state."""
        rs = RollingState(
            email="test@test.com",
            base_checkpoint_timestamp=1234567890.0,
        )
        events_messages = get_mock_events_messages(3)

        for msg in events_messages:
            rs.add_events_message(msg)

        assert rs.event_count == 3

    def test_rolling_state_clear(self):
        """Test clearing rolling state."""
        rs = RollingState(
            email="test@test.com",
            base_checkpoint_timestamp=1234567890.0,
        )
        event = get_mock_event("test@test.com/file1.txt")
        rs.add_event(event)

        new_checkpoint_ts = 1234567900.0
        rs.clear(new_checkpoint_ts)

        assert rs.event_count == 0
        assert rs.base_checkpoint_timestamp == new_checkpoint_ts
        assert rs.last_event_timestamp is None

    def test_rolling_state_filename(self):
        """Test rolling state filename generation."""
        rs = RollingState(
            email="test@test.com",
            base_checkpoint_timestamp=1234567890.0,
        )
        filename = rs.filename
        assert filename.startswith(ROLLING_STATE_FILENAME_PREFIX)
        assert filename.endswith(".tar.gz")

    def test_rolling_state_filename_to_timestamp(self):
        """Test extracting timestamp from filename."""
        # Create a rolling state and get its filename
        rs = RollingState(
            email="test@test.com",
            base_checkpoint_timestamp=1234567890.0,
        )
        filename = rs.filename

        # Extract timestamp back
        extracted_ts = RollingState.filename_to_timestamp(filename)
        assert extracted_ts == rs.timestamp

    def test_rolling_state_compression(self):
        """Test rolling state serialization and deserialization."""
        rs = RollingState(
            email="test@test.com",
            base_checkpoint_timestamp=1234567890.0,
        )
        event = get_mock_event("test@test.com/file1.txt")
        rs.add_event(event)

        # Compress and decompress
        compressed = rs.as_compressed_data()
        restored = RollingState.from_compressed_data(compressed)

        assert restored.email == rs.email
        assert restored.base_checkpoint_timestamp == rs.base_checkpoint_timestamp
        assert restored.event_count == rs.event_count
        assert restored.last_event_timestamp == rs.last_event_timestamp


class TestRollingStateInMemoryConnection:
    """Tests for RollingState in the in-memory connection."""

    def test_upload_and_get_rolling_state(self):
        """Test uploading and retrieving rolling state from in-memory store."""
        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()

        # Create a rolling state
        rs = RollingState(
            email=do_manager.email,
            base_checkpoint_timestamp=time.time(),
        )
        event = get_mock_event(f"{do_manager.email}/file1.txt")
        rs.add_event(event)

        # Upload
        do_manager.connection_router.upload_rolling_state(rs)

        # Retrieve
        retrieved = do_manager.connection_router.get_rolling_state()
        assert retrieved is not None
        assert retrieved.email == rs.email
        assert retrieved.event_count == rs.event_count

    def test_delete_rolling_state(self):
        """Test deleting rolling state from in-memory store."""
        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()

        # Create and upload a rolling state
        rs = RollingState(
            email=do_manager.email,
            base_checkpoint_timestamp=time.time(),
        )
        do_manager.connection_router.upload_rolling_state(rs)

        # Verify it exists
        assert do_manager.connection_router.get_rolling_state() is not None

        # Delete
        do_manager.connection_router.delete_rolling_state()

        # Verify it's gone
        assert do_manager.connection_router.get_rolling_state() is None

    def test_upload_replaces_existing(self):
        """Test that uploading rolling state replaces existing one."""
        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()

        # Create and upload first rolling state
        rs1 = RollingState(
            email=do_manager.email,
            base_checkpoint_timestamp=1000.0,
        )
        do_manager.connection_router.upload_rolling_state(rs1)

        # Create and upload second rolling state
        rs2 = RollingState(
            email=do_manager.email,
            base_checkpoint_timestamp=2000.0,
        )
        do_manager.connection_router.upload_rolling_state(rs2)

        # Verify only one exists and it's the second one
        retrieved = do_manager.connection_router.get_rolling_state()
        assert retrieved is not None
        assert retrieved.base_checkpoint_timestamp == 2000.0


class TestRollingStateIntegration:
    """Integration tests for rolling state with checkpoint functionality."""

    def test_rolling_state_created_after_checkpoint(self):
        """Test that rolling state is accumulated after checkpoint creation."""
        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()

        # Send some events
        ds_manager.send_file_change(f"{do_manager.email}/file1.txt", "content1")
        ds_manager.send_file_change(f"{do_manager.email}/file2.txt", "content2")

        # DO syncs and creates checkpoint
        do_manager.sync(auto_checkpoint=False)
        do_manager.create_checkpoint()

        # Send more events after checkpoint
        ds_manager.send_file_change(f"{do_manager.email}/file3.txt", "content3")
        ds_manager.send_file_change(f"{do_manager.email}/file4.txt", "content4")

        # DO syncs again
        do_manager.sync(auto_checkpoint=False)

        # Verify rolling state exists and has the new events
        rs = do_manager.connection_router.get_rolling_state()
        assert rs is not None
        assert rs.event_count == 2  # file3 and file4

    def test_fresh_login_uses_checkpoint_and_rolling_state(self):
        """Test that fresh login downloads checkpoint + rolling state instead of all events.

        This test verifies that:
        1. Checkpoint is downloaded and applied
        2. Rolling state is downloaded and applied
        3. No additional event downloads are needed when rolling state is current
        """
        from syft_client.sync.syftbox_manager import SyftboxManagerConfig
        from syft_client.sync.connections.inmemory_connection import (
            InMemoryPlatformConnection,
        )

        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()
        store: InMemoryBackingPlatform = do_manager.connection_router.connections[
            0
        ].backing_store
        do_email = do_manager.email

        # Send events and create checkpoint
        ds_manager.send_file_change(f"{do_manager.email}/file1.txt", "content1")
        ds_manager.send_file_change(f"{do_manager.email}/file2.txt", "content2")
        do_manager.sync(auto_checkpoint=False)
        do_manager.create_checkpoint()

        # Verify checkpoint exists with 2 files
        checkpoint = store.checkpoints[-1]
        assert len(checkpoint.files) == 2

        # Send more events after checkpoint
        ds_manager.send_file_change(f"{do_manager.email}/file3.txt", "content3")
        do_manager.sync(auto_checkpoint=False)

        # Verify rolling state exists
        rolling_state = do_manager.connection_router.get_rolling_state()
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
        fresh_do.add_connection(fresh_do_connection)

        # Track how many individual events are downloaded
        download_count = 0
        original_download = fresh_do.proposed_file_change_handler.download_events_message_by_id_with_connection

        def counted_download(event_id):
            nonlocal download_count
            download_count += 1
            return original_download(event_id)

        fresh_do.proposed_file_change_handler.download_events_message_by_id_with_connection = counted_download

        # Sync should use checkpoint + rolling state
        fresh_do.sync(auto_checkpoint=False)

        # With rolling state, we shouldn't need to download individual events
        # because rolling state contains them
        assert download_count == 0, (
            f"Expected 0 individual event downloads (rolling state should contain them), "
            f"but got {download_count}"
        )

        # Verify checkpoint files are in the cache (at minimum)
        cache = fresh_do.proposed_file_change_handler.event_cache
        assert len(cache.file_hashes) >= 2, (
            f"Expected at least 2 files from checkpoint, got {len(cache.file_hashes)}"
        )

    def test_checkpoint_resets_rolling_state(self):
        """Test that creating a new checkpoint resets the rolling state."""
        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()

        # Send events and create checkpoint
        ds_manager.send_file_change(f"{do_manager.email}/file1.txt", "content1")
        do_manager.sync(auto_checkpoint=False)
        do_manager.create_checkpoint()

        # Send more events
        ds_manager.send_file_change(f"{do_manager.email}/file2.txt", "content2")
        ds_manager.send_file_change(f"{do_manager.email}/file3.txt", "content3")
        do_manager.sync(auto_checkpoint=False)

        # Verify rolling state has 2 events
        rs = do_manager.connection_router.get_rolling_state()
        assert rs is not None
        assert rs.event_count == 2

        # Create another checkpoint
        do_manager.create_checkpoint()

        # Rolling state should be deleted/reset
        rs = do_manager.connection_router.get_rolling_state()
        # It may be None (deleted) or empty (reset)
        assert rs is None or rs.event_count == 0
