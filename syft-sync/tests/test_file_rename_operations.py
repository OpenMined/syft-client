"""
Tests for file rename/move operations
Testing various rename and move scenarios
"""
import os
import sys
import time
import shutil
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


class TestRenameFile:
    """Test: Rename/Move File - File rename operations"""
    
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
    
    def test_simple_rename_same_directory(self):
        """Test 1: Simple rename within same directory"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Create original file
        original_path = self.watch_dir / "original.txt"
        content = "Content that will be renamed"
        original_path.write_text(content)
        time.sleep(0.5)
        
        # Rename the file
        new_path = self.watch_dir / "renamed.txt"
        original_path.rename(new_path)
        time.sleep(0.5)
        
        watcher.stop()
        
        # Analyze rename operation
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if 'version_id' in metadata and 'event_type' in metadata:
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        print(f"Simple rename: {len(all_events)} events total")
        
        # Verify events
        # Should see: create original, modify (during move), move
        original_events = [e for e in all_events if e.get('file_name') == 'original.txt']
        renamed_events = [e for e in all_events if e.get('file_name') == 'renamed.txt']
        
        print(f"Original file events: {[e['event_type'] for e in original_events]}")
        print(f"Renamed file events: {[e['event_type'] for e in renamed_events]}")
        
        # Find move event to get new filename
        move_events = [e for e in all_events if e.get('event_type') == 'file_moved']
        assert len(move_events) >= 1, "Should have at least one move event"
        
        # Verify the move event has proper metadata
        move_event = move_events[0]
        assert 'old_path' in move_event or 'file_name' in move_event, "Move event should track paths"
        
        # Verify exact event sequence for simple rename
        assert len(original_events) == 3, "Should have exactly 3 events for original file"
        assert original_events[0]['event_type'] == 'file_created', "First event should be create"
        assert original_events[1]['event_type'] == 'file_modified', "Second event should be modify"
        assert original_events[2]['event_type'] == 'file_moved', "Third event should be move"
        
        # Verify content is preserved through the rename
        # The original file's content should be captured in the create event
        if original_events:
            create_archive = get_version_archive(self.log_dir, original_events[0]['version_id'])
            create_content = read_file_from_archive(create_archive, 'original.txt')
            assert create_content == content, "Original content should be preserved"
        
        # Verify final state
        assert not original_path.exists(), "Original file should not exist"
        assert new_path.exists(), "Renamed file should exist"
        assert new_path.read_text() == content, "Renamed file should have correct content"
    
    def test_move_to_subdirectory(self):
        """Test 2: Move file to subdirectory"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Create subdirectory
        subdir = self.watch_dir / "subdir"
        subdir.mkdir()
        time.sleep(0.5)
        
        # Create file in root
        original_path = self.watch_dir / "moveme.txt"
        content = "File to be moved to subdirectory"
        original_path.write_text(content)
        time.sleep(0.5)
        
        # Move to subdirectory
        new_path = subdir / "moved.txt"
        original_path.rename(new_path)
        time.sleep(0.5)
        
        watcher.stop()
        
        # Analyze move operation
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if 'version_id' in metadata and 'event_type' in metadata:
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        print(f"Move to subdir: {len(all_events)} events total")
        
        # Check for events on both paths
        original_events = [e for e in all_events if e.get('file_name') == 'moveme.txt']
        moved_events = [e for e in all_events if e.get('file_name') == 'subdir/moved.txt']
        
        print(f"Original location events: {[e['event_type'] for e in original_events]}")
        print(f"New location events: {[e['event_type'] for e in moved_events]}")
        
        # Verify content preservation
        if moved_events:
            for event in moved_events:
                if event['event_type'] == 'file_created':
                    moved_archive = get_version_archive(self.log_dir, event['version_id'])
                    moved_content = read_file_from_archive(moved_archive, 'subdir/moved.txt')
                    assert moved_content == content, "Content should be preserved after move"
                    break
        
        # Verify final state
        assert not original_path.exists(), "Original location should not exist"
        assert new_path.exists(), "New location should exist"
        assert new_path.read_text() == content, "Moved file should have correct content"
    
    def test_complex_rename_scenarios(self):
        """Test 3: Complex rename scenarios including chains and swaps"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Scenario 1: Chain rename (A→B→C)
        file_a = self.watch_dir / "file_a.txt"
        content_a = "Original content A"
        file_a.write_text(content_a)
        time.sleep(0.5)
        
        # First rename A→B
        file_b = self.watch_dir / "file_b.txt"
        file_a.rename(file_b)
        time.sleep(0.5)
        
        # Second rename B→C
        file_c = self.watch_dir / "file_c.txt"
        file_b.rename(file_c)
        time.sleep(0.5)
        
        # Scenario 2: Swap names (X↔Y using temp)
        file_x = self.watch_dir / "file_x.txt"
        file_y = self.watch_dir / "file_y.txt"
        content_x = "Original content X"
        content_y = "Original content Y"
        
        file_x.write_text(content_x)
        time.sleep(0.5)
        file_y.write_text(content_y)
        time.sleep(0.5)
        
        # Swap using temp name
        file_temp = self.watch_dir / "file_temp.txt"
        file_x.rename(file_temp)  # X→temp
        time.sleep(0.5)
        file_y.rename(file_x)     # Y→X
        time.sleep(0.5)
        file_temp.rename(file_y)  # temp→Y
        time.sleep(0.5)
        
        # Scenario 3: Rename with extension change
        file_txt = self.watch_dir / "document.txt"
        content_doc = "Document content"
        file_txt.write_text(content_doc)
        time.sleep(0.5)
        
        file_md = self.watch_dir / "document.md"
        file_txt.rename(file_md)
        time.sleep(0.5)
        
        # Scenario 4: Case-only rename (if filesystem is case-sensitive)
        file_lower = self.watch_dir / "casefile.txt"
        content_case = "Case sensitive content"
        file_lower.write_text(content_case)
        time.sleep(0.5)
        
        file_upper = self.watch_dir / "CASEFILE.txt"
        try:
            file_lower.rename(file_upper)
            time.sleep(0.5)
            case_rename_success = True
        except:
            # Filesystem might be case-insensitive
            case_rename_success = False
        
        watcher.stop()
        
        # Analyze all operations
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if 'version_id' in metadata and 'event_type' in metadata:
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        
        # Verify chain rename preserved content
        file_c_events = [e for e in all_events if e.get('file_name') == 'file_c.txt']
        if file_c_events:
            for event in file_c_events:
                if event['event_type'] == 'file_created':
                    c_archive = get_version_archive(self.log_dir, event['version_id'])
                    c_content = read_file_from_archive(c_archive, 'file_c.txt')
                    assert c_content == content_a, "Chain rename should preserve original content"
                    break
        
        # Verify swap preserved both contents
        final_x_content = file_x.read_text()
        final_y_content = file_y.read_text()
        assert final_x_content == content_y, "X should have Y's original content after swap"
        assert final_y_content == content_x, "Y should have X's original content after swap"
        
        # Verify extension change preserved content
        assert file_md.exists(), "File with new extension should exist"
        assert file_md.read_text() == content_doc, "Extension change should preserve content"
        
        # Report on case rename if it succeeded
        if case_rename_success:
            assert file_upper.exists(), "Case-renamed file should exist"
            assert file_upper.read_text() == content_case, "Case rename should preserve content"
        
        print(f"Complex scenarios: {len(all_events)} total events")
        print(f"Chain rename: A→B→C completed")
        print(f"Swap rename: X↔Y completed")
        print(f"Extension change: .txt→.md completed")
        print(f"Case rename: {'completed' if case_rename_success else 'skipped (case-insensitive FS)'}")
    
    def test_rapid_rename_operations(self):
        """Test rapid rename operations with and without delays"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Test 1: Rapid renames without delays
        rapid_file = self.watch_dir / "rapid_0.txt"
        content = "Content for rapid rename testing"
        rapid_file.write_text(content)
        
        # Rapid rename chain without delays
        for i in range(1, 5):
            new_name = self.watch_dir / f"rapid_{i}.txt"
            old_name = self.watch_dir / f"rapid_{i-1}.txt"
            old_name.rename(new_name)
        
        time.sleep(1.0)  # Wait for events to be processed
        
        # Test 2: Renames with delays
        delayed_file = self.watch_dir / "delayed_0.txt"
        delayed_file.write_text(content)
        time.sleep(0.5)
        
        # Rename chain with delays
        for i in range(1, 5):
            new_name = self.watch_dir / f"delayed_{i}.txt"
            old_name = self.watch_dir / f"delayed_{i-1}.txt"
            old_name.rename(new_name)
            time.sleep(0.3)
        
        watcher.stop()
        
        # Analyze events
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        rapid_events = []
        delayed_events = []
        
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if 'rapid_' in metadata.get('file_name', ''):
                    rapid_events.append(metadata)
                elif 'delayed_' in metadata.get('file_name', ''):
                    delayed_events.append(metadata)
        
        print(f"Rapid renames (no delays): {len(rapid_events)} events")
        print(f"Delayed renames: {len(delayed_events)} events")
        
        # Verify final files exist with correct content
        assert (self.watch_dir / "rapid_4.txt").exists(), "Final rapid file should exist"
        assert (self.watch_dir / "rapid_4.txt").read_text() == content, "Content should be preserved"
        
        assert (self.watch_dir / "delayed_4.txt").exists(), "Final delayed file should exist"
        assert (self.watch_dir / "delayed_4.txt").read_text() == content, "Content should be preserved"
    
    def test_rename_edge_cases(self):
        """Test edge cases for rename operations"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Edge case 1: Rename to name with spaces
        file1 = self.watch_dir / "nospace.txt"
        file1.write_text("Content 1")
        time.sleep(0.5)
        
        spaced_name = self.watch_dir / "with spaces in name.txt"
        file1.rename(spaced_name)
        time.sleep(0.5)
        
        # Edge case 2: Rename to name with special characters
        file2 = self.watch_dir / "normal.txt"
        file2.write_text("Content 2")
        time.sleep(0.5)
        
        special_name = self.watch_dir / "special_#@$_chars.txt"
        file2.rename(special_name)
        time.sleep(0.5)
        
        # Edge case 3: Very long filename
        file3 = self.watch_dir / "short.txt"
        file3.write_text("Content 3")
        time.sleep(0.5)
        
        long_name = self.watch_dir / ("very_long_filename_" + "x" * 200 + ".txt")
        try:
            file3.rename(long_name)
            time.sleep(0.5)
            long_rename_success = True
        except:
            long_rename_success = False
        
        # Edge case 4: Rename directory with files
        test_dir = self.watch_dir / "test_directory"
        test_dir.mkdir()
        (test_dir / "file_inside.txt").write_text("Inside content")
        time.sleep(0.5)
        
        renamed_dir = self.watch_dir / "renamed_directory"
        test_dir.rename(renamed_dir)
        time.sleep(0.5)
        
        watcher.stop()
        
        # Verify edge cases
        assert spaced_name.exists(), "File with spaces should exist"
        assert spaced_name.read_text() == "Content 1", "Content preserved with spaces"
        
        assert special_name.exists(), "File with special chars should exist"
        assert special_name.read_text() == "Content 2", "Content preserved with special chars"
        
        if long_rename_success:
            assert long_name.exists(), "Long filename should exist"
            assert long_name.read_text() == "Content 3", "Content preserved with long name"
        
        assert renamed_dir.exists(), "Renamed directory should exist"
        assert (renamed_dir / "file_inside.txt").exists(), "File inside renamed dir should exist"
        assert (renamed_dir / "file_inside.txt").read_text() == "Inside content", "Content inside dir preserved"
    
    def test_rename_with_content_changes(self):
        """Test rename operations combined with content modifications"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Scenario 1: Modify then rename
        file1 = self.watch_dir / "modify_then_rename.txt"
        file1.write_text("Original content")
        time.sleep(0.5)
        
        file1.write_text("Modified content")
        time.sleep(0.5)
        
        renamed1 = self.watch_dir / "was_modified.txt"
        file1.rename(renamed1)
        time.sleep(0.5)
        
        # Scenario 2: Rename then modify
        file2 = self.watch_dir / "rename_then_modify.txt"
        file2.write_text("Original content 2")
        time.sleep(0.5)
        
        renamed2 = self.watch_dir / "will_be_modified.txt"
        file2.rename(renamed2)
        time.sleep(0.5)
        
        renamed2.write_text("Modified after rename")
        time.sleep(0.5)
        
        # Scenario 3: Create, rename, delete, recreate with same name
        file3 = self.watch_dir / "lifecycle.txt"
        file3.write_text("First incarnation")
        time.sleep(0.5)
        
        renamed3 = self.watch_dir / "lifecycle_renamed.txt"
        file3.rename(renamed3)
        time.sleep(0.5)
        
        renamed3.unlink()
        time.sleep(0.5)
        
        # Recreate with original name
        file3.write_text("Second incarnation")
        time.sleep(0.5)
        
        watcher.stop()
        
        # Analyze combined operations
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if 'version_id' in metadata and 'event_type' in metadata:
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        
        # Count events by filename
        event_counts = {}
        for event in all_events:
            filename = event.get('file_name', '')
            if filename not in event_counts:
                event_counts[filename] = []
            event_counts[filename].append(event['event_type'])
        
        print("Event counts by filename:")
        for filename, events in sorted(event_counts.items()):
            print(f"  {filename}: {events}")
        
        # Verify final states
        assert renamed1.exists() and renamed1.read_text() == "Modified content"
        assert renamed2.exists() and renamed2.read_text() == "Modified after rename"
        assert file3.exists() and file3.read_text() == "Second incarnation"
        assert not renamed3.exists(), "Deleted file should not exist"


if __name__ == "__main__":
    # Run tests
    test = TestRenameFile()
    test.setup_method()
    try:
        test.test_simple_rename_same_directory()
        print("✓ Simple rename test passed!")
        
        test.teardown_method()
        test.setup_method()
        test.test_move_to_subdirectory()
        print("✓ Move to subdirectory test passed!")
        
        test.teardown_method()
        test.setup_method() 
        test.test_complex_rename_scenarios()
        print("✓ Complex rename scenarios test passed!")
        
    finally:
        test.teardown_method()