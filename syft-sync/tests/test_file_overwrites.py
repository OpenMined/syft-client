"""
Tests for file overwrite operations from TEST_STRATEGY.md
Section 1.1: Basic File Operations - Overwrite File
"""
import os
import sys
import time
import json
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


class TestOverwriteFile:
    """Test: Overwrite File - Complete replacement of file contents"""
    
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
    
    def test_complete_content_replacement(self):
        """Test complete replacement with different content types"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        file_path = self.watch_dir / "overwrite.txt"
        
        # Original: Small text
        original = "Small original content"
        file_path.write_text(original)
        time.sleep(0.5)
        
        # Overwrite 1: Large text  
        large_overwrite = "Large replacement: " + "X" * 5000
        file_path.write_text(large_overwrite)
        time.sleep(0.5)
        
        # Overwrite 2: Binary-like content
        binary_overwrite = "Binary replacement: \x00\x01\x02\xFF"
        file_path.write_text(binary_overwrite)
        time.sleep(0.5)
        
        # Overwrite 3: Unicode and special characters
        unicode_overwrite = "Unicode: 🚀 ñáéíóú ∑∏∆ 中文 العربية"
        file_path.write_text(unicode_overwrite)
        time.sleep(0.5)
        
        # Overwrite 4: Empty content (edge case)
        empty_overwrite = ""
        file_path.write_text(empty_overwrite)
        time.sleep(0.5)
        
        watcher.stop()
        
        # Should have 5 archives: 1 create + 4 overwrites
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        assert len(archives) == 5, f"Should have exactly 5 archives (1 create + 4 overwrites), found {len(archives)}"
        
        # Extract all events and sort by timestamp
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'overwrite.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        assert len(all_events) == 5, f"Should have 5 events for overwrite.txt, found {len(all_events)}"
        
        # Verify event sequence
        assert all_events[0]['event_type'] == 'file_created', "First event should be file_created"
        for i in range(1, 5):
            assert all_events[i]['event_type'] == 'file_modified', f"Event {i+1} should be file_modified"
        
        # Define expected content for each version
        expected_contents = [
            original,
            large_overwrite,
            binary_overwrite,
            unicode_overwrite,
            empty_overwrite
        ]
        
        # Verify each version's content is preserved in archives
        for i, expected_content in enumerate(expected_contents):
            version_archive = get_version_archive(self.log_dir, all_events[i]['version_id'])
            assert version_archive is not None, f"Archive should exist for version {i+1}"
            
            actual_content = read_file_from_archive(version_archive, 'overwrite.txt')
            assert actual_content == expected_content, f"Version {i+1} content mismatch"
            
            # Verify file sizes are tracked correctly
            expected_size = len(expected_content.encode('utf-8'))
            actual_size = all_events[i]['size']
            assert actual_size == expected_size, f"Version {i+1} size mismatch: expected {expected_size}, got {actual_size}"
        
        # Verify size progression makes sense
        sizes = [event['size'] for event in all_events]
        assert sizes[0] < sizes[1], "Original -> Large: size should increase significantly"
        assert sizes[1] > sizes[2], "Large -> Binary: size should decrease"
        assert sizes[4] == 0, "Empty overwrite should have size 0"
        
        # Verify the final file state
        final_content = file_path.read_text()
        assert final_content == empty_overwrite, "Final file should be empty"
    
    def test_filetype_overwrites(self):
        """Test overwriting same filename with different file types"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        file_path = self.watch_dir / "document.txt"
        
        # Version 1: Text document
        text_content = "This is a text document with some content"
        file_path.write_text(text_content)
        time.sleep(0.5)
        
        # Version 2: JSON data (same filename)
        json_data = {"type": "json", "data": [1, 2, 3], "nested": {"key": "value"}}
        json_content = json.dumps(json_data, indent=2)
        file_path.write_text(json_content)
        time.sleep(0.5)
        
        # Version 3: CSV data (same filename)  
        csv_content = "name,age,city\nJohn,30,NYC\nJane,25,LA\nBob,35,Chicago"
        file_path.write_text(csv_content)
        time.sleep(0.5)
        
        # Version 4: XML data (same filename)
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<root>
    <person id="1">
        <name>Alice</name>
        <age>28</age>
    </person>
    <person id="2">
        <name>Bob</name>
        <age>32</age>
    </person>
</root>"""
        file_path.write_text(xml_content)
        time.sleep(0.5)
        
        # Version 5: Log format (same filename)
        log_content = """2023-10-09 10:00:01 INFO Starting application
2023-10-09 10:00:02 DEBUG Loading configuration
2023-10-09 10:00:03 WARN Missing optional config
2023-10-09 10:00:04 ERROR Failed to connect to database"""
        file_path.write_text(log_content)
        time.sleep(0.5)
        
        watcher.stop()
        
        # Should have 5 archives: 1 create + 4 overwrites
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        assert len(archives) == 5, f"Should have exactly 5 archives (1 create + 4 overwrites), found {len(archives)}"
        
        # Extract all events and sort by timestamp
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'document.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        assert len(all_events) == 5, f"Should have 5 events for document.txt, found {len(all_events)}"
        
        # Define expected content for each version
        expected_contents = [
            text_content,
            json_content,
            csv_content,
            xml_content,
            log_content
        ]
        
        # Verify each version's content and validate format
        for i, expected_content in enumerate(expected_contents):
            version_archive = get_version_archive(self.log_dir, all_events[i]['version_id'])
            actual_content = read_file_from_archive(version_archive, 'document.txt')
            assert actual_content == expected_content, f"Version {i+1} content mismatch"
            
            # Validate specific file formats
            if i == 1:  # JSON version
                parsed_json = json.loads(actual_content)
                assert parsed_json["type"] == "json", "JSON should be valid and parseable"
                assert len(parsed_json["data"]) == 3, "JSON data array should have 3 elements"
            
            elif i == 2:  # CSV version
                lines = actual_content.strip().split('\n')
                assert len(lines) == 4, "CSV should have 4 lines (header + 3 data rows)"
                assert lines[0] == "name,age,city", "CSV header should be correct"
            
            elif i == 3:  # XML version
                assert "<?xml version" in actual_content, "XML should have declaration"
                assert "<root>" in actual_content and "</root>" in actual_content, "XML should have root element"
            
            elif i == 4:  # Log version
                log_lines = actual_content.strip().split('\n')
                assert len(log_lines) == 4, "Log should have 4 entries"
                assert all("2023-10-09" in line for line in log_lines), "All log lines should have date"
        
        # Verify that each format completely replaced the previous one
        final_content = file_path.read_text()
        assert final_content == log_content, "Final file should contain log format"
        assert "json" not in final_content, "No traces of JSON should remain"
        assert "name,age,city" not in final_content, "No traces of CSV should remain"
    
    def test_different_overwrite_methods(self):
        """Test different ways of overwriting files"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        base_content = "Original content to be overwritten"
        
        # Method 1: write_text() replacement (atomic)
        file1 = self.watch_dir / "atomic.txt"
        file1.write_text(base_content)
        time.sleep(0.5)
        method1_content = "Atomic overwrite via write_text()"
        file1.write_text(method1_content)
        time.sleep(0.5)
        
        # Method 2: Open with 'w' mode (truncate + write)
        file2 = self.watch_dir / "truncate.txt" 
        file2.write_text(base_content)
        time.sleep(0.5)
        method2_content = "Overwrite via truncate mode"
        with open(file2, 'w') as f:
            f.write(method2_content)
        time.sleep(0.5)
        
        # Method 3: write_bytes() replacement
        file3 = self.watch_dir / "binary.txt"
        file3.write_text(base_content)
        time.sleep(0.5)
        method3_bytes = b"Binary overwrite content"
        file3.write_bytes(method3_bytes)
        method3_content = method3_bytes.decode('utf-8')
        time.sleep(0.5)
        
        # Method 4: Copy over existing file
        file4 = self.watch_dir / "copy.txt"
        file4.write_text(base_content)
        time.sleep(0.5)
        method4_content = "Copy-based overwrite"
        temp_file = self.watch_dir / "temp.txt"
        temp_file.write_text(method4_content)
        shutil.copy2(temp_file, file4)
        time.sleep(0.5)
        
        # Method 5: Multiple write operations (simulate partial then complete overwrite)
        file5 = self.watch_dir / "multi.txt"
        file5.write_text(base_content)
        time.sleep(0.5)
        # First, truncate and start writing
        with open(file5, 'w') as f:
            f.write("Partial")
        time.sleep(0.1)
        # Then complete the overwrite
        method5_content = "Complete multi-step overwrite"
        file5.write_text(method5_content)
        time.sleep(0.5)
        
        watcher.stop()
        
        # Should have multiple archives for all the operations
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        # At minimum: 5 creates + 5 overwrites = 10, but may have more due to multi-step operations
        assert len(archives) >= 10, f"Should have at least 10 archives, found {len(archives)}"
        
        # Test each file individually
        files_and_expected = [
            ("atomic.txt", method1_content),
            ("truncate.txt", method2_content), 
            ("binary.txt", method3_content),
            ("copy.txt", method4_content),
            ("multi.txt", method5_content)
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
            assert len(file_events) >= 2, f"Should have at least 2 events for {filename}: create + overwrite"
            
            # Verify original content is preserved
            original_archive = get_version_archive(self.log_dir, file_events[0]['version_id'])
            original_content = read_file_from_archive(original_archive, filename)
            assert original_content == base_content, f"Original content should be preserved for {filename}"
            
            # Verify final content is correct
            final_archive = get_version_archive(self.log_dir, file_events[-1]['version_id'])
            final_content = read_file_from_archive(final_archive, filename)
            assert final_content == expected_final_content, f"Final content mismatch for {filename}"
            
            # Verify the file on disk has the final content
            actual_file_content = (self.watch_dir / filename).read_text()
            assert actual_file_content == expected_final_content, f"File on disk should have final content for {filename}"
            
            # Verify sizes changed appropriately
            original_size = file_events[0]['size']
            final_size = file_events[-1]['size']
            expected_original_size = len(base_content.encode('utf-8'))
            expected_final_size = len(expected_final_content.encode('utf-8'))
            
            assert original_size == expected_original_size, f"Original size incorrect for {filename}"
            assert final_size == expected_final_size, f"Final size incorrect for {filename}"
        
        # Clean up temp file
        if temp_file.exists():
            temp_file.unlink()
    
    def test_overwrite_with_metadata_changes(self):
        """Test overwrites that also change file metadata"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        file_path = self.watch_dir / "metadata.txt"
        
        # Original file with small content
        original = "Small file"
        file_path.write_text(original)
        original_size = len(original.encode('utf-8'))
        time.sleep(0.5)
        
        # Overwrite with much larger content (significant size change)
        large_content = "Large file: " + "LARGE" * 2000  # ~10KB
        file_path.write_text(large_content)
        large_size = len(large_content.encode('utf-8'))
        time.sleep(0.5)
        
        # Overwrite with binary content (type change)
        binary_content = bytes(range(256))  # All byte values 0-255
        file_path.write_bytes(binary_content)
        binary_size = len(binary_content)
        time.sleep(0.5)
        
        watcher.stop()
        
        # Extract events
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        assert len(archives) == 3, f"Should have exactly 3 archives, found {len(archives)}"
        
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if (metadata.get('file_name') == 'metadata.txt' and 
                    'version_id' in metadata and 'event_type' in metadata):
                    all_events.append(metadata)
        
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        assert len(all_events) == 3, "Should have 3 events"
        
        # Verify size progression
        assert all_events[0]['size'] == original_size, "Original size should match"
        assert all_events[1]['size'] == large_size, "Large size should match"
        assert all_events[2]['size'] == binary_size, "Binary size should match"
        
        # Verify dramatic size changes are captured
        assert all_events[1]['size'] > all_events[0]['size'] * 100, "Size should increase dramatically"
        assert all_events[2]['size'] < all_events[1]['size'] / 10, "Size should decrease dramatically"
        
        # Verify content integrity across all versions
        original_archive = get_version_archive(self.log_dir, all_events[0]['version_id'])
        large_archive = get_version_archive(self.log_dir, all_events[1]['version_id'])
        binary_archive = get_version_archive(self.log_dir, all_events[2]['version_id'])
        
        # Verify text content
        assert read_file_from_archive(original_archive, 'metadata.txt') == original
        assert read_file_from_archive(large_archive, 'metadata.txt') == large_content
        
        # For binary content, we need to handle it specially since read_file_from_archive expects text
        # Let's verify the binary content by checking the actual archive
        info = extract_syft_archive(binary_archive)
        try:
            binary_file = info["data_dir"] / "metadata.txt"
            actual_binary = binary_file.read_bytes()
            assert actual_binary == binary_content, "Binary content should be preserved"
        finally:
            shutil.rmtree(info["temp_dir"], ignore_errors=True)


if __name__ == "__main__":
    # Run a simple test
    test = TestOverwriteFile()
    test.setup_method()
    try:
        test.test_complete_content_replacement()
        print("✓ Complete content replacement test passed!")
        
        test.teardown_method()
        test.setup_method()
        test.test_filetype_overwrites()
        print("✓ File type overwrites test passed!")
        
        test.teardown_method()
        test.setup_method()
        test.test_different_overwrite_methods()
        print("✓ Different overwrite methods test passed!")
        
    finally:
        test.teardown_method()