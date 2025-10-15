#!/usr/bin/env python3
"""
Debug script to understand filesystem events during file operations
"""
import tempfile
import time
from pathlib import Path
from syft_sync import SyftWatcher
from tests.test_utils import get_archive_metadata

def analyze_events(description, log_dir):
    """Analyze and print events from archives"""
    print(f"\n=== {description} ===")
    archives = sorted(log_dir.glob('*.tar.gz'))
    print(f"Total archives: {len(archives)}")
    
    for i, archive in enumerate(archives):
        metadata_list = get_archive_metadata(archive)
        for metadata in metadata_list:
            event_type = metadata.get('event_type', 'unknown')
            file_name = metadata.get('file_name', 'unknown')
            timestamp = metadata.get('timestamp', 'unknown')
            print(f"  {i+1}. {event_type} - {file_name} - {timestamp}")

def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        watch_dir = Path(tmpdir) / 'watched'
        log_dir = Path(tmpdir) / 'logs'
        watch_dir.mkdir()
        log_dir.mkdir()
        
        # Test 1: Just file creation
        print("TEST 1: File creation only")
        watcher = SyftWatcher(str(watch_dir), str(log_dir), verbose=False)
        watcher.start()
        time.sleep(0.5)
        
        print("Creating file...")
        test_file = watch_dir / 'test.txt'
        test_file.write_text('test content')
        time.sleep(1.5)  # Give time for all events
        
        analyze_events("After file creation", log_dir)
        
        print("\nDeleting file...")
        test_file.unlink()
        time.sleep(1.5)  # Give time for all events
        
        analyze_events("After file deletion", log_dir)
        
        watcher.stop()
        
        # Clear for next test
        for archive in log_dir.glob('*.tar.gz'):
            archive.unlink()
        
        # Test 2: File creation with explicit steps
        print("\n" + "="*60)
        print("TEST 2: Detailed file creation process")
        
        watcher = SyftWatcher(str(watch_dir), str(log_dir), verbose=False)
        watcher.start()
        time.sleep(0.5)
        
        print("Step 1: Creating empty file...")
        test_file2 = watch_dir / 'test2.txt'
        test_file2.touch()  # Create empty file
        time.sleep(1.0)
        analyze_events("After touch()", log_dir)
        
        print("Step 2: Writing content...")
        test_file2.write_text('some content')
        time.sleep(1.0)
        analyze_events("After write_text()", log_dir)
        
        print("Step 3: Deleting file...")
        test_file2.unlink()
        time.sleep(1.0)
        analyze_events("After unlink()", log_dir)
        
        watcher.stop()
        
        # Test 3: Different write methods
        print("\n" + "="*60)
        print("TEST 3: Different write methods")
        
        # Clear logs
        for archive in log_dir.glob('*.tar.gz'):
            archive.unlink()
            
        watcher = SyftWatcher(str(watch_dir), str(log_dir), verbose=False)
        watcher.start()
        time.sleep(0.5)
        
        print("Method 1: Direct write_text() on new file...")
        test_file3 = watch_dir / 'method1.txt'
        test_file3.write_text('content')
        time.sleep(1.0)
        analyze_events("After direct write_text()", log_dir)
        
        print("Method 2: Open, write, close...")
        test_file4 = watch_dir / 'method2.txt'
        with open(test_file4, 'w') as f:
            f.write('content')
        time.sleep(1.0)
        analyze_events("After open/write/close", log_dir)
        
        watcher.stop()

if __name__ == "__main__":
    main()