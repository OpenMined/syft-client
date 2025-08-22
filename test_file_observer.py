#!/usr/bin/env python3
"""
Test script for SyftBox File Observer
"""
import requests
import time
from pathlib import Path
import json

# Configuration - match the observer script
EMAIL = "andrew@openmined.org"
SYFTBOX_DIR = Path.home() / f"SyftBox_{EMAIL}"
DATASITES_DIR = SYFTBOX_DIR / "datasites"
OUTBOX_DIR = SYFTBOX_DIR / "outbox"

# Server URL
BASE_URL = "http://localhost:8000"

def test_observer():
    print("🧪 Testing SyftBox File Observer\n")
    
    # Check status
    print("1️⃣ Checking observer status...")
    response = requests.get(f"{BASE_URL}/status")
    status = response.json()
    print(f"   Running: {status['running']}")
    print(f"   Messages created: {status['messages_created']}")
    
    # Create a test file
    print("\n2️⃣ Creating a test data file...")
    test_file = DATASITES_DIR / "test_data.csv"
    test_file.write_text("id,name,value\n1,Alice,100\n2,Bob,200")
    print(f"   Created: {test_file}")
    
    # Wait for processing
    time.sleep(2)
    
    # Check messages
    print("\n3️⃣ Checking messages created...")
    response = requests.get(f"{BASE_URL}/messages")
    messages = response.json()
    print(f"   Total messages: {messages['count']}")
    
    if messages['messages']:
        latest = messages['messages'][-1]
        print(f"   Latest message:")
        print(f"     ID: {latest['id']}")
        print(f"     Event: {latest['event_type']}")
        print(f"     Ready: {latest['ready']}")
    
    # Modify the file
    print("\n4️⃣ Modifying the test file...")
    test_file.write_text("id,name,value\n1,Alice,150\n2,Bob,250\n3,Charlie,300")
    
    time.sleep(2)
    
    # Check updated status
    response = requests.get(f"{BASE_URL}/status")
    status = response.json()
    print(f"   Messages created: {status['messages_created']}")
    
    if status['last_event']:
        print(f"   Last event: {status['last_event']['type']} - {status['last_event']['file']}")
    
    # List all messages in outbox
    print("\n5️⃣ Messages in outbox:")
    if OUTBOX_DIR.exists():
        count = 0
        for msg_dir in sorted(OUTBOX_DIR.iterdir()):
            if msg_dir.is_dir() and msg_dir.name.startswith("gdrive_"):
                count += 1
                print(f"   - {msg_dir.name}")
                
                # Check if message has files
                files_dir = msg_dir / "data" / "files"
                if files_dir.exists():
                    files = list(files_dir.iterdir())
                    print(f"     Files: {[f.name for f in files]}")
        
        print(f"   Total: {count} messages")
    
    # Optional: Clear outbox
    print("\n6️⃣ Clear outbox? (y/n): ", end="")
    if input().lower() == 'y':
        response = requests.post(f"{BASE_URL}/clear")
        result = response.json()
        print(f"   Cleared {result['cleared']} messages")

if __name__ == "__main__":
    test_observer()