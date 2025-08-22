#!/usr/bin/env python3
"""
SyftBox File Observer API
Monitors datasites folder and creates SyftMessages for file changes
"""
import syft_serve as ss
import syft_client as sc
from pathlib import Path
import requests
import sys
import time
import json

# Terminate existing servers
ss.servers.terminate_all()

# Configuration
EMAIL = "andrew@openmined.org"
SYFTBOX_DIR = Path.home() / f"SyftBox_{EMAIL}"
DATASITES_DIR = SYFTBOX_DIR / "datasites"
OUTBOX_DIR = SYFTBOX_DIR / "outbox"

# Ensure directories exist
DATASITES_DIR.mkdir(parents=True, exist_ok=True)
OUTBOX_DIR.mkdir(parents=True, exist_ok=True)

# Global state
state = {
    "observer": None,
    "processed_files": set(),
    "messages_created": 0,
    "last_event": None
}

def start_observer():
    """Start the file observer"""
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    
    # Force unbuffered output
    sys.stdout.reconfigure(line_buffering=True)
    
    class DataSitesHandler(FileSystemEventHandler):
        def on_created(self, event):
            if not event.is_directory:
                process_file_event(event, "created")
        
        def on_modified(self, event):
            if not event.is_directory:
                process_file_event(event, "modified")
        
        def on_deleted(self, event):
            if not event.is_directory:
                process_file_event(event, "deleted")
    
    # Create and start observer
    if state["observer"] is None:
        observer = Observer()
        observer.schedule(DataSitesHandler(), str(DATASITES_DIR), recursive=True)
        observer.start()
        state["observer"] = observer
        
        print(f"📁 Monitoring: {DATASITES_DIR}", flush=True)
        return {"status": "Observer started", "monitoring": str(DATASITES_DIR)}
    else:
        return {"status": "Observer already running", "monitoring": str(DATASITES_DIR)}

def process_file_event(event, event_type):
    """Process a file event and create a SyftMessage"""
    file_path = Path(event.src_path)
    
    # Skip hidden files and temporary files
    if file_path.name.startswith('.') or file_path.suffix == '.tmp':
        return
    
    # Skip if we just processed this file (debounce rapid events)
    file_key = f"{file_path}:{event_type}:{time.time()//1}"  # 1 second debounce
    if file_key in state["processed_files"]:
        return
    state["processed_files"].add(file_key)
    
    # Keep only recent processed files
    if len(state["processed_files"]) > 100:
        state["processed_files"] = set(list(state["processed_files"])[-50:])
    
    print(f"🔔 {event_type}: {file_path.name}", flush=True)
    
    # Create SyftMessage for the file change
    try:
        # Determine recipient (for demo, using a default)
        recipient_email = "recipient@example.com"  # In real use, this would be determined by the datasite
        
        # Create the message
        message = sc.SyftMessage.create(
            sender_email=EMAIL,
            recipient_email=recipient_email,
            message_root=OUTBOX_DIR,
            message_type="file_update"
        )
        
        # Add metadata about the event
        message.update_metadata({
            "event_type": event_type,
            "datasite_path": str(file_path.relative_to(DATASITES_DIR)),
            "timestamp": time.time()
        })
        
        # If file exists (not deleted), add it to the message
        if event_type != "deleted" and file_path.exists():
            syftbox_path = f"/{EMAIL}/datasites/{file_path.relative_to(DATASITES_DIR)}"
            message.add_file(
                source_path=file_path,
                syftbox_path=syftbox_path,
                permissions={
                    "read": [recipient_email],
                    "write": [EMAIL],
                    "admin": [EMAIL]
                }
            )
        
        # Add a README explaining the update
        readme_content = f"""
        <html>
        <body>
            <h2>File Update Notification</h2>
            <p><strong>Event:</strong> {event_type}</p>
            <p><strong>File:</strong> {file_path.name}</p>
            <p><strong>Path:</strong> datasites/{file_path.relative_to(DATASITES_DIR)}</p>
            <p><strong>Time:</strong> {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>From:</strong> {EMAIL}</p>
        </body>
        </html>
        """
        message.add_readme(readme_content)
        
        # Finalize the message
        message.finalize()
        
        state["messages_created"] += 1
        state["last_event"] = {
            "type": event_type,
            "file": file_path.name,
            "message_id": message.message_id,
            "time": time.time()
        }
        
        print(f"✅ Created SyftMessage: {message.message_id}", flush=True)
        
    except Exception as e:
        print(f"❌ Error creating SyftMessage: {e}", flush=True)

def get_status():
    """Get observer status"""
    return {
        "running": state["observer"] is not None and state["observer"].is_alive(),
        "messages_created": state["messages_created"],
        "last_event": state["last_event"],
        "monitoring": str(DATASITES_DIR),
        "outbox": str(OUTBOX_DIR)
    }

def list_messages():
    """List messages in outbox"""
    messages = []
    if OUTBOX_DIR.exists():
        for msg_dir in OUTBOX_DIR.iterdir():
            if msg_dir.is_dir() and msg_dir.name.startswith("gdrive_"):
                try:
                    msg = sc.SyftMessage(msg_dir)
                    metadata = msg.get_metadata()
                    messages.append({
                        "id": msg.message_id,
                        "recipient": metadata.get("recipient_email"),
                        "event_type": metadata.get("event_type"),
                        "timestamp": metadata.get("timestamp"),
                        "ready": msg.is_ready
                    })
                except:
                    pass
    
    return {"messages": messages, "count": len(messages)}

def clear_outbox():
    """Clear all messages from outbox (for testing)"""
    import shutil
    count = 0
    if OUTBOX_DIR.exists():
        for msg_dir in OUTBOX_DIR.iterdir():
            if msg_dir.is_dir() and msg_dir.name.startswith("gdrive_"):
                shutil.rmtree(msg_dir)
                count += 1
    
    return {"cleared": count}

# Create the server
server = ss.create(
    name="syftbox_observer",
    dependencies=["watchdog"],
    endpoints={
        "/start": start_observer,
        "/status": get_status,
        "/messages": list_messages,
        "/clear": clear_outbox
    }
)

print(f"\n🚀 SyftBox File Observer API")
print(f"📧 Email: {EMAIL}")
print(f"📁 Monitoring: {DATASITES_DIR}")
print(f"📤 Outbox: {OUTBOX_DIR}")
print(f"\n🌐 Server: {server.url}")
print(f"\nEndpoints:")
print(f"  POST {server.url}/start    - Start monitoring")
print(f"  GET  {server.url}/status   - Check status")
print(f"  GET  {server.url}/messages - List messages created")
print(f"  POST {server.url}/clear    - Clear outbox (testing)")

# Auto-start the observer
print(f"\n🔧 Auto-starting observer...")
response = requests.post(f"{server.url}/start")
print(f"✅ {response.json()['status']}")

print(f"\n📝 Try creating or editing files in:")
print(f"   {DATASITES_DIR}")
print(f"\n💡 Messages will be created in:")
print(f"   {OUTBOX_DIR}")

# Show logs
print(f"\n📋 To view logs:")
print(f"   observer = ss.servers['syftbox_observer']")
print(f"   observer.stdout.lines()[-10:]")

# Keep running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    if state["observer"]:
        state["observer"].stop()
        state["observer"].join()
    print("\n👋 Observer stopped")