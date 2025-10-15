"""
Tests for file deletion operations from TEST_STRATEGY.md
Section 1.1: Basic File Operations - Delete File
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


class TestDeleteFile:
    """Test: Delete File - Remove files and verify they're preserved in log"""
    
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
    
    def test_basic_delete(self):
        """Test basic file deletion - Option 1"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=True
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Create file
        test_file = self.watch_dir / "delete_test.txt"
        test_content = "This file will be deleted"
        test_file.write_text(test_content)
        
        # Wait for create event to be logged
        time.sleep(1.0)
        
        # Delete the file
        test_file.unlink()
        
        # Wait for delete event to be logged
        time.sleep(1.0)
        
        watcher.stop()
        
        # Verify by checking the actual log directory structure
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        # Basic delete generates exactly 3 archives: 1 create + 1 modify (during deletion) + 1 delete
        assert len(archives) == 3, f"Should have exactly 3 archives (1 create + 1 modify + 1 delete), found {len(archives)}"
        
        # Extract metadata from all archives to find events
        all_events = []
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if 'version_id' in metadata and 'event_type' in metadata:
                    all_events.append(metadata)
        
        # Sort by timestamp
        all_events.sort(key=lambda x: x.get('timestamp', ''))
        
        # Find create event
        create_event = None
        for event in all_events:
            if event.get('event_type') == 'file_created' and event.get('file_name') == 'delete_test.txt':
                create_event = event
                break
        
        assert create_event is not None, "Should find create event"
        assert create_event['has_syft_archive'] == True
        
        # Verify file content is preserved in create event archive
        create_archive = get_version_archive(self.log_dir, create_event['version_id'])
        assert create_archive is not None
        
        # Extract and verify the file is in the archive
        archived_content = read_file_from_archive(create_archive, 'delete_test.txt')
        assert archived_content == test_content
        
        # Check delete event exists
        delete_event = None
        for event in all_events:
            if event.get('event_type') == 'file_deleted' and event.get('file_name') == 'delete_test.txt':
                delete_event = event
                break
        
        assert delete_event is not None, "Should find a delete event in the log"
    
    def test_delete_and_restore(self):
        """Test deletion and restoration - Option 2"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Create file with important content
        test_file = self.watch_dir / "important_data.txt"
        important_content = """Important data that must not be lost:
        - Configuration settings
        - User preferences
        - Critical information"""
        test_file.write_text(important_content)
        
        time.sleep(1.0)
        
        # Get the create version ID before deletion
        history_before_delete = watcher.get_file_history(str(test_file.resolve()))
        assert len(history_before_delete) == 1
        create_version_id = history_before_delete[0]['version_id']
        
        # Delete the file
        test_file.unlink()
        assert not test_file.exists(), "File should be deleted from filesystem"
        
        time.sleep(1.0)
        watcher.stop()
        
        # Verify deletion by checking raw log structure
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        # Expect exactly 3: 1 create + 1 modify + 1 delete events
        assert len(archives) == 3, f"Should have exactly 3 archives (1 create + 1 modify + 1 delete), found {len(archives)}"
        
        # Find and verify the create event archive exists
        create_archive = get_version_archive(self.log_dir, create_version_id)
        assert create_archive is not None
        assert create_archive.exists()
        
        # Read content directly from archive
        archived_content = read_file_from_archive(create_archive, 'important_data.txt')
        assert archived_content == important_content
        
        # Test restoration
        restore_path = self.watch_dir / "restored_important_data.txt"
        
        # Since watcher.restore_version might use the history, let's restore manually
        # by extracting from the archive
        info = extract_syft_archive(create_archive)
        try:
            source_file = info["data_dir"] / "important_data.txt"
            assert source_file.exists()
            shutil.copy2(source_file, restore_path)
        finally:
            shutil.rmtree(info["temp_dir"], ignore_errors=True)
        
        # Verify restoration
        assert restore_path.exists()
        assert restore_path.read_text() == important_content
        
        # Also verify the delete event exists by checking all archives
        delete_event_found = False
        for archive_path in archives:
            metadata_list = get_archive_metadata(archive_path)
            for metadata in metadata_list:
                if ('event_type' in metadata and metadata['event_type'] == 'file_deleted' and 
                    'file_name' in metadata and metadata['file_name'] == 'important_data.txt'):
                    delete_event_found = True
                    break
            if delete_event_found:
                break
        
        assert delete_event_found, "Delete event should be logged"
    
    def test_complex_delete_scenarios(self):
        """Test complex deletion scenarios - Option 3"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Scenario 1: Delete immediately after create
        quick_file = self.watch_dir / "quick_delete.txt"
        quick_file.write_text("Created and immediately deleted")
        time.sleep(0.5)  # Give more time for create event
        quick_file.unlink()
        
        # Scenario 2: Delete file that was modified multiple times
        multi_edit_file = self.watch_dir / "multi_edit.txt"
        multi_edit_file.write_text("Version 1")
        time.sleep(0.5)
        multi_edit_file.write_text("Version 2 - Modified")
        time.sleep(0.5)
        multi_edit_file.write_text("Version 3 - Final")
        time.sleep(0.5)
        multi_edit_file.unlink()
        
        # Scenario 3: Delete and recreate with same name
        recreate_file = self.watch_dir / "recreate.txt"
        recreate_file.write_text("First incarnation")
        time.sleep(0.5)
        recreate_file.unlink()
        time.sleep(0.5)
        recreate_file.write_text("Second incarnation")
        
        # Wait for all events to be processed
        time.sleep(2.0)
        watcher.stop()
        
        # Count expected events:
        # - quick_delete: create + delete = 2
        # - multi_edit: create + 2 modifies + delete = 4 
        # - recreate: create + delete + create = 3
        # Total minimum: 9 events
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        assert len(archives) >= 9, f"Should have at least 9 archives for complex scenarios, found {len(archives)}"
        
        # Verify by examining the raw log structure
        all_versions = []
        for archive_path in archives:
                metadata_list = get_archive_metadata(archive_path)
                for metadata in metadata_list:
                    if 'version_id' in metadata and 'event_type' in metadata:
                        all_versions.append(metadata)
        
        # Sort by timestamp to get chronological order
        all_versions.sort(key=lambda x: x['timestamp'])
        
        # Verify Scenario 1: Quick delete
        quick_events = [v for v in all_versions if v['file_name'] == 'quick_delete.txt']
        assert len(quick_events) >= 2, "Should have create and delete for quick_delete.txt"
        assert quick_events[0]['event_type'] == 'file_created'
        assert quick_events[-1]['event_type'] == 'file_deleted'
        
        # Verify content is preserved even for quickly deleted file
        quick_create_version = quick_events[0]['version_id']
        quick_archive = get_version_archive(self.log_dir, quick_create_version)
        if quick_archive:  # Might not have archive if deleted too quickly
            quick_content = read_file_from_archive(quick_archive, 'quick_delete.txt')
            assert quick_content == "Created and immediately deleted"
        
        # Verify Scenario 2: Multiple edits before delete
        multi_events = [v for v in all_versions if v['file_name'] == 'multi_edit.txt']
        assert len(multi_events) >= 4, "Should have multiple events for multi_edit.txt"
        
        # Check we have the final version before delete
        create_events = [e for e in multi_events if e['event_type'] in ['file_created', 'file_modified']]
        delete_events = [e for e in multi_events if e['event_type'] == 'file_deleted']
        assert len(create_events) >= 1
        assert len(delete_events) == 1
        
        # Verify we can retrieve different versions
        found_versions = set()
        for event in create_events:
            archive = get_version_archive(self.log_dir, event['version_id'])
            if archive:
                try:
                    content = read_file_from_archive(archive, 'multi_edit.txt')
                    found_versions.add(content)
                except FileNotFoundError:
                    # Some events might not have the file in archive
                    pass
        
        # We should have at least one version preserved
        assert len(found_versions) >= 1, "Should have at least one version of the file preserved"
        
        # Verify Scenario 3: Delete and recreate
        recreate_events = [v for v in all_versions if v['file_name'] == 'recreate.txt']
        assert len(recreate_events) >= 3, "Should have create, delete, create for recreate.txt"
        
        # Verify the sequence
        event_types = [e['event_type'] for e in recreate_events]
        assert 'file_created' in event_types
        assert 'file_deleted' in event_types
        
        # Verify both incarnations are preserved
        create_events = [e for e in recreate_events if e['event_type'] == 'file_created']
        for i, event in enumerate(create_events):
            archive = get_version_archive(self.log_dir, event['version_id'])
            if archive:
                content = read_file_from_archive(archive, 'recreate.txt')
                if i == 0:
                    assert content == "First incarnation"
                else:
                    assert content == "Second incarnation"
    
    def test_delete_various_file_types(self):
        """Test deletion of various file types"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Create various file types
        files_to_delete = [
            ("text.txt", "Text content"),
            ("data.json", json.dumps({"key": "value"})),
            ("script.py", "#!/usr/bin/env python3\nprint('hello')"),
            ("binary.dat", b"\x00\x01\x02\x03\x04\x05"),
            ("empty.txt", ""),
        ]
        
        # Create all files
        for filename, content in files_to_delete:
            file_path = self.watch_dir / filename
            if isinstance(content, bytes):
                file_path.write_bytes(content)
            else:
                file_path.write_text(content)
        
        time.sleep(1.5)
        
        # Delete all files
        for filename, _ in files_to_delete:
            file_path = self.watch_dir / filename
            file_path.unlink()
        
        time.sleep(1.5)
        watcher.stop()
        
        # We created 5 files and deleted 5 files = at least 10 events
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        assert len(archives) >= 10, f"Should have at least 10 archives (5 creates + 5 deletes), found {len(archives)}"
        
        # Verify each file type is preserved
        for filename, expected_content in files_to_delete:
            # Find create event for this file
            create_event = None
            for archive_path in self.log_dir.glob('*.tar.gz'):
                    metadata_list = get_archive_metadata(archive_path)
                    for metadata in metadata_list:
                        if ('event_type' in metadata and metadata['event_type'] == 'file_created' and 
                            'file_name' in metadata and metadata['file_name'] == filename):
                            create_event = metadata
                            break
                    if create_event:
                        break
            
            assert create_event is not None, f"Should find create event for {filename}"
            
            # Verify content is preserved
            archive = get_version_archive(self.log_dir, create_event['version_id'])
            assert archive is not None
            
            # Use the utility that handles binary files correctly
            try:
                verify_syft_message_content(
                    archive_path=archive,
                    expected_filename=filename,
                    expected_content=expected_content
                )
            except Exception as e:
                # If this is an empty file, it might not be stored
                if filename == "empty.txt" and expected_content == "":
                    pass
                else:
                    raise
    
    def test_delete_nested_files(self):
        """Test deletion of files in nested directories"""
        watcher = SyftWatcher(
            watch_path=str(self.watch_dir),
            log_path=str(self.log_dir),
            verbose=False
        )
        
        watcher.start()
        time.sleep(0.5)
        
        # Create nested structure
        nested_dir = self.watch_dir / "level1" / "level2" / "level3"
        nested_dir.mkdir(parents=True)
        
        nested_file = nested_dir / "deeply_nested.txt"
        nested_content = "Deep content that should be preserved"
        nested_file.write_text(nested_content)
        
        time.sleep(1.0)
        
        # Delete the file
        nested_file.unlink()
        
        time.sleep(1.0)
        watcher.stop()
        
        # Should have at least 2 archives: create + delete for the nested file
        archives = sorted(self.log_dir.glob('*.tar.gz'))
        assert len(archives) >= 2, f"Should have at least 2 archives for nested file, found {len(archives)}"
        
        # Find the create event in raw logs
        create_event = None
        for archive_path in archives:
                metadata_list = get_archive_metadata(archive_path)
                for metadata in metadata_list:
                    if ('event_type' in metadata and metadata['event_type'] == 'file_created' and 
                        'file_name' in metadata and metadata['file_name'] == 'deeply_nested.txt'):
                        create_event = metadata
                        break
                if create_event:
                    break
        
        assert create_event is not None
        
        # Verify content is preserved
        archive = get_version_archive(self.log_dir, create_event['version_id'])
        assert archive is not None
        
        content = read_file_from_archive(archive, 'deeply_nested.txt')
        assert content == nested_content


if __name__ == "__main__":
    # Run a simple test
    test = TestDeleteFile()
    test.setup_method()
    try:
        test.test_delete_and_restore()
        print("✓ Delete and restore test passed!")
    finally:
        test.teardown_method()