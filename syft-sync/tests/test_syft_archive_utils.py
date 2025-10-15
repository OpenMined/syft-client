"""
Tests specifically for SyftMessage archive manipulation utilities
"""
import tempfile
import json
from pathlib import Path

import pytest

from syft_sync import SyftWatcher
from .test_utils import (
    extract_syft_archive,
    read_file_from_archive,
    get_archive_metadata,
    verify_syft_message_content,
    get_version_archive,
    verify_version_metadata
)


class TestSyftArchiveUtils:
    """Test the utility functions for working with SyftMessage archives"""
    
    def setup_method(self):
        """Setup test directories"""
        self.temp_dir = tempfile.mkdtemp()
        self.watch_dir = Path(self.temp_dir) / "watched"
        self.log_dir = Path(self.temp_dir) / "logs"
        self.watch_dir.mkdir(parents=True)
        self.log_dir.mkdir(parents=True)
        
    def teardown_method(self):
        """Cleanup test directories"""
        import shutil
        import os
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_extract_syft_archive(self):
        """Test extracting a SyftMessage archive"""
        # Create a file and let watcher archive it
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        test_file = self.watch_dir / "test.txt"
        test_file.write_text("Test content")
        
        import time
        time.sleep(1.0)
        watcher.stop()
        
        # Get the archive
        history = watcher.get_file_history(str(test_file.resolve()))
        version_id = history[0]['version_id']
        archive_path = get_version_archive(self.log_dir, version_id)
        
        # Extract it
        info = extract_syft_archive(archive_path)
        try:
            # Verify structure
            assert info["temp_dir"] is not None
            assert info["message_dir"].exists()
            assert info["data_dir"].exists()
            assert len(info["metadata_files"]) > 0
            assert len(info["data_files"]) > 0
            
            # Verify the file is there
            test_files = list(info["data_dir"].glob("test.txt"))
            assert len(test_files) == 1
            assert test_files[0].read_text() == "Test content"
        finally:
            # Clean up
            import shutil
            shutil.rmtree(info["temp_dir"], ignore_errors=True)
    
    def test_read_file_from_archive(self):
        """Test reading specific files from archive"""
        # Create files
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        
        # Create different file types
        text_file = self.watch_dir / "text.txt"
        text_file.write_text("Hello World")
        
        binary_file = self.watch_dir / "binary.bin"
        binary_file.write_bytes(b"\x89PNG\r\n\x1a\n")
        
        import time
        time.sleep(1.0)
        watcher.stop()
        
        # Read text file from archive
        text_history = watcher.get_file_history(str(text_file.resolve()))
        text_archive = get_version_archive(self.log_dir, text_history[0]['version_id'])
        
        text_content = read_file_from_archive(text_archive, "text.txt")
        assert text_content == "Hello World"
        assert isinstance(text_content, str)
        
        # Read binary file from archive
        binary_history = watcher.get_file_history(str(binary_file.resolve()))
        binary_archive = get_version_archive(self.log_dir, binary_history[0]['version_id'])
        
        binary_content = read_file_from_archive(binary_archive, "binary.bin")
        assert binary_content == b"\x89PNG\r\n\x1a\n"
        assert isinstance(binary_content, bytes)
    
    def test_get_archive_metadata(self):
        """Test extracting metadata from archives"""
        # Create a file
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        test_file = self.watch_dir / "metadata_test.txt"
        test_file.write_text("Content for metadata test")
        
        import time
        time.sleep(1.0)
        watcher.stop()
        
        # Get metadata
        history = watcher.get_file_history(str(test_file.resolve()))
        archive_path = get_version_archive(self.log_dir, history[0]['version_id'])
        
        metadata_list = get_archive_metadata(archive_path)
        assert len(metadata_list) > 0
        
        # Check metadata content
        found_file_info = False
        for metadata in metadata_list:
            # Could be at top level or nested
            if metadata.get('file_name') == 'metadata_test.txt':
                found_file_info = True
                assert metadata.get('event_type') == 'file_created'
                assert metadata.get('size') == len("Content for metadata test".encode())
                break
            elif 'metadata' in metadata and metadata['metadata'].get('file_name') == 'metadata_test.txt':
                found_file_info = True
                assert metadata['metadata'].get('event_type') == 'file_created'
                break
        
        assert found_file_info, "Should find file information in metadata"
    
    def test_verify_syft_message_content(self):
        """Test the comprehensive verification function"""
        # Create multiple files
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        
        files = [
            ("verify1.txt", "First file content"),
            ("verify2.json", json.dumps({"key": "value", "number": 42})),
            ("verify3.bin", b"\x00\x01\x02\x03")
        ]
        
        for filename, content in files:
            file_path = self.watch_dir / filename
            if isinstance(content, bytes):
                file_path.write_bytes(content)
            else:
                file_path.write_text(content)
        
        import time
        time.sleep(1.5)
        watcher.stop()
        
        # Verify each file
        for filename, expected_content in files:
            file_path = self.watch_dir / filename
            history = watcher.get_file_history(str(file_path.resolve()))
            archive_path = get_version_archive(self.log_dir, history[0]['version_id'])
            
            # This should not raise any assertions
            verify_syft_message_content(
                archive_path=archive_path,
                expected_filename=filename,
                expected_content=expected_content
            )
    
    def test_verify_version_metadata(self):
        """Test version metadata verification"""
        # Create a file
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        test_file = self.watch_dir / "version_test.txt"
        test_file.write_text("Version test content")
        
        import time
        time.sleep(1.0)
        watcher.stop()
        
        # Verify metadata
        history = watcher.get_file_history(str(test_file.resolve()))
        version_id = history[0]['version_id']
        
        verify_version_metadata(self.log_dir, version_id, {
            'version_id': version_id,
            'event_type': 'file_created',
            'file_name': 'version_test.txt',
            'has_syft_archive': True
        })
    
    def test_archive_not_found(self):
        """Test handling of missing archives"""
        # Non-existent version
        archive = get_version_archive(self.log_dir, "non_existent_version")
        assert archive is None
    
    def test_file_not_in_archive(self):
        """Test handling when file is not found in archive"""
        # Create a file
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        test_file = self.watch_dir / "exists.txt"
        test_file.write_text("This file exists")
        
        import time
        time.sleep(1.0)
        watcher.stop()
        
        # Try to read non-existent file from archive
        history = watcher.get_file_history(str(test_file.resolve()))
        archive_path = get_version_archive(self.log_dir, history[0]['version_id'])
        
        with pytest.raises(FileNotFoundError):
            read_file_from_archive(archive_path, "does_not_exist.txt")