"""
Tests for basic file operations from TEST_STRATEGY.md
Section 1.1: Basic File Operations
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
    get_archive_metadata
)


class TestAddFile:
    """Test: Add File - Create new files of various types and sizes"""
    
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
    
    def test_add_single_text_file(self):
        """Test adding a single text file"""
        # Initialize watcher
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=True
        )
        
        # Start watching
        watcher.start()
        time.sleep(0.5)  # Let watcher initialize
        
        # Create a text file
        test_file = self.watch_dir / "test.txt"
        test_content = "Hello, this is a test file!"
        test_file.write_text(test_content)
        
        # Wait for event to be processed
        time.sleep(1.0)
        
        # Stop watcher
        watcher.stop()
        
        # Verify file was detected
        # Use resolve() to get the canonical path (handles /var vs /private/var on macOS)
        history = watcher.get_file_history(str(test_file.resolve()))
        assert len(history) > 0, "File creation was not detected"
        
        # Check the first event
        first_event = history[0]
        assert first_event['event_type'] == 'file_created'
        assert first_event['file_path'] == str(test_file.resolve())
        assert first_event['file_name'] == 'test.txt'
        assert first_event['size'] == len(test_content.encode())
        
        # Verify content was captured
        assert 'version_id' in first_event
        assert 'hash' in first_event
        assert first_event['hash'] is not None
        
        # Also check the raw log files
        version_id = first_event['version_id']
        
        # Verify version metadata
        verify_version_metadata(self.log_dir, version_id, {
            'version_id': version_id,
            'event_type': 'file_created',
            'file_name': 'test.txt'
        })
        
        # Check how the file was stored
        archive_path = get_version_archive(self.log_dir, version_id)
        if archive_path:
            # File is in SyftMessage archive
            verify_syft_message_content(
                archive_path=archive_path,
                expected_filename='test.txt',
                expected_content=test_content
            )
        else:
            # With new flat structure, there should always be an archive
            assert False, "Should always have SyftMessage archive in new structure"
        
    def test_add_multiple_file_types(self):
        """Test adding files of different types"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Create different file types
        files_created = []
        
        # Text file
        txt_file = self.watch_dir / "document.txt"
        txt_file.write_text("Text file content")
        files_created.append(txt_file)
        
        # JSON file
        json_file = self.watch_dir / "data.json"
        json_file.write_text(json.dumps({"key": "value", "number": 42}))
        files_created.append(json_file)
        
        # Python file
        py_file = self.watch_dir / "script.py"
        py_file.write_text("#!/usr/bin/env python3\nprint('Hello')")
        files_created.append(py_file)
        
        # Markdown file
        md_file = self.watch_dir / "readme.md"
        md_file.write_text("# README\n\nThis is a test")
        files_created.append(md_file)
        
        # Binary file (small)
        bin_file = self.watch_dir / "binary.dat"
        bin_file.write_bytes(b'\x00\x01\x02\x03\x04\x05')
        files_created.append(bin_file)
        
        # Wait for processing
        time.sleep(1.5)
        watcher.stop()
        
        # Verify all files were detected
        for file_path in files_created:
            history = watcher.get_file_history(str(file_path.resolve()))
            assert len(history) > 0, f"File {file_path.name} was not detected"
            assert history[0]['event_type'] == 'file_created'
            assert history[0]['file_name'] == file_path.name
    
    def test_add_files_various_sizes(self):
        """Test adding files of various sizes"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Test different file sizes
        test_sizes = [
            ("empty.txt", 0),           # Empty file
            ("tiny.txt", 1),            # 1 byte
            ("small.txt", 100),         # 100 bytes
            ("medium.txt", 10_000),     # 10 KB
            ("large.txt", 1_000_000),   # 1 MB
        ]
        
        files_created = []
        for filename, size in test_sizes:
            file_path = self.watch_dir / filename
            if size == 0:
                file_path.touch()  # Create empty file
            else:
                # Create file with specified size
                content = b'X' * size
                file_path.write_bytes(content)
            files_created.append((file_path, size))
        
        # Wait for processing
        time.sleep(2.0)
        watcher.stop()
        
        # Verify all files were detected with correct sizes
        for file_path, expected_size in files_created:
            history = watcher.get_file_history(str(file_path.resolve()))
            assert len(history) > 0, f"File {file_path.name} was not detected"
            
            event = history[0]
            assert event['event_type'] == 'file_created'
            assert event['size'] == expected_size, f"Size mismatch for {file_path.name}"
    
    def test_add_file_special_names(self):
        """Test adding files with special characters in names"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Files with special names
        special_files = [
            "file with spaces.txt",
            "file-with-dashes.txt",
            "file_with_underscores.txt",
            "file.multiple.dots.txt",
            "file@symbol.txt",
            "file#hash.txt",
            "file(parens).txt",
            "file[brackets].txt",
            "file{braces}.txt",
            "file$dollar.txt",
            "file%percent.txt",
            "file&ampersand.txt",
            "file+plus.txt",
            "file=equals.txt",
            "file,comma.txt",
            "file;semicolon.txt",
            "file'apostrophe.txt",
        ]
        
        # Create files with special names
        for filename in special_files:
            try:
                file_path = self.watch_dir / filename
                file_path.write_text(f"Content of {filename}")
            except Exception as e:
                # Some filesystems might not support certain characters
                print(f"Skipping {filename}: {e}")
                continue
        
        # Wait for processing
        time.sleep(2.0)
        watcher.stop()
        
        # Verify files were detected
        detected_count = 0
        for filename in special_files:
            file_path = self.watch_dir / filename
            if file_path.exists():
                history = watcher.get_file_history(str(file_path.resolve()))
                if len(history) > 0:
                    detected_count += 1
                    assert history[0]['event_type'] == 'file_created'
        
        # Should detect at least most of the files
        assert detected_count >= len(special_files) * 0.8, \
            f"Only detected {detected_count}/{len(special_files)} special files"
    
    def test_add_file_unicode_names(self):
        """Test adding files with unicode characters"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Unicode filenames
        unicode_files = [
            "hello_世界.txt",          # Chinese
            "привет_мир.txt",         # Russian
            "مرحبا_عالم.txt",         # Arabic
            "γειά_σου_κόσμε.txt",     # Greek
            "emoji_😀🎉🌟.txt",       # Emojis
            "café_français.txt",      # Accented characters
            "ñoño_español.txt",       # Spanish
        ]
        
        created_files = []
        for filename in unicode_files:
            try:
                file_path = self.watch_dir / filename
                file_path.write_text(f"Unicode content: {filename}")
                created_files.append(file_path)
            except Exception as e:
                print(f"Skipping {filename}: {e}")
        
        # Wait for processing
        time.sleep(2.0)
        watcher.stop()
        
        # Verify unicode files were detected
        for file_path in created_files:
            history = watcher.get_file_history(str(file_path.resolve()))
            assert len(history) > 0, f"Unicode file {file_path.name} was not detected"
            assert history[0]['event_type'] == 'file_created'
    
    def test_add_file_verify_content_capture(self):
        """Test that file content is properly captured"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Create file with known content
        test_file = self.watch_dir / "content_test.txt"
        test_content = "Line 1\nLine 2\nLine 3\nSpecial chars: @#$%^&*()"
        test_file.write_text(test_content)
        
        time.sleep(1.0)
        watcher.stop()
        
        # Get file history
        history = watcher.get_file_history(str(test_file.resolve()))
        assert len(history) > 0
        
        # Verify we can retrieve the content
        event = history[0]
        version_id = event['version_id']
        
        # Check if content can be retrieved (if the storage supports it)
        # This depends on the implementation
        assert 'has_syft_archive' in event
        if event.get('has_syft_archive'):
            # Verify a SyftMessage was created
            assert event.get('syft_message_id') is not None
            
            # Get the archive and verify its contents
            archive_path = get_version_archive(self.log_dir, version_id)
            assert archive_path is not None, "Should have a SyftMessage archive"
            
            # Verify the archive contains our file with correct content
            verify_syft_message_content(
                archive_path=archive_path,
                expected_filename='content_test.txt',
                expected_content=test_content
            )
            
            # Also verify metadata contains file info
            metadata_list = get_archive_metadata(archive_path)
            assert len(metadata_list) > 0, "Should have metadata in archive"
            
            # Check that at least one metadata entry has our file info
            found_file_info = False
            for metadata in metadata_list:
                # File metadata might be at top level or nested
                if 'event_type' in metadata:
                    # Top level metadata
                    if (metadata.get('event_type') == 'file_created' and
                        metadata.get('file_name') == 'content_test.txt'):
                        assert metadata.get('size') == len(test_content.encode())
                        found_file_info = True
                        break
                elif 'metadata' in metadata:
                    # Nested metadata
                    file_metadata = metadata['metadata']
                    if (file_metadata.get('event_type') == 'file_created' and
                        file_metadata.get('file_name') == 'content_test.txt'):
                        assert file_metadata.get('size') == len(test_content.encode())
                        found_file_info = True
                        break
            
            assert found_file_info, "Should find file info in metadata"
    
    def test_add_file_rapid_succession(self):
        """Test adding multiple files rapidly"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Create many files rapidly
        num_files = 20
        for i in range(num_files):
            file_path = self.watch_dir / f"rapid_file_{i:03d}.txt"
            file_path.write_text(f"Rapid file content {i}")
            # Minimal delay to stress test
            time.sleep(0.01)
        
        # Wait for all to be processed
        time.sleep(2.0)
        watcher.stop()
        
        # Verify all files were detected
        detected = 0
        for i in range(num_files):
            file_path = self.watch_dir / f"rapid_file_{i:03d}.txt"
            history = watcher.get_file_history(str(file_path.resolve()))
            if len(history) > 0:
                detected += 1
        
        assert detected == num_files, \
            f"Only detected {detected}/{num_files} rapidly created files"
    
    def test_add_file_stats_tracking(self):
        """Test that watcher stats are properly updated"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Get initial stats
        initial_stats = watcher.get_stats()
        initial_created = initial_stats.get('files_created', 0)
        
        # Create some files
        num_files = 5
        for i in range(num_files):
            file_path = self.watch_dir / f"stats_test_{i}.txt"
            file_path.write_text(f"Stats test {i}")
            time.sleep(0.1)
        
        time.sleep(1.0)
        
        # Get final stats
        final_stats = watcher.get_stats()
        final_created = final_stats.get('files_created', 0)
        
        watcher.stop()
        
        # Verify stats were updated
        assert final_created - initial_created == num_files, \
            f"Stats show {final_created - initial_created} files created, expected {num_files}"
        
        assert final_stats['tracked_files'] >= num_files
    
    def test_raw_archive_structure(self):
        """Test that we can directly read files from the raw archive structure"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Create test files with different content
        files_to_test = [
            ("simple.txt", "Simple text content"),
            ("unicode.txt", "Unicode: 你好世界 🌍"),
            ("multiline.txt", "Line 1\nLine 2\nLine 3"),
            ("binary.dat", b"\x00\x01\x02\x03\x04\x05"),
        ]
        
        for filename, content in files_to_test:
            file_path = self.watch_dir / filename
            if isinstance(content, bytes):
                file_path.write_bytes(content)
            else:
                file_path.write_text(content)
        
        time.sleep(1.5)
        watcher.stop()
        
        # Verify each file's archive
        for filename, expected_content in files_to_test:
            file_path = self.watch_dir / filename
            history = watcher.get_file_history(str(file_path.resolve()))
            assert len(history) > 0
            
            version_id = history[0]['version_id']
            
            # Verify version metadata exists
            verify_version_metadata(self.log_dir, version_id, {
                'version_id': version_id,
                'file_name': filename
            })
            
            # Get archive and verify contents
            archive_path = get_version_archive(self.log_dir, version_id)
            assert archive_path is not None, f"Should have archive for {filename}"
            
            # Verify the file content in the archive
            verify_syft_message_content(
                archive_path=archive_path,
                expected_filename=filename,
                expected_content=expected_content
            )
            
            # Verify metadata is present
            metadata_list = get_archive_metadata(archive_path)
            assert len(metadata_list) > 0, "Should have metadata in archive"


if __name__ == "__main__":
    # Run a simple test
    test = TestAddFile()
    test.setup_method()
    try:
        test.test_add_single_text_file()
        print("✓ Basic file addition test passed!")
    finally:
        test.teardown_method()