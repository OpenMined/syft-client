"""
Tests for file update operations from TEST_STRATEGY.md
Section 1.1: Basic File Operations - Update File
"""
import os
import sys
import time
import json
from pathlib import Path
import tempfile
import shutil

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


class TestUpdateFile:
    """Test: Update File - Modify existing files with different content"""
    
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
    
    def test_progressive_updates(self):
        """Test multiple sequential updates to same file"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        file_path = self.watch_dir / "evolving.txt"
        
        # Version 1: Initial content
        version1_content = "Version 1: Initial content"
        file_path.write_text(version1_content)
        time.sleep(0.5)
        
        # Version 2: Add more content
        version2_content = "Version 1: Initial content\nVersion 2: Added line"
        file_path.write_text(version2_content)
        time.sleep(0.5)
        
        # Version 3: Major rewrite
        version3_content = "Version 3: Complete rewrite with new content"
        file_path.write_text(version3_content)
        time.sleep(0.5)
        
        watcher.stop()
        
        # Verify: Should have 3 archives (1 create + 2 modify)
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        assert len(archives) == 3, f"Should have exactly 3 archives (1 create + 2 modify), found {len(archives)}"
        
        # Extract all events and sort by timestamp
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if 'version_id' in metadata and 'event_type' in metadata and metadata['file_name'] == 'evolving.txt':
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        assert len(all_events) == 3, f"Should have 3 events for evolving.txt, found {len(all_events)}"
        
        # Verify event sequence
        assert all_events[0]['event_type'] == 'file_created', "First event should be file_created"
        assert all_events[1]['event_type'] == 'file_modified', "Second event should be file_modified"
        assert all_events[2]['event_type'] == 'file_modified', "Third event should be file_modified"
        
        # Verify each version's content is preserved
        version1_archive = get_version_archive(self.log_dir, all_events[0]['version_id'])
        version1_actual = read_file_from_archive(version1_archive, 'evolving.txt')
        assert version1_actual == version1_content, "Version 1 content mismatch"
        
        version2_archive = get_version_archive(self.log_dir, all_events[1]['version_id'])
        version2_actual = read_file_from_archive(version2_archive, 'evolving.txt')
        assert version2_actual == version2_content, "Version 2 content mismatch"
        
        version3_archive = get_version_archive(self.log_dir, all_events[2]['version_id'])
        version3_actual = read_file_from_archive(version3_archive, 'evolving.txt')
        assert version3_actual == version3_content, "Version 3 content mismatch"
        
        # Verify file sizes are tracked correctly
        assert all_events[0]['size'] == len(version1_content.encode()), "Version 1 size mismatch"
        assert all_events[1]['size'] == len(version2_content.encode()), "Version 2 size mismatch"
        assert all_events[2]['size'] == len(version3_content.encode()), "Version 3 size mismatch"
    
    def test_different_update_methods(self):
        """Test different ways of modifying files"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        base_content = "Original content"
        
        # Method 1: write_text() replacement
        file1 = self.watch_dir / "method1.txt"
        file1.write_text(base_content)
        time.sleep(0.5)
        method1_updated = "Updated via write_text()"
        file1.write_text(method1_updated)
        time.sleep(0.5)
        
        # Method 2: Append mode
        file2 = self.watch_dir / "method2.txt" 
        file2.write_text(base_content)
        time.sleep(0.5)
        with open(file2, 'a') as f:
            f.write("\nAppended content")
        method2_expected = base_content + "\nAppended content"
        time.sleep(0.5)
        
        # Method 3: Truncate and rewrite
        file3 = self.watch_dir / "method3.txt"
        file3.write_text(base_content)
        time.sleep(0.5)
        method3_updated = "Truncated and rewritten"
        with open(file3, 'w') as f:
            f.write(method3_updated)
        time.sleep(0.5)
        
        # Method 4: Binary write
        file4 = self.watch_dir / "method4.txt"
        file4.write_text(base_content)
        time.sleep(0.5)
        method4_binary = b"Binary update content"
        file4.write_bytes(method4_binary)
        time.sleep(0.5)
        
        watcher.stop()
        
        # Should have 8 archives: 4 creates + 4 modifies
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        assert len(archives) == 8, f"Should have exactly 8 archives (4 creates + 4 modifies), found {len(archives)}"
        
        # Verify all methods generate modify events
        files_and_expected = [
            ("method1.txt", method1_updated),
            ("method2.txt", method2_expected),
            ("method3.txt", method3_updated),
            ("method4.txt", method4_binary.decode('utf-8')),
        ]
        
        for filename, expected_final_content in files_and_expected:
            # Find events for this file
            file_events = []
            for archive_path in archives:
                metadata_list = get_archive_metadata(archive_path)
                for metadata in metadata_list:
                    if (metadata.get('file_name') == filename and 
                        'version_id' in metadata and 'event_type' in metadata):
                        file_events.append(metadata)
            
            file_events.sort(key=lambda x: x.get('timestamp', ''))
            assert len(file_events) == 2, f"Should have 2 events for {filename}: create + modify"
            assert file_events[0]['event_type'] == 'file_created', f"First event for {filename} should be create"
            assert file_events[1]['event_type'] == 'file_modified', f"Second event for {filename} should be modify"
            
            # Verify final content
            final_archive = get_version_archive(self.log_dir, file_events[1]['version_id'])
            final_content = read_file_from_archive(final_archive, filename)
            assert final_content == expected_final_content, f"Final content mismatch for {filename}"
    
    def test_content_variations(self):
        """Test updates with different content sizes and types"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        file_path = self.watch_dir / "variations.txt"
        
        # Track all versions
        versions = []
        
        # Version 1: Start small
        small_content = "Small"
        file_path.write_text(small_content)
        versions.append(("small", small_content))
        time.sleep(0.5)
        
        # Version 2: Grow significantly larger
        large_content = "Large content: " + "x" * 10000
        file_path.write_text(large_content)
        versions.append(("large", large_content))
        time.sleep(0.5)
        
        # Version 3: Shrink back down
        tiny_content = "Tiny"
        file_path.write_text(tiny_content)
        versions.append(("tiny", tiny_content))
        time.sleep(0.5)
        
        # Version 4: Special characters and unicode
        special_content = "Special chars: àáâãäåæçèéêë 🚀 ∑∏∆"
        file_path.write_text(special_content)
        versions.append(("special", special_content))
        time.sleep(0.5)
        
        # Version 5: Empty file
        empty_content = ""
        file_path.write_text(empty_content)
        versions.append(("empty", empty_content))
        time.sleep(0.5)
        
        # Version 6: Multi-line with consistent line endings
        multiline_content = "Line 1\nLine 2\nLine 3\n\nLine 5 after empty line"
        file_path.write_text(multiline_content)
        versions.append(("multiline", multiline_content))
        time.sleep(0.5)
        
        watcher.stop()
        
        # Should have 6 archives: 1 create + 5 modify
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        assert len(archives) == 6, f"Should have exactly 6 archives (1 create + 5 modify), found {len(archives)}"
        
        # Extract all events and sort by timestamp
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'variations.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        assert len(all_events) == 6, f"Should have 6 events for variations.txt, found {len(all_events)}"
        
        # Verify event types
        assert all_events[0]['event_type'] == 'file_created', "First event should be file_created"
        for i in range(1, 6):
            assert all_events[i]['event_type'] == 'file_modified', f"Event {i+1} should be file_modified"
        
        # Verify each version's content and size
        for i, (version_name, expected_content) in enumerate(versions):
            version_archive = get_version_archive(self.log_dir, all_events[i]['version_id'])
            actual_content = read_file_from_archive(version_archive, 'variations.txt')
            assert actual_content == expected_content, f"{version_name} version content mismatch"
            
            expected_size = len(expected_content.encode('utf-8'))
            actual_size = all_events[i]['size']
            assert actual_size == expected_size, f"{version_name} version size mismatch: expected {expected_size}, got {actual_size}"
        
        # Verify size progression
        sizes = [event['size'] for event in all_events]
        assert sizes[0] < sizes[1], "Small -> Large: size should increase"
        assert sizes[1] > sizes[2], "Large -> Tiny: size should decrease"
        assert sizes[4] == 0, "Empty version should have size 0"
        assert sizes[5] > sizes[4], "Multiline should be larger than empty"
        
        # Verify special characters are preserved
        special_archive = get_version_archive(self.log_dir, all_events[3]['version_id'])
        special_actual = read_file_from_archive(special_archive, 'variations.txt')
        assert "🚀" in special_actual, "Unicode emoji should be preserved"
        assert "àáâãäåæçèéêë" in special_actual, "Accented characters should be preserved"
        assert "∑∏∆" in special_actual, "Mathematical symbols should be preserved"
    
    def test_rapid_updates_no_delays(self):
        """Test rapid successive updates without delays - demonstrates filesystem event coalescing"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)  # Just initial startup delay
        
        file_path = self.watch_dir / "rapid.txt"
        
        # Create initial file
        file_path.write_text("Initial")
        
        # Rapid updates with NO delays - filesystem will coalesce these
        for i in range(5):
            content = f"Rapid update {i+1}"
            file_path.write_text(content)
        
        # Only wait at the end for filesystem events to be processed
        time.sleep(1.0)
        watcher.stop()
        
        # With no delays, filesystem coalescing means we likely get only 1 event
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        assert len(archives) >= 1, f"Should have at least 1 archive, found {len(archives)}"
        
        # Extract events
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'rapid.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        
        # Should have at least 1 event
        assert len(all_events) >= 1, "Should have at least one event"
        
        # The event should capture the final state due to coalescing
        final_archive = get_version_archive(self.log_dir, all_events[-1]['version_id'])
        final_archived_content = read_file_from_archive(final_archive, 'rapid.txt')
        assert final_archived_content == "Rapid update 5", "Should capture the final state"
        
        # Verify the final file state is correct
        final_content = file_path.read_text()
        assert final_content == "Rapid update 5", "Final content should be the last update"
        
        print(f"Rapid updates (no delays): {len(all_events)} events captured out of 6 total writes - filesystem coalescing occurred")
    
    def test_rapid_updates_with_delays(self):
        """Test rapid successive updates with small delays - captures more events"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        file_path = self.watch_dir / "rapid_delayed.txt"
        
        # Create initial file
        file_path.write_text("Initial")
        time.sleep(0.1)  # Small delay
        
        # Rapid updates with small delays
        for i in range(5):
            content = f"Rapid update {i+1}"
            file_path.write_text(content)
            time.sleep(0.05)  # Very small delay to prevent full coalescing
        
        time.sleep(1.0)
        watcher.stop()
        
        # With small delays, we should capture more events
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        assert len(archives) >= 2, f"Should have at least 2 archives with delays, found {len(archives)}"
        
        # Extract events
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'rapid_delayed.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        
        # Should have multiple events with delays
        assert len(all_events) >= 2, "Should have multiple events with delays"
        assert all_events[0]['event_type'] == 'file_created', "First event should be file_created"
        
        # Verify the final state is correct
        final_content = file_path.read_text()
        assert final_content == "Rapid update 5", "Final content should be the last update"
        
        print(f"Rapid updates (with delays): {len(all_events)} events captured out of 6 total writes")


if __name__ == "__main__":
    # Run a simple test
    test = TestUpdateFile()
    test.setup_method()
    try:
        test.test_progressive_updates()
        print("✓ Progressive updates test passed!")
        
        test.teardown_method()
        test.setup_method()
        test.test_different_update_methods()
        print("✓ Different update methods test passed!")
        
        test.teardown_method()
        test.setup_method()
        test.test_content_variations()
        print("✓ Content variations test passed!")
        
    finally:
        test.teardown_method()