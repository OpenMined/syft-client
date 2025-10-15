#!/usr/bin/env python3
"""Test script to debug sync functionality"""

import syft_client as sc
import time
from pathlib import Path

print("Testing sync functionality...")
print("=" * 50)

# Test login
print("\n1. Testing login for liamtrask@gmail.com...")
try:
    client1 = sc.login("liamtrask@gmail.com")
    print("✅ Login successful!")
    
    # Check if watcher started
    print("\n2. Checking watcher status...")
    if hasattr(client1, 'watcher'):
        print("✅ Watcher attribute exists")
    else:
        print("❌ Watcher attribute missing!")
        
    # Check sync services
    print("\n3. Checking sync services...")
    if hasattr(client1, 'sync') and hasattr(client1.sync, 'services'):
        print("✅ Sync services exist")
        status = client1.sync_status(verbose=True)
        print(f"Sync status: {status}")
    else:
        print("❌ Sync services missing!")
        
    # Test file creation
    print("\n4. Testing file sync...")
    test_dir = Path(client1.folder) / "datasites" / client1.email / "test_sync"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = test_dir / "test_file.txt"
    test_file.write_text("Testing sync at " + str(time.time()))
    print(f"✅ Created test file: {test_file}")
    
    # Wait a bit
    print("\n5. Waiting 10 seconds for sync...")
    time.sleep(10)
    
    # Check sync activity
    print("\n6. Checking sync activity...")
    # This would normally check logs or sync history
    
except Exception as e:
    print(f"❌ Error during testing: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 50)
print("Test complete!")