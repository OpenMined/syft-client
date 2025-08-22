#!/usr/bin/env python3
"""
SyftBox File Watcher using syft_serve

This creates a file watcher service that monitors SyftBox directories
and provides an API to query file changes.
"""

import syft_serve as ss
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import threading
import queue
import time
import json

# Try to import watchdog, provide instructions if not available
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
except ImportError:
    print("❌ watchdog not installed. Please run: pip install watchdog")
    exit(1)


class SyftBoxEventHandler(FileSystemEventHandler):
    """Handles file system events for SyftBox directories"""
    
    def __init__(self, event_queue: queue.Queue):
        self.event_queue = event_queue
        
    def on_any_event(self, event: FileSystemEvent):
        """Capture all events and add to queue"""
        if event.is_directory:
            return
            
        event_data = {
            "event_type": event.event_type,
            "src_path": event.src_path,
            "timestamp": datetime.now().isoformat(),
            "is_directory": event.is_directory
        }
        
        # Add destination path for move events
        if hasattr(event, 'dest_path'):
            event_data["dest_path"] = event.dest_path
            
        self.event_queue.put(event_data)


class SyftBoxWatcher:
    """Main file watcher for SyftBox directories"""
    
    def __init__(self):
        self.observers: Dict[str, Observer] = {}
        self.event_queue = queue.Queue(maxsize=1000)
        self.events: List[Dict[str, Any]] = []
        self.handler = SyftBoxEventHandler(self.event_queue)
        self.running = True
        
        # Start event processor thread
        self.processor_thread = threading.Thread(target=self._process_events)
        self.processor_thread.daemon = True
        self.processor_thread.start()
    
    def _process_events(self):
        """Process events from queue"""
        while self.running:
            try:
                event = self.event_queue.get(timeout=0.1)
                self.events.append(event)
                
                # Keep only last 1000 events
                if len(self.events) > 1000:
                    self.events = self.events[-1000:]
                    
            except queue.Empty:
                continue
    
    def start_watching(self, email: str) -> Dict[str, Any]:
        """Start watching a SyftBox directory for a given email"""
        syftbox_dir = Path.home() / f"SyftBox_{email}"
        
        if not syftbox_dir.exists():
            return {
                "success": False,
                "error": f"SyftBox directory not found: {syftbox_dir}"
            }
        
        # Stop existing observer if any
        if email in self.observers:
            self.stop_watching(email)
        
        # Create and start observer
        observer = Observer()
        observer.schedule(self.handler, str(syftbox_dir), recursive=True)
        observer.start()
        
        self.observers[email] = observer
        
        return {
            "success": True,
            "message": f"Started watching {syftbox_dir}",
            "path": str(syftbox_dir)
        }
    
    def stop_watching(self, email: str) -> Dict[str, Any]:
        """Stop watching a SyftBox directory"""
        if email not in self.observers:
            return {
                "success": False,
                "error": f"Not watching {email}"
            }
        
        observer = self.observers[email]
        observer.stop()
        observer.join()
        del self.observers[email]
        
        return {
            "success": True,
            "message": f"Stopped watching SyftBox_{email}"
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current watcher status"""
        return {
            "watching": list(self.observers.keys()),
            "event_count": len(self.events),
            "queue_size": self.event_queue.qsize()
        }
    
    def get_events(self, limit: int = 100, since: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent events"""
        events = self.events[-limit:]
        
        if since:
            try:
                since_dt = datetime.fromisoformat(since)
                events = [
                    e for e in events 
                    if datetime.fromisoformat(e["timestamp"]) > since_dt
                ]
            except ValueError:
                pass
                
        return events
    
    def cleanup(self):
        """Stop all observers and cleanup"""
        self.running = False
        for email in list(self.observers.keys()):
            self.stop_watching(email)
        self.processor_thread.join()


# Create global watcher instance
watcher = SyftBoxWatcher()


# API Endpoint functions
def start_watching_endpoint(email: str) -> Dict[str, Any]:
    """API endpoint to start watching a SyftBox"""
    return watcher.start_watching(email)


def stop_watching_endpoint(email: str) -> Dict[str, Any]:
    """API endpoint to stop watching a SyftBox"""
    return watcher.stop_watching(email)


def get_status_endpoint() -> Dict[str, Any]:
    """API endpoint to get watcher status"""
    return watcher.get_status()


def get_events_endpoint(limit: int = 100, since: Optional[str] = None) -> List[Dict[str, Any]]:
    """API endpoint to get recent events"""
    return watcher.get_events(limit=limit, since=since)


def list_syftboxes_endpoint() -> Dict[str, Any]:
    """API endpoint to list available SyftBox directories"""
    home = Path.home()
    syftboxes = []
    
    for path in home.iterdir():
        if path.is_dir() and path.name.startswith("SyftBox_"):
            email = path.name.replace("SyftBox_", "")
            syftboxes.append({
                "email": email,
                "path": str(path),
                "is_watching": email in watcher.observers
            })
    
    return {"syftboxes": syftboxes}


# Create the syft_serve server
if __name__ == "__main__":
    print("🚀 Starting SyftBox File Watcher Service...")
    
    # Create server with endpoints
    server = ss.create(
        name="syftbox_watcher",
        endpoints={
            "/start/{email}": start_watching_endpoint,
            "/stop/{email}": stop_watching_endpoint,
            "/status": get_status_endpoint,
            "/events": get_events_endpoint,
            "/list": list_syftboxes_endpoint,
        },
        expiration_seconds=-1,  # Never expire
        force=True  # Replace if exists
    )
    
    print(f"""
📁 SyftBox File Watcher is running!

Server URL: {server.url}

Available endpoints:
- GET  /list                     - List available SyftBox directories
- POST /start/{{email}}            - Start watching a SyftBox
- POST /stop/{{email}}             - Stop watching a SyftBox  
- GET  /status                   - Get watcher status
- GET  /events?limit=100&since=  - Get recent file events

Example:
  curl {server.url}/list
  curl -X POST {server.url}/start/alice@example.com
  curl {server.url}/events?limit=10
""")
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down SyftBox File Watcher...")
        watcher.cleanup()
        print("✅ Cleanup complete")