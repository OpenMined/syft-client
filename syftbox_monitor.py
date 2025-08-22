#!/usr/bin/env python3
"""
SyftBox Monitor - Integrated file watcher for syft_client

This integrates with syft_client to automatically monitor SyftBox directories
when a client is authenticated.
"""

import syft_client as sc
import syft_serve as ss
from pathlib import Path
from typing import Dict, Optional, Callable, Any
import threading
import time

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
except ImportError:
    print("❌ watchdog not installed. Please run: uv add watchdog")
    exit(1)


class SyftBoxMonitor(FileSystemEventHandler):
    """Monitor SyftBox directories and trigger actions on file changes"""
    
    def __init__(self, client: sc.GDriveUnifiedClient):
        self.client = client
        self.callbacks = {
            'created': [],
            'modified': [],
            'deleted': [],
            'moved': []
        }
        self.observer = None
        
    def on_created(self, event: FileSystemEvent):
        if not event.is_directory:
            self._trigger_callbacks('created', event)
            
    def on_modified(self, event: FileSystemEvent):
        if not event.is_directory:
            self._trigger_callbacks('modified', event)
            
    def on_deleted(self, event: FileSystemEvent):
        if not event.is_directory:
            self._trigger_callbacks('deleted', event)
            
    def on_moved(self, event: FileSystemEvent):
        if not event.is_directory:
            self._trigger_callbacks('moved', event)
    
    def _trigger_callbacks(self, event_type: str, event: FileSystemEvent):
        """Trigger registered callbacks for an event type"""
        for callback in self.callbacks[event_type]:
            try:
                callback(self.client, event)
            except Exception as e:
                print(f"❌ Error in callback: {e}")
    
    def register_callback(self, event_type: str, callback: Callable):
        """Register a callback for specific event types"""
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
    
    def start(self):
        """Start monitoring the SyftBox directory"""
        if not self.client.authenticated:
            raise RuntimeError("Client must be authenticated first")
            
        syftbox_dir = self.client.get_syftbox_directory()
        if not syftbox_dir or not syftbox_dir.exists():
            raise RuntimeError(f"SyftBox directory not found: {syftbox_dir}")
        
        self.observer = Observer()
        self.observer.schedule(self, str(syftbox_dir), recursive=True)
        self.observer.start()
        
        print(f"📁 Monitoring {syftbox_dir}")
        
    def stop(self):
        """Stop monitoring"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            print("🛑 Stopped monitoring")


# Example callback functions
def sync_to_gdrive(client: sc.GDriveUnifiedClient, event: FileSystemEvent):
    """Example: Sync new files to Google Drive"""
    file_path = Path(event.src_path)
    
    # Skip hidden files and temp files
    if file_path.name.startswith('.') or file_path.suffix == '.tmp':
        return
    
    # Get relative path from SyftBox root
    syftbox_dir = client.get_syftbox_directory()
    rel_path = file_path.relative_to(syftbox_dir)
    
    print(f"📤 Would sync to GDrive: {rel_path}")
    # TODO: Implement actual GDrive sync using client._upload_file()


def log_changes(client: sc.GDriveUnifiedClient, event: FileSystemEvent):
    """Example: Log all file changes"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {event.event_type}: {Path(event.src_path).name}")


# API endpoints for syft_serve
def create_monitor_api(monitor: SyftBoxMonitor):
    """Create API endpoints for the monitor"""
    
    def get_status():
        return {
            "monitoring": monitor.observer is not None and monitor.observer.is_alive(),
            "client_email": monitor.client.my_email,
            "syftbox_dir": str(monitor.client.get_syftbox_directory())
        }
    
    def enable_sync():
        monitor.register_callback('created', sync_to_gdrive)
        monitor.register_callback('modified', sync_to_gdrive)
        return {"status": "sync enabled"}
    
    def enable_logging():
        for event_type in ['created', 'modified', 'deleted', 'moved']:
            monitor.register_callback(event_type, log_changes)
        return {"status": "logging enabled"}
    
    return {
        "/monitor/status": get_status,
        "/monitor/enable_sync": enable_sync,
        "/monitor/enable_logging": enable_logging
    }


# Example usage
if __name__ == "__main__":
    print("🚀 SyftBox Monitor Example\n")
    
    # Create and authenticate a client
    print("1️⃣ Creating client...")
    # For demo, we'll use a mock client
    client = sc.GDriveUnifiedClient(email="demo@example.com")
    
    # In real usage:
    # client = sc.create_gdrive_client("user@gmail.com")
    
    # For demo purposes, manually set up the client
    client.my_email = "demo@example.com"
    client.authenticated = True
    client._create_local_syftbox_directory()
    
    # Create monitor
    print("\n2️⃣ Creating monitor...")
    monitor = SyftBoxMonitor(client)
    
    # Register callbacks
    print("\n3️⃣ Registering callbacks...")
    monitor.register_callback('created', log_changes)
    monitor.register_callback('modified', log_changes)
    monitor.register_callback('deleted', log_changes)
    
    # Start monitoring
    print("\n4️⃣ Starting monitor...")
    monitor.start()
    
    # Create API server
    print("\n5️⃣ Creating API server...")
    endpoints = create_monitor_api(monitor)
    
    server = ss.create(
        name="syftbox_monitor",
        endpoints=endpoints,
        force=True,
        expiration_seconds=-1  # Never expire
    )
    
    print(f"""
✅ SyftBox Monitor is running!

Server URL: {server.url}

Try:
- Creating files in ~/SyftBox_demo@example.com/
- Modifying existing files
- Deleting files

API endpoints:
- GET {server.url}/monitor/status         - Check monitor status
- POST {server.url}/monitor/enable_sync   - Enable GDrive sync
- POST {server.url}/monitor/enable_logging - Enable detailed logging

Press Ctrl+C to stop.
""")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        monitor.stop()
        
        # Clean up demo directory
        import shutil
        demo_dir = Path.home() / "SyftBox_demo@example.com"
        if demo_dir.exists():
            shutil.rmtree(demo_dir)
            print(f"Cleaned up demo directory: {demo_dir}")