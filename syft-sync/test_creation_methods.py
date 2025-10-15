#!/usr/bin/env python3
"""
Test different file creation methods to see which ones avoid modify events
"""
import tempfile
import time
import os
import subprocess
from pathlib import Path
from syft_sync import SyftWatcher
from tests.test_utils import get_archive_metadata

def test_creation_method(method_name, creation_func, watch_dir, log_dir):
    """Test a specific file creation method"""
    print(f"\n=== Testing: {method_name} ===")
    
    # Clear any existing archives
    for archive in log_dir.glob('*.tar.gz'):
        archive.unlink()
    
    watcher = SyftWatcher(str(watch_dir), str(log_dir), verbose=False)
    watcher.start()
    time.sleep(0.5)
    
    # Execute the creation method
    creation_func(watch_dir)
    time.sleep(1.5)  # Wait for events
    
    watcher.stop()
    
    # Analyze events
    archives = sorted(log_dir.glob('*.tar.gz'))
    print(f"Total archives: {len(archives)}")
    
    for i, archive in enumerate(archives):
        metadata_list = get_archive_metadata(archive)
        for metadata in metadata_list:
            event_type = metadata.get('event_type', 'unknown')
            file_name = metadata.get('file_name', 'unknown')
            timestamp = metadata.get('timestamp', 'unknown')
            print(f"  {i+1}. {event_type} - {file_name}")
    
    return len(archives)

def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        watch_dir = Path(tmpdir) / 'watched'
        log_dir = Path(tmpdir) / 'logs'
        watch_dir.mkdir()
        log_dir.mkdir()
        
        methods = [
            # Method 1: Standard write_text (baseline)
            ("write_text() with content", 
             lambda wd: (wd / "test1.txt").write_text("content")),
            
            # Method 2: Touch to create empty file
            ("touch() empty file", 
             lambda wd: (wd / "test2.txt").touch()),
            
            # Method 3: Open and immediately close (no write)
            ("open() and close() only", 
             lambda wd: open(wd / "test3.txt", 'w').close()),
            
            # Method 4: Create with pathlib and 0 bytes
            ("write_bytes() with empty bytes", 
             lambda wd: (wd / "test4.txt").write_bytes(b"")),
            
            # Method 5: Copy from /dev/null (Unix)
            ("copy from /dev/null", 
             lambda wd: subprocess.run(['cp', '/dev/null', str(wd / "test5.txt")], check=True)),
            
            # Method 6: Create with os.open() and close immediately
            ("os.open() with O_CREAT", 
             lambda wd: os.close(os.open(str(wd / "test6.txt"), os.O_CREAT | os.O_WRONLY, 0o644))),
            
            # Method 7: Create with specific flags
            ("os.open() with O_CREAT|O_EXCL", 
             lambda wd: os.close(os.open(str(wd / "test7.txt"), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644))),
            
            # Method 8: Create then truncate to 0
            ("create and truncate to 0", 
             lambda wd: (lambda f: [f.write_text("temp"), f.write_text("")])(wd / "test8.txt")),
            
            # Method 9: Hard link to empty file
            ("hard link to /dev/null", 
             lambda wd: os.link('/dev/null', str(wd / "test9.txt")) if hasattr(os, 'link') else None),
            
            # Method 10: Create via shell touch command
            ("shell touch command", 
             lambda wd: subprocess.run(['touch', str(wd / "test10.txt")], check=True)),
        ]
        
        results = {}
        
        for method_name, creation_func in methods:
            try:
                event_count = test_creation_method(method_name, creation_func, watch_dir, log_dir)
                results[method_name] = event_count
            except Exception as e:
                print(f"  ERROR: {e}")
                results[method_name] = f"Failed: {e}"
        
        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY - Event counts by creation method:")
        print(f"{'='*60}")
        
        for method, count in results.items():
            print(f"{method:<30} -> {count}")
        
        # Find methods with only 1 event (pure create)
        single_event_methods = [method for method, count in results.items() if count == 1]
        if single_event_methods:
            print(f"\n✅ Methods with only 1 event (pure create):")
            for method in single_event_methods:
                print(f"   - {method}")
        else:
            print(f"\n❌ No methods found with only 1 event")

if __name__ == "__main__":
    main()