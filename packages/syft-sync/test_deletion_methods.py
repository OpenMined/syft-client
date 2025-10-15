#!/usr/bin/env python3
"""
Test different file deletion methods to see which ones generate fewer events
"""
import tempfile
import time
import os
import subprocess
from pathlib import Path
from syft_sync import SyftWatcher
from tests.test_utils import get_archive_metadata

def test_deletion_method(method_name, deletion_func):
    """Test a specific file deletion method"""
    print(f"\n=== Testing deletion: {method_name} ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        watch_dir = Path(tmpdir) / 'watched'
        log_dir = Path(tmpdir) / 'logs'
        watch_dir.mkdir()
        log_dir.mkdir()
        
        watcher = SyftWatcher(str(watch_dir), str(log_dir), verbose=False)
        watcher.start()
        time.sleep(0.5)
        
        # Create file first
        test_file = watch_dir / "test.txt"
        test_file.write_text("content to delete")
        time.sleep(0.5)
        
        print("After creation:")
        archives = list(log_dir.glob('*.tar.gz'))
        for archive in sorted(archives):
            metadata_list = get_archive_metadata(archive)
            for metadata in metadata_list:
                print(f"  {metadata.get('event_type')} - {metadata.get('file_name')}")
        
        # Execute the deletion method
        print(f"Deleting with {method_name}...")
        deletion_func(test_file)
        time.sleep(1.0)
        
        watcher.stop()
        
        print("After deletion:")
        archives = sorted(log_dir.glob('*.tar.gz'))
        deletion_events = []
        for archive in archives:
            metadata_list = get_archive_metadata(archive)
            for metadata in metadata_list:
                event_type = metadata.get('event_type')
                file_name = metadata.get('file_name')
                print(f"  {event_type} - {file_name}")
                if event_type in ['file_modified', 'file_deleted']:
                    deletion_events.append(event_type)
        
        print(f"Deletion events: {deletion_events}")
        return len(deletion_events), deletion_events

def main():
    deletion_methods = [
        # Method 1: Standard Path.unlink() (baseline)
        ("Path.unlink()", 
         lambda f: f.unlink()),
        
        # Method 2: Direct os.unlink()
        ("os.unlink()", 
         lambda f: os.unlink(str(f))),
        
        # Method 3: Direct os.remove() (same as unlink)
        ("os.remove()", 
         lambda f: os.remove(str(f))),
        
        # Method 4: Shell rm command
        ("shell rm", 
         lambda f: subprocess.run(['rm', str(f)], check=True)),
        
        # Method 5: Shell rm -f (force)
        ("shell rm -f", 
         lambda f: subprocess.run(['rm', '-f', str(f)], check=True)),
        
        # Method 6: Truncate to 0 then delete
        ("truncate then unlink", 
         lambda f: [f.write_text(""), f.unlink()]),
        
        # Method 7: Move to temp then delete
        ("move then delete", 
         lambda f: [f.rename(f.parent / (f.name + ".tmp")), 
                   (f.parent / (f.name + ".tmp")).unlink()]),
        
        # Method 8: Open with truncate mode then delete
        ("open truncate then unlink", 
         lambda f: [open(f, 'w').close(), f.unlink()]),
        
        # Method 9: Move outside watch dir (simulated delete)
        ("move outside watch dir", 
         lambda f: f.rename(f.parent.parent / "moved_file.txt")),
        
        # Method 10: Change permissions then delete
        ("chmod then unlink", 
         lambda f: [f.chmod(0o000), f.unlink()]),
    ]
    
    results = {}
    
    for method_name, deletion_func in deletion_methods:
        try:
            event_count, events = test_deletion_method(method_name, deletion_func)
            results[method_name] = (event_count, events)
        except Exception as e:
            print(f"  ERROR: {e}")
            results[method_name] = (f"Failed: {e}", [])
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY - Deletion event counts by method:")
    print(f"{'='*80}")
    
    for method, (count, events) in results.items():
        print(f"{method:<30} -> {count} deletion events: {events}")
    
    # Find methods with fewer deletion events
    min_events = min([count for count, events in results.values() if isinstance(count, int)])
    minimal_methods = [(method, events) for method, (count, events) in results.items() 
                      if isinstance(count, int) and count == min_events]
    
    if minimal_methods:
        print(f"\n✅ Methods with minimal deletion events ({min_events}):")
        for method, events in minimal_methods:
            print(f"   - {method}: {events}")
    
    # Check if any method avoids file_modified during deletion
    no_modify_methods = [(method, events) for method, (count, events) in results.items() 
                        if isinstance(events, list) and 'file_modified' not in events]
    
    if no_modify_methods:
        print(f"\n🎯 Methods that avoid file_modified during deletion:")
        for method, events in no_modify_methods:
            print(f"   - {method}: {events}")
    else:
        print(f"\n❌ No methods found that avoid file_modified events during deletion")

if __name__ == "__main__":
    main()