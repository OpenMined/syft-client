#!/usr/bin/env python3
"""
Test different file creation methods in isolation to see which ones avoid modify events
"""
import tempfile
import time
import os
import subprocess
from pathlib import Path
from syft_sync import SyftWatcher
from tests.test_utils import get_archive_metadata

def test_creation_method_isolated(method_name, creation_func):
    """Test a specific file creation method in complete isolation"""
    print(f"\n=== Testing: {method_name} ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        watch_dir = Path(tmpdir) / 'watched'
        log_dir = Path(tmpdir) / 'logs'
        watch_dir.mkdir()
        log_dir.mkdir()
        
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
        
        events = []
        for i, archive in enumerate(archives):
            metadata_list = get_archive_metadata(archive)
            for metadata in metadata_list:
                event_type = metadata.get('event_type', 'unknown')
                file_name = metadata.get('file_name', 'unknown')
                events.append((event_type, file_name))
                print(f"  {i+1}. {event_type} - {file_name}")
        
        return len(archives), events

def main():
    methods = [
        # Method 1: Standard write_text with content (baseline)
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
        
        # Method 7: Shell touch command
        ("shell touch command", 
         lambda wd: subprocess.run(['touch', str(wd / "test7.txt")], check=True)),
        
        # Method 8: Create empty file with explicit write
        ("open() write empty string", 
         lambda wd: open(wd / "test8.txt", 'w').write("")),
        
        # Method 9: Create with truncate flag
        ("open() with w mode (truncate)", 
         lambda wd: open(wd / "test9.txt", 'w').close()),
    ]
    
    results = {}
    
    for method_name, creation_func in methods:
        try:
            event_count, events = test_creation_method_isolated(method_name, creation_func)
            results[method_name] = (event_count, events)
        except Exception as e:
            print(f"  ERROR: {e}")
            results[method_name] = (f"Failed: {e}", [])
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY - Event counts by creation method:")
    print(f"{'='*80}")
    
    for method, (count, events) in results.items():
        event_types = [event[0] for event in events] if isinstance(events, list) else []
        print(f"{method:<35} -> {count} events: {event_types}")
    
    # Find methods with only 1 event (pure create)
    single_event_methods = [(method, events) for method, (count, events) in results.items() 
                           if isinstance(count, int) and count == 1]
    if single_event_methods:
        print(f"\n✅ Methods with only 1 event (pure create):")
        for method, events in single_event_methods:
            event_types = [event[0] for event in events]
            print(f"   - {method}: {event_types}")
    else:
        print(f"\n❌ No methods found with only 1 event")
    
    # Find methods with 2+ events (create + modify)
    multi_event_methods = [(method, events) for method, (count, events) in results.items() 
                          if isinstance(count, int) and count > 1]
    if multi_event_methods:
        print(f"\n⚠️  Methods with multiple events:")
        for method, events in multi_event_methods:
            event_types = [event[0] for event in events]
            print(f"   - {method}: {event_types}")

if __name__ == "__main__":
    main()