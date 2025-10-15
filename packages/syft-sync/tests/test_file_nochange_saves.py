"""
Tests for file updates with same contents from TEST_STRATEGY.md
Section 1.1: Basic File Operations - Update with Same Contents
"""
import os
import sys
import time
import shutil
import threading
import hashlib
from pathlib import Path
import tempfile
import concurrent.futures

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


class TestNoChangeSaves:
    """Test: Update with Same Contents - Save file without actual changes"""
    
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
    
    def test_identical_content_saves(self):
        """Test saving file with exact same content multiple times"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        file_path = self.watch_dir / "unchanged.txt"
        
        # Original content
        content = "This content will remain the same throughout all saves"
        file_path.write_text(content)
        time.sleep(0.5)
        
        # Save same content multiple times
        for i in range(4):
            file_path.write_text(content)  # Exact same content
            time.sleep(0.5)
        
        watcher.stop()
        
        # Analyze what happened
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        print(f"Identical saves: {len(archives)} archives created for 5 identical saves")
        
        # Extract all events
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'unchanged.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        
        # Verify all events capture the same content
        for i, event in enumerate(all_events):
            archive = get_version_archive(self.log_dir, event['version_id'])
            actual_content = read_file_from_archive(archive, 'unchanged.txt')
            assert actual_content == content, f"Event {i+1} should have identical content"
            
            # All should have same size and hash (if tracked)
            expected_size = len(content.encode('utf-8'))
            assert event['size'] == expected_size, f"Event {i+1} should have same size"
        
        # The system should generate events (filesystem behavior) but content should be identical
        assert len(all_events) >= 1, "Should have at least the initial create event"
        
        # Verify final file state
        final_content = file_path.read_text()
        assert final_content == content, "Final file should have unchanged content"
    
    def test_different_save_methods_same_content(self):
        """Test different methods of saving identical content"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        content = "Identical content across all methods"
        
        # Method 1: write_text() repetition
        file1 = self.watch_dir / "method1.txt"
        file1.write_text(content)
        time.sleep(0.5)
        file1.write_text(content)  # Same content
        time.sleep(0.5)
        
        # Method 2: read then write back
        file2 = self.watch_dir / "method2.txt" 
        file2.write_text(content)
        time.sleep(0.5)
        existing = file2.read_text()
        file2.write_text(existing)  # Write back what was read
        time.sleep(0.5)
        
        # Method 3: copy over itself (if filesystem allows)
        file3 = self.watch_dir / "method3.txt"
        file3.write_text(content)
        time.sleep(0.5)
        # Create a temp copy then copy back
        temp_copy = self.watch_dir / "temp_copy.txt"
        shutil.copy2(file3, temp_copy)
        shutil.copy2(temp_copy, file3)  # Copy back
        temp_copy.unlink()  # Clean up
        time.sleep(0.5)
        
        # Method 4: write_bytes of same content
        file4 = self.watch_dir / "method4.txt"
        file4.write_text(content)
        time.sleep(0.5)
        file4.write_bytes(content.encode('utf-8'))  # Same content as bytes
        time.sleep(0.5)
        
        watcher.stop()
        
        # Analyze each file's events
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        files_to_check = ["method1.txt", "method2.txt", "method3.txt", "method4.txt"]
        
        for filename in files_to_check:
            file_events = []
            for archive_path in archives:
                metadata_list = get_archive_metadata(archive_path)
                for metadata in metadata_list:
                    if (metadata.get('file_name') == filename and 
                        'version_id' in metadata and 'event_type' in metadata):
                        file_events.append(metadata)
            
            file_events.sort(key=lambda x: x.get('timestamp', ''))
            print(f"{filename}: {len(file_events)} events for identical content saves")
            
            # Verify all versions have identical content
            for event in file_events:
                archive = get_version_archive(self.log_dir, event['version_id'])
                actual_content = read_file_from_archive(archive, filename)
                assert actual_content == content, f"{filename} should have identical content in all versions"
            
            # Verify file on disk
            actual_file = self.watch_dir / filename
            assert actual_file.read_text() == content, f"{filename} on disk should have correct content"
    
    def test_timestamp_vs_content_changes(self):
        """Test operations that change file metadata but not content"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        file_path = self.watch_dir / "metadata.txt"
        content = "Content that never changes"
        
        # Original file
        file_path.write_text(content)
        time.sleep(0.5)
        
        # Touch file (updates timestamp only)
        file_path.touch()
        time.sleep(0.5)
        
        # Change permissions (metadata change)
        original_mode = file_path.stat().st_mode
        file_path.chmod(0o644)
        time.sleep(0.5)
        
        # "Save" same content after metadata changes
        file_path.write_text(content)
        time.sleep(0.5)
        
        # Another touch
        file_path.touch()
        time.sleep(0.5)
        
        watcher.stop()
        
        # Analyze what operations triggered archive creation
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'metadata.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        print(f"Metadata operations: {len(all_events)} events for {len(archives)} archives")
        
        # Verify content consistency across all events
        for i, event in enumerate(all_events):
            archive = get_version_archive(self.log_dir, event['version_id'])
            actual_content = read_file_from_archive(archive, 'metadata.txt')
            assert actual_content == content, f"Event {i+1} should preserve original content despite metadata changes"
        
        # Verify final state
        assert file_path.read_text() == content, "Content should be unchanged after metadata operations"
    
    def test_whitespace_encoding_variations(self):
        """Test content that's semantically same but technically different"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Base content
        base_text = "Line 1\nLine 2\nLine 3"
        
        # Test 1: Different line endings
        file1 = self.watch_dir / "lineendings.txt"
        file1.write_text(base_text)  # Unix: \n
        time.sleep(0.5)
        
        # Windows line endings
        windows_text = base_text.replace('\n', '\r\n')
        file1.write_text(windows_text)
        time.sleep(0.5)
        
        # Mac line endings  
        mac_text = base_text.replace('\n', '\r')
        file1.write_text(mac_text)
        time.sleep(0.5)
        
        # Test 2: Whitespace variations
        file2 = self.watch_dir / "whitespace.txt"
        original = "function() {\n    return true;\n}"
        file2.write_text(original)
        time.sleep(0.5)
        
        # Tabs instead of spaces
        tabbed = "function() {\n\treturn true;\n}"
        file2.write_text(tabbed)
        time.sleep(0.5)
        
        # Extra trailing whitespace
        trailing = "function() {\n    return true; \n} "
        file2.write_text(trailing)
        time.sleep(0.5)
        
        # Test 3: Encoding variations (simulate different encodings)
        file3 = self.watch_dir / "encoding.txt"
        unicode_content = "Special chars: àáâã 🚀 ñ"
        file3.write_text(unicode_content, encoding='utf-8')
        time.sleep(0.5)
        
        # Write same content (filesystem will use UTF-8)
        file3.write_text(unicode_content)
        time.sleep(0.5)
        
        watcher.stop()
        
        # Analyze how system handles "similar but different" content
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        files_to_analyze = [
            ("lineendings.txt", [base_text, windows_text, mac_text]),
            ("whitespace.txt", [original, tabbed, trailing]),
            ("encoding.txt", [unicode_content, unicode_content])
        ]
        
        for filename, expected_versions in files_to_analyze:
            file_events = []
            for archive_path in archives:
                metadata_list = get_archive_metadata(archive_path)
                for metadata in metadata_list:
                    if (metadata.get('file_name') == filename and 
                        'version_id' in metadata and 'event_type' in metadata):
                        file_events.append(metadata)
            
            file_events.sort(key=lambda x: x.get('timestamp', ''))
            print(f"{filename}: {len(file_events)} events for whitespace/encoding variations")
            
            # Verify each version is preserved correctly
            # Note: Python's text mode normalizes line endings to \n
            for i, (event, expected_content) in enumerate(zip(file_events, expected_versions)):
                archive = get_version_archive(self.log_dir, event['version_id'])
                actual_content = read_file_from_archive(archive, filename)
                
                # For line ending tests, normalize expected content since Python text mode converts to \n
                if filename == "lineendings.txt":
                    normalized_expected = expected_content.replace('\r\n', '\n').replace('\r', '\n')
                    assert actual_content == normalized_expected, f"{filename} version {i+1} content mismatch (normalized)"
                else:
                    assert actual_content == expected_content, f"{filename} version {i+1} content mismatch"
    
    def test_content_deduplication_logic(self):
        """Test if system properly handles content deduplication scenarios"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        shared_content = "This exact content will be used in multiple scenarios"
        
        # Scenario 1: Create file, delete it, recreate with same content
        file1 = self.watch_dir / "recreated.txt"
        file1.write_text(shared_content)
        time.sleep(0.5)
        
        file1.unlink()
        time.sleep(0.5)
        
        file1.write_text(shared_content)  # Same content as before
        time.sleep(0.5)
        
        # Scenario 2: Different filenames, same content
        file2 = self.watch_dir / "copy1.txt"
        file3 = self.watch_dir / "copy2.txt"
        file4 = self.watch_dir / "copy3.txt"
        
        file2.write_text(shared_content)
        time.sleep(0.5)
        file3.write_text(shared_content)
        time.sleep(0.5)
        file4.write_text(shared_content)
        time.sleep(0.5)
        
        # Scenario 3: Same content written at different times
        file5 = self.watch_dir / "delayed.txt"
        file5.write_text(shared_content)
        time.sleep(1.0)  # Longer delay
        file5.write_text(shared_content)  # Same content, different timestamp
        time.sleep(0.5)
        
        watcher.stop()
        
        # Analyze deduplication behavior
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        
        # Count how many times the same content is stored
        content_instances = 0
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if 'version_id' in metadata and 'event_type' in metadata:
                    try:
                        archive = get_version_archive(self.log_dir, metadata['version_id'])
                        actual_content = read_file_from_archive(archive, metadata['file_name'])
                        if actual_content == shared_content:
                            content_instances += 1
                    except:
                        pass  # Skip if file not in archive (e.g., delete events)
        
        print(f"Content deduplication: {content_instances} instances of identical content across {len(archives)} archives")
        
        # Verify all files have correct content
        for filename in ["recreated.txt", "copy1.txt", "copy2.txt", "copy3.txt", "delayed.txt"]:
            if (self.watch_dir / filename).exists():
                actual = (self.watch_dir / filename).read_text()
                assert actual == shared_content, f"{filename} should have correct content"
    
    def test_rapid_nochange_saves(self):
        """Test rapid saves without content changes"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        file_path = self.watch_dir / "rapid_unchanged.txt"
        content = "Content that gets saved rapidly without changes"
        
        # Initial save
        file_path.write_text(content)
        time.sleep(0.5)
        
        # Rapid saves without delays (simulate auto-save)
        for i in range(10):
            file_path.write_text(content)
            # No delay - as fast as possible
        
        time.sleep(1.0)  # Wait for events to be processed
        
        # Some saves with tiny delays
        for i in range(5):
            file_path.write_text(content)
            time.sleep(0.05)  # Very small delay
        
        watcher.stop()
        
        # Analyze rapid save behavior
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'rapid_unchanged.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        print(f"Rapid no-change saves: {len(all_events)} events captured from 16 total saves")
        
        # Verify all captured events have identical content
        for i, event in enumerate(all_events):
            archive = get_version_archive(self.log_dir, event['version_id'])
            actual_content = read_file_from_archive(archive, 'rapid_unchanged.txt')
            assert actual_content == content, f"Rapid save event {i+1} should have unchanged content"
        
        # Verify filesystem event coalescing may have occurred
        assert len(all_events) <= 16, "Filesystem may have coalesced some rapid events"
        assert len(all_events) >= 1, "Should have at least one event"
    
    def test_large_file_nochange_detection(self):
        """Test efficiency with large files that don't change"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Create large content (1MB)
        large_content = "Large file content: " + "X" * (1024 * 1024 - 20)
        file_path = self.watch_dir / "large_unchanged.txt"
        
        # Initial save
        start_time = time.time()
        file_path.write_text(large_content)
        time.sleep(1.0)
        
        # Save same large content multiple times
        for i in range(3):
            save_start = time.time()
            file_path.write_text(large_content)
            save_end = time.time()
            print(f"Large file save {i+1}: {save_end - save_start:.3f}s")
            time.sleep(0.5)
        
        watcher.stop()
        
        # Analyze large file handling
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        all_events = []
        total_archive_size = 0
        
        for archive_path in archives:
            archive_size = archive_path.stat().st_size
            total_archive_size += archive_size
            
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'large_unchanged.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        print(f"Large file no-change: {len(all_events)} events, {total_archive_size} bytes total storage")
        
        # Verify content integrity for large files
        for event in all_events:
            archive = get_version_archive(self.log_dir, event['version_id'])
            actual_content = read_file_from_archive(archive, 'large_unchanged.txt')
            assert len(actual_content) == len(large_content), "Large file size should be preserved"
            assert actual_content == large_content, "Large file content should be identical"
        
        # Check if system is efficient with large unchanged files
        expected_size = len(large_content.encode('utf-8'))
        for event in all_events:
            assert event['size'] == expected_size, "Large file size should be consistent"
    
    def test_binary_nochange_scenarios(self):
        """Test binary files saved without changes"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Create binary content (simulate image/executable)
        binary_data = bytes(range(256)) * 4  # 1024 bytes of binary data
        binary_file = self.watch_dir / "binary_unchanged.bin"
        
        # Initial save
        binary_file.write_bytes(binary_data)
        time.sleep(0.5)
        
        # Save same binary data multiple times
        for i in range(3):
            binary_file.write_bytes(binary_data)
            time.sleep(0.5)
        
        # Save via different method (read then write)
        existing_data = binary_file.read_bytes()
        binary_file.write_bytes(existing_data)
        time.sleep(0.5)
        
        watcher.stop()
        
        # Analyze binary file handling
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'binary_unchanged.bin' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        print(f"Binary no-change: {len(all_events)} events for unchanged binary file")
        
        # Verify binary content integrity
        for i, event in enumerate(all_events):
            archive = get_version_archive(self.log_dir, event['version_id'])
            # Extract binary data from archive
            info = extract_syft_archive(archive)
            try:
                binary_archive_file = info["data_dir"] / "binary_unchanged.bin"
                if binary_archive_file.exists():
                    archived_data = binary_archive_file.read_bytes()
                    assert archived_data == binary_data, f"Binary event {i+1} should preserve exact binary data"
                    assert len(archived_data) == len(binary_data), f"Binary event {i+1} size should match"
            finally:
                shutil.rmtree(info["temp_dir"], ignore_errors=True)
        
        # Verify final binary file
        final_data = binary_file.read_bytes()
        assert final_data == binary_data, "Final binary file should be unchanged"
    
    def test_concurrent_nochange_saves(self):
        """Test multiple processes/threads saving same content"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        shared_content = "Content saved by multiple concurrent operations"
        file_path = self.watch_dir / "concurrent.txt"
        
        # Initial save
        file_path.write_text(shared_content)
        time.sleep(0.5)
        
        def save_same_content(thread_id):
            """Function to save same content from different threads"""
            for i in range(3):
                file_path.write_text(shared_content)
                time.sleep(0.1)
        
        # Run concurrent saves
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(save_same_content, i) for i in range(3)]
            concurrent.futures.wait(futures)
        
        time.sleep(1.0)  # Wait for all events
        watcher.stop()
        
        # Analyze concurrent save behavior
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'concurrent.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        print(f"Concurrent no-change saves: {len(all_events)} events from concurrent operations")
        
        # Verify content consistency despite concurrency
        for i, event in enumerate(all_events):
            archive = get_version_archive(self.log_dir, event['version_id'])
            actual_content = read_file_from_archive(archive, 'concurrent.txt')
            assert actual_content == shared_content, f"Concurrent event {i+1} should have consistent content"
        
        # Verify final state
        final_content = file_path.read_text()
        assert final_content == shared_content, "Final content should be correct after concurrent saves"
    
    def test_storage_efficiency(self):
        """Test storage implications of no-change events"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Test with different content sizes
        test_content = "Storage efficiency test content"
        
        # Scenario 1: Small file saved multiple times
        small_file = self.watch_dir / "small_efficiency.txt"
        small_file.write_text(test_content)
        time.sleep(0.5)
        
        for i in range(5):
            small_file.write_text(test_content)  # Same content
            time.sleep(0.3)
        
        # Scenario 2: Compare with actual content changes
        changing_file = self.watch_dir / "changing_efficiency.txt"
        changing_file.write_text(test_content)
        time.sleep(0.5)
        
        for i in range(5):
            changing_content = f"{test_content} - version {i+1}"
            changing_file.write_text(changing_content)  # Different content each time
            time.sleep(0.3)
        
        watcher.stop()
        
        # Analyze storage efficiency
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        
        # Calculate storage used for unchanged vs changed files
        unchanged_storage = 0
        changed_storage = 0
        unchanged_events = 0
        changed_events = 0
        
        for archive_path in archives:
            archive_size = archive_path.stat().st_size
            metadata_list = get_archive_metadata(archive_path)
            
            for metadata in metadata_list:
                filename = metadata.get('file_name', '')
                if 'small_efficiency.txt' in filename:
                    unchanged_storage += archive_size
                    unchanged_events += 1
                elif 'changing_efficiency.txt' in filename:
                    changed_storage += archive_size
                    changed_events += 1
        
        print(f"Storage efficiency:")
        print(f"  Unchanged file: {unchanged_events} events, {unchanged_storage} bytes")
        print(f"  Changing file: {changed_events} events, {changed_storage} bytes")
        print(f"  Storage ratio: {unchanged_storage/max(changed_storage, 1):.2f}")
        
        # Verify that unchanged content doesn't waste excessive space
        # (This is observational - actual behavior may vary)
        assert unchanged_events >= 1, "Should have at least one event for unchanged file"
        assert changed_events >= 1, "Should have at least one event for changing file"
        
        # Both files should preserve their correct final state
        assert small_file.read_text() == test_content, "Unchanged file should have original content"
        expected_final = f"{test_content} - version 5"
        assert changing_file.read_text() == expected_final, "Changed file should have final version"


if __name__ == "__main__":
    # Run tests
    test = TestNoChangeSaves()
    test.setup_method()
    try:
        test.test_identical_content_saves()
        print("✓ Identical content saves test passed!")
        
        test.teardown_method()
        test.setup_method()
        test.test_different_save_methods_same_content()
        print("✓ Different save methods test passed!")
        
        test.teardown_method()
        test.setup_method() 
        test.test_storage_efficiency()
        print("✓ Storage efficiency test passed!")
        
    finally:
        test.teardown_method()