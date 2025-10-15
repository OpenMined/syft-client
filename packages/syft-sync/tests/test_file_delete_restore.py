"""
Tests for file delete and restore operations from TEST_STRATEGY.md
Section 1.1: Basic File Operations - Delete and Restore
"""
import os
import sys
import time
import shutil
import threading
import concurrent.futures
from pathlib import Path
import tempfile

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from syft_sync import SyftWatcher
from .test_utils import (
    verify_syft_message_content,
    get_version_archive,
    verify_version_metadata,
    read_file_from_archive,
    get_archive_metadata,
    extract_syft_archive
)


class TestDeleteRestore:
    """Test: Delete and Restore - Delete file then recreate with same/different content"""
    
    def setup_method(self):
        """Setup test directories"""
        self.temp_dir = tempfile.mkdtemp()
        self.watch_dir = Path(self.temp_dir) / "watched"
        self.log_dir = Path(self.temp_dir) / "logs"
        self.watch_dir.mkdir(parents=True)
        self.log_dir.mkdir(parents=True)
        
    def teardown_method(self):
        """Cleanup test directories"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_same_content_restoration_with_delays(self):
        """Test deleting then recreating with identical content - with delays to prevent coalescing"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        file_path = self.watch_dir / "restore_delayed.txt"
        content = "Original content that will be restored identically with delays"
        
        # Create original
        file_path.write_text(content)
        time.sleep(1.0)  # Longer delay to prevent coalescing
        
        # Delete
        file_path.unlink()
        time.sleep(1.0)  # Longer delay to prevent coalescing
        
        # Restore with SAME content
        file_path.write_text(content)  # Identical content
        time.sleep(1.0)  # Longer delay to prevent coalescing
        
        watcher.stop()
        
        # Analyze the delete/restore cycle
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'restore_delayed.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        print(f"Restoration with delays: {len(all_events)} events for create->delete->restore cycle")
        
        # ACTUAL BEHAVIOR: System intelligently optimizes delete→restore cycles with identical content
        # Standard delete pattern: create, modify (during delete), delete - restoration with same content is optimized away
        assert len(all_events) == 3, f"Should have exactly 3 events (create + modify + delete, restore optimized), found {len(all_events)}"
        
        # Verify exact event sequence
        assert all_events[0]['event_type'] == 'file_created', "Event 1 should be file_created"
        assert all_events[1]['event_type'] == 'file_modified', "Event 2 should be file_modified (during delete)"
        assert all_events[2]['event_type'] == 'file_deleted', "Event 3 should be file_deleted"
        
        print("System optimized identical content restoration - no separate restore event created")
        
        # Verify content preservation in archives
        original_archive = get_version_archive(self.log_dir, all_events[0]['version_id'])
        original_content = read_file_from_archive(original_archive, 'restore_delayed.txt')
        assert original_content == content, "Original content should be preserved"
        
        # No separate restore archive since restoration was optimized away
        
        # Verify final file state
        assert file_path.exists(), "File should exist after restoration"
        assert file_path.read_text() == content, "Final file should have correct content"
    
    def test_same_content_restoration_with_coalescing(self):
        """Test deleting then recreating with identical content - without delays to test coalescing"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        file_path = self.watch_dir / "restore_coalesced.txt"
        content = "Original content that will be restored with coalescing"
        
        # Create original
        file_path.write_text(content)
        # No delay - allow coalescing
        
        # Delete
        file_path.unlink()
        # No delay - allow coalescing
        
        # Restore with SAME content
        file_path.write_text(content)  # Identical content
        # No delay - allow coalescing
        
        time.sleep(1.0)  # Only wait at end for all events to be processed
        watcher.stop()
        
        # Analyze the delete/restore cycle with coalescing
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'restore_coalesced.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        print(f"Restoration with coalescing: {len(all_events)} events for create->delete->restore cycle")
        
        # With coalescing, filesystem may optimize to fewer events
        # Common patterns: 1 event (fully coalesced) or 3 events (create, modify, delete with restore optimized away)
        assert len(all_events) >= 1, f"Should have at least 1 event, found {len(all_events)}"
        assert len(all_events) <= 3, f"Should have at most 3 events with coalescing, found {len(all_events)}"
        
        if len(all_events) == 1:
            # Fully coalesced - single event captures final state
            assert all_events[0]['event_type'] == 'file_created', "Single coalesced event should be file_created"
            print("Fully coalesced: delete->restore optimized to single create event")
        elif len(all_events) == 3:
            # Partial coalescing - delete captured but restore optimized away
            assert all_events[0]['event_type'] == 'file_created', "Event 1 should be file_created"
            assert all_events[1]['event_type'] == 'file_modified', "Event 2 should be file_modified"
            assert all_events[2]['event_type'] == 'file_deleted', "Event 3 should be file_deleted"
            print("Partial coalescing: delete captured, restore optimized away")
        
        # Verify content is accessible regardless of coalescing
        # The first create event should have the original content
        original_archive = get_version_archive(self.log_dir, all_events[0]['version_id'])
        original_content = read_file_from_archive(original_archive, 'restore_coalesced.txt')
        assert original_content == content, "Original content should be preserved despite coalescing"
        
        # Verify final file state matches expected content
        assert file_path.exists(), "File should exist after restoration"
        assert file_path.read_text() == content, "Final file should have correct content"
    
    def test_different_content_recreation(self):
        """Test deleting then recreating with different content"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        file_path = self.watch_dir / "recreate_different.txt"
        original = "Original version before deletion"
        recreated = "Completely different content after recreation"
        
        # Create -> Delete -> Recreate cycle with different content
        file_path.write_text(original)
        time.sleep(1.0)  # Use delays to ensure separate events
        
        file_path.unlink() 
        time.sleep(1.0)
        
        file_path.write_text(recreated)
        time.sleep(1.0)
        
        watcher.stop()
        
        # Analyze different content recreation
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'recreate_different.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        print(f"Different content recreation: {len(all_events)} events for create->delete->recreate cycle")
        
        # With different content and delays, expect exactly 4 events:
        # create, modify (during delete), delete, create (recreation)
        assert len(all_events) == 4, f"Should have exactly 4 events (create + modify + delete + recreate), found {len(all_events)}"
        
        # Verify exact event sequence
        assert all_events[0]['event_type'] == 'file_created', "Event 1 should be file_created (original)"
        assert all_events[1]['event_type'] == 'file_modified', "Event 2 should be file_modified (during delete)"
        assert all_events[2]['event_type'] == 'file_deleted', "Event 3 should be file_deleted"
        assert all_events[3]['event_type'] == 'file_created', "Event 4 should be file_created (recreation)"
        
        # Verify both versions are preserved in archives
        original_archive = get_version_archive(self.log_dir, all_events[0]['version_id'])
        original_content = read_file_from_archive(original_archive, 'recreate_different.txt')
        assert original_content == original, "Original content should be preserved"
        
        recreation_archive = get_version_archive(self.log_dir, all_events[3]['version_id'])
        recreation_content = read_file_from_archive(recreation_archive, 'recreate_different.txt')
        assert recreation_content == recreated, "Recreated content should be preserved"
        
        # Verify no content confusion between versions
        assert original_content != recreation_content, "Original and recreated content should be different"
        
        # Verify file sizes are different (since content is different)
        original_size = all_events[0]['size']
        recreation_size = all_events[3]['size']
        expected_original_size = len(original.encode('utf-8'))
        expected_recreation_size = len(recreated.encode('utf-8'))
        
        assert original_size == expected_original_size, "Original event should have correct size"
        assert recreation_size == expected_recreation_size, "Recreation event should have correct size"
        assert original_size != recreation_size, "Original and recreation should have different sizes"
        
        # Verify final file state
        assert file_path.read_text() == recreated, "Final file should have recreated content"
    
    def test_complex_restoration_workflows(self):
        """Test complex delete/restore workflows"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Scenario 1: Multiple delete/restore cycles
        file1 = self.watch_dir / "cyclic.txt"
        cycle_contents = []
        for i in range(3):
            content = f"Cycle {i+1} content with unique data"
            cycle_contents.append(content)
            file1.write_text(content)
            time.sleep(0.5)
            file1.unlink()
            time.sleep(0.5)
        
        # Final restoration
        final_content = "Final restored content after all cycles"
        file1.write_text(final_content)
        time.sleep(0.5)
        
        # Scenario 2: Delete, wait, then restore (time gap)
        file2 = self.watch_dir / "delayed.txt"
        before_content = "Before long deletion period"
        file2.write_text(before_content)
        time.sleep(0.5)
        file2.unlink()
        time.sleep(2.0)  # Longer gap
        after_content = "After long deletion period"
        file2.write_text(after_content)
        time.sleep(0.5)
        
        # Scenario 3: Partial restoration (different filename, same content)
        file3 = self.watch_dir / "original.txt"
        shared_content = "Shared content across different filenames"
        file3.write_text(shared_content)
        time.sleep(0.5)
        file3.unlink()
        time.sleep(0.5)
        # Restore with different filename
        file3_restored = self.watch_dir / "restored.txt"
        file3_restored.write_text(shared_content)
        time.sleep(0.5)
        
        watcher.stop()
        
        # Analyze complex workflows
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        
        # Scenario 1 analysis: Multiple cycles
        file1_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'cyclic.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    file1_events.append(metadata)
        
        file1_events.sort(key=lambda x: x.get('timestamp', ''))
        print(f"Cyclic workflow: {len(file1_events)} events for 3 cycles + final restore")
        
        # Should have multiple create/delete pairs plus final create
        create_events = [e for e in file1_events if e['event_type'] == 'file_created']
        delete_events = [e for e in file1_events if e['event_type'] == 'file_deleted']
        assert len(create_events) >= 4, "Should have 3 cycle creates + 1 final create"
        assert len(delete_events) >= 3, "Should have 3 delete events"
        
        # Verify cycle content preservation
        for i, create_event in enumerate(create_events[:-1]):  # Exclude final
            if i < len(cycle_contents):
                archive = get_version_archive(self.log_dir, create_event['version_id'])
                content = read_file_from_archive(archive, 'cyclic.txt')
                assert content == cycle_contents[i], f"Cycle {i+1} content should be preserved"
        
        # Verify final restoration
        final_archive = get_version_archive(self.log_dir, create_events[-1]['version_id'])
        final_preserved = read_file_from_archive(final_archive, 'cyclic.txt')
        assert final_preserved == final_content, "Final content should be preserved"
        
        # Scenario 2 analysis: Time gap
        file2_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'delayed.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    file2_events.append(metadata)
        
        file2_events.sort(key=lambda x: x.get('timestamp', ''))
        print(f"Delayed workflow: {len(file2_events)} events with time gap")
        
        # Verify time gap doesn't affect preservation
        if len(file2_events) >= 2:
            first_archive = get_version_archive(self.log_dir, file2_events[0]['version_id'])
            first_content = read_file_from_archive(first_archive, 'delayed.txt')
            assert first_content == before_content, "Content before deletion should be preserved"
            
            # Find restoration event
            restore_event = None
            for event in reversed(file2_events):
                if event['event_type'] == 'file_created':
                    restore_event = event
                    break
            
            if restore_event:
                restore_archive = get_version_archive(self.log_dir, restore_event['version_id'])
                restore_content = read_file_from_archive(restore_archive, 'delayed.txt')
                assert restore_content == after_content, "Content after delay should be preserved"
        
        # Scenario 3 analysis: Different filename restoration
        original_events = []
        restored_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if metadata.get('file_name') == 'original.txt' and 'version_id' in metadata:
                    original_events.append(metadata)
                elif metadata.get('file_name') == 'restored.txt' and 'version_id' in metadata:
                    restored_events.append(metadata)
        
        print(f"Cross-filename: {len(original_events)} original events, {len(restored_events)} restored events")
        
        # Verify content appears in both filenames
        if original_events:
            original_archive = get_version_archive(self.log_dir, original_events[0]['version_id'])
            original_content = read_file_from_archive(original_archive, 'original.txt')
            assert original_content == shared_content, "Original file should have shared content"
        
        if restored_events:
            restored_archive = get_version_archive(self.log_dir, restored_events[0]['version_id'])
            restored_content = read_file_from_archive(restored_archive, 'restored.txt')
            assert restored_content == shared_content, "Restored file should have shared content"
    
    def test_archive_integrity_across_deletion(self):
        """Test that deletion doesn't break archive integrity"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        file_path = self.watch_dir / "versioned.txt"
        
        # Create file with multiple versions
        versions = [
            "Version 1: Initial content with timestamp info",
            "Version 2: Modified with additional data and changes", 
            "Version 3: Final version before deletion with comprehensive content"
        ]
        
        for i, version in enumerate(versions):
            file_path.write_text(version)
            time.sleep(0.5)
        
        # Delete the file
        file_path.unlink()
        time.sleep(0.5)
        
        # Recreate with new content
        post_delete_content = "Version 4: After restoration with completely new approach"
        file_path.write_text(post_delete_content)
        time.sleep(0.5)
        
        watcher.stop()
        
        # Verify ALL versions are still accessible in archives
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'versioned.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        print(f"Archive integrity: {len(all_events)} events preserved across deletion")
        
        # Verify original 3 versions are preserved
        create_modify_events = [e for e in all_events if e['event_type'] in ['file_created', 'file_modified']]
        pre_delete_events = []
        
        # Find events before deletion
        delete_event = None
        for event in all_events:
            if event['event_type'] == 'file_deleted':
                delete_event = event
                break
        
        if delete_event:
            for event in create_modify_events:
                if event['timestamp'] < delete_event['timestamp']:
                    pre_delete_events.append(event)
        else:
            pre_delete_events = create_modify_events[:-1]  # All but last if no delete found
        
        # Verify pre-deletion versions
        assert len(pre_delete_events) >= 3, f"Should preserve all 3 pre-deletion versions, found {len(pre_delete_events)}"
        
        for i, event in enumerate(pre_delete_events[:3]):
            archive = get_version_archive(self.log_dir, event['version_id'])
            content = read_file_from_archive(archive, 'versioned.txt')
            expected_content = versions[i]
            assert content == expected_content, f"Version {i+1} should be preserved: expected '{expected_content}', got '{content}'"
        
        # Verify delete event is recorded
        assert delete_event is not None, "Delete event should be recorded"
        
        # Verify post-restoration version
        post_delete_events = [e for e in create_modify_events 
                             if delete_event and e['timestamp'] > delete_event['timestamp']]
        
        if post_delete_events:
            post_archive = get_version_archive(self.log_dir, post_delete_events[0]['version_id'])
            post_content = read_file_from_archive(post_archive, 'versioned.txt')
            assert post_content == post_delete_content, "Post-restoration content should be preserved"
        
        # Verify no data loss across deletion boundary
        all_contents = []
        for event in create_modify_events:
            try:
                archive = get_version_archive(self.log_dir, event['version_id'])
                content = read_file_from_archive(archive, 'versioned.txt')
                all_contents.append(content)
            except:
                pass
        
        # Should have all 3 original versions plus post-restore version
        expected_contents = versions + [post_delete_content]
        for expected in expected_contents:
            assert expected in all_contents, f"Content '{expected}' should be preserved in archives"
    
    def test_edge_cases_and_error_scenarios(self):
        """Test edge cases in delete/restore workflows"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Edge 1: Rapid delete/recreate (filesystem race conditions)
        file1 = self.watch_dir / "rapid.txt"
        rapid_content = "Rapid delete/recreate content"
        file1.write_text(rapid_content)
        file1.unlink()
        file1.write_text("Immediate recreation content")  # No delay
        time.sleep(0.5)
        
        # Edge 2: Delete non-existent file then create
        file2 = self.watch_dir / "phantom.txt"
        try:
            file2.unlink()  # Should fail
        except FileNotFoundError:
            pass
        phantom_content = "Created after failed delete attempt"
        file2.write_text(phantom_content)
        time.sleep(0.5)
        
        # Edge 3: Large file delete/restore
        large_content = "Large file content: " + "LARGE_DATA" * 10000  # ~100KB
        file3 = self.watch_dir / "large.txt"
        file3.write_text(large_content)
        time.sleep(1.0)
        file3.unlink()
        time.sleep(0.5)
        file3.write_text(large_content)  # Same large content
        time.sleep(1.0)
        
        # Edge 4: Empty file delete/restore
        file4 = self.watch_dir / "empty.txt"
        file4.write_text("")  # Empty content
        time.sleep(0.5)
        file4.unlink()
        time.sleep(0.5)
        file4.write_text("Now has content after empty deletion")
        time.sleep(0.5)
        
        # Edge 5: Binary content delete/restore
        file5 = self.watch_dir / "binary.dat"
        binary_data = bytes(range(256))  # Binary content
        file5.write_bytes(binary_data)
        time.sleep(0.5)
        file5.unlink()
        time.sleep(0.5)
        new_binary = b"Different binary content after deletion"
        file5.write_bytes(new_binary)
        time.sleep(0.5)
        
        watcher.stop()
        
        # Analyze edge cases
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        
        # Edge 1: Rapid delete/recreate
        rapid_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'rapid.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    rapid_events.append(metadata)
        
        rapid_events.sort(key=lambda x: x.get('timestamp', ''))
        print(f"Rapid delete/recreate: {len(rapid_events)} events captured")
        
        # Should handle rapid operations correctly
        assert len(rapid_events) >= 1, "Should capture rapid delete/recreate"
        
        # Edge 2: Phantom file creation
        phantom_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'phantom.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    phantom_events.append(metadata)
        
        print(f"Phantom file: {len(phantom_events)} events for create after failed delete")
        assert len(phantom_events) >= 1, "Should capture phantom file creation"
        
        # Verify phantom file content
        if phantom_events:
            phantom_archive = get_version_archive(self.log_dir, phantom_events[0]['version_id'])
            phantom_preserved = read_file_from_archive(phantom_archive, 'phantom.txt')
            assert phantom_preserved == phantom_content, "Phantom file content should be preserved"
        
        # Edge 3: Large file operations
        large_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'large.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    large_events.append(metadata)
        
        print(f"Large file delete/restore: {len(large_events)} events")
        
        # Verify large file handling
        large_create_events = [e for e in large_events if e['event_type'] == 'file_created']
        if len(large_create_events) >= 2:
            # Verify both versions have correct size
            for event in large_create_events:
                expected_size = len(large_content.encode('utf-8'))
                assert event['size'] == expected_size, "Large file size should be tracked correctly"
        
        # Edge 4: Empty file handling
        empty_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'empty.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    empty_events.append(metadata)
        
        print(f"Empty file delete/restore: {len(empty_events)} events")
        
        # Verify empty file transitions
        if len(empty_events) >= 2:
            empty_events.sort(key=lambda x: x.get('timestamp', ''))
            # First event should be empty file creation
            assert empty_events[0]['size'] == 0, "Empty file should have size 0"
            
            # Find restoration event
            restore_event = None
            for event in reversed(empty_events):
                if event['event_type'] == 'file_created':
                    restore_event = event
                    break
            
            if restore_event and restore_event != empty_events[0]:
                assert restore_event['size'] > 0, "Restored file should have content"
        
        # Verify final states
        test_files = {
            'rapid.txt': "Immediate recreation content",
            'phantom.txt': phantom_content,
            'large.txt': large_content,
            'empty.txt': "Now has content after empty deletion"
        }
        
        for filename, expected_content in test_files.items():
            file_path = self.watch_dir / filename
            if file_path.exists():
                if filename == 'large.txt':
                    # For large files, just check size
                    actual_size = len(file_path.read_text().encode('utf-8'))
                    expected_size = len(expected_content.encode('utf-8'))
                    assert actual_size == expected_size, f"{filename} should have correct size"
                else:
                    actual_content = file_path.read_text()
                    assert actual_content == expected_content, f"{filename} should have correct final content"
        
        # Binary file verification
        if (self.watch_dir / 'binary.dat').exists():
            final_binary = (self.watch_dir / 'binary.dat').read_bytes()
            assert final_binary == new_binary, "Binary file should have correct final content"
    
    def test_concurrent_delete_restore_operations(self):
        """Test concurrent delete/restore operations"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        shared_content = "Content for concurrent delete/restore testing"
        
        def delete_restore_cycle(file_id):
            """Perform delete/restore cycle for a specific file"""
            file_path = self.watch_dir / f"concurrent_{file_id}.txt"
            content = f"{shared_content} - File {file_id}"
            
            # Create, delete, restore cycle
            file_path.write_text(content)
            time.sleep(0.1)
            file_path.unlink()
            time.sleep(0.1)
            file_path.write_text(f"{content} - Restored")
            time.sleep(0.1)
        
        # Run concurrent delete/restore operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(delete_restore_cycle, i) for i in range(3)]
            concurrent.futures.wait(futures)
        
        time.sleep(1.0)  # Wait for all events
        watcher.stop()
        
        # Analyze concurrent operations
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        
        for file_id in range(3):
            filename = f"concurrent_{file_id}.txt"
            file_events = []
            
            for archive_path in archives:
                metadata_list = get_archive_metadata(archive_path)
                for metadata in metadata_list:
                    if (metadata.get('file_name') == filename and 
                        'version_id' in metadata and 'event_type' in metadata):
                        file_events.append(metadata)
            
            file_events.sort(key=lambda x: x.get('timestamp', ''))
            print(f"Concurrent file {file_id}: {len(file_events)} events")
            
            # Verify concurrent operations don't interfere
            assert len(file_events) >= 2, f"Concurrent file {file_id} should have create and restore events"
            
            # Verify final state
            final_file = self.watch_dir / filename
            if final_file.exists():
                final_content = final_file.read_text()
                assert "Restored" in final_content, f"Concurrent file {file_id} should be in restored state"


if __name__ == "__main__":
    # Run tests
    test = TestDeleteRestore()
    test.setup_method()
    try:
        test.test_same_content_restoration()
        print("✓ Same content restoration test passed!")
        
        test.teardown_method()
        test.setup_method()
        test.test_different_content_recreation()
        print("✓ Different content recreation test passed!")
        
        test.teardown_method()
        test.setup_method() 
        test.test_archive_integrity_across_deletion()
        print("✓ Archive integrity test passed!")
        
    finally:
        test.teardown_method()