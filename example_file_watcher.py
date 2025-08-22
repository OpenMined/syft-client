#!/usr/bin/env python3
"""
Simple example of using syftbox_watcher
"""

import requests
import time
import json

# Base URL for the watcher service
BASE_URL = "http://localhost:8000"  # syft_serve default port

def main():
    # List available SyftBox directories
    print("📁 Listing available SyftBox directories...")
    response = requests.get(f"{BASE_URL}/list")
    data = response.json()
    
    print(json.dumps(data, indent=2))
    
    if not data.get("syftboxes"):
        print("\nNo SyftBox directories found. Create one by authenticating with syft_client.")
        return
    
    # Start watching the first available SyftBox
    first_box = data["syftboxes"][0]
    email = first_box["email"]
    
    print(f"\n👀 Starting to watch {email}...")
    response = requests.post(f"{BASE_URL}/start/{email}")
    print(response.json())
    
    # Check status
    print("\n📊 Watcher status:")
    response = requests.get(f"{BASE_URL}/status")
    print(json.dumps(response.json(), indent=2))
    
    # Wait a bit for some events
    print("\n⏳ Monitoring for file changes for 10 seconds...")
    print("   (Try creating or modifying files in the SyftBox directory)")
    time.sleep(10)
    
    # Get events
    print("\n📋 Recent events:")
    response = requests.get(f"{BASE_URL}/events?limit=10")
    events = response.json()
    
    if events:
        for event in events:
            print(f"  - {event['event_type']}: {event['src_path']} at {event['timestamp']}")
    else:
        print("  No events captured yet.")
    
    # Stop watching
    print(f"\n🛑 Stopping watcher for {email}...")
    response = requests.post(f"{BASE_URL}/stop/{email}")
    print(response.json())


if __name__ == "__main__":
    main()