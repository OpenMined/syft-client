#!/usr/bin/env python3
"""
Notebook-friendly version of SyftBox File Observer
Copy and paste this into a Jupyter notebook
"""

# Cell 1: Setup and start observer
import syft_serve as ss
import syft_client as sc
from pathlib import Path
import requests

# Configuration
EMAIL = "andrew@openmined.org"
SYFTBOX_DIR = Path.home() / f"SyftBox_{EMAIL}"
DATASITES_DIR = SYFTBOX_DIR / "datasites"
OUTBOX_DIR = SYFTBOX_DIR / "outbox"

# Ensure directories exist
DATASITES_DIR.mkdir(parents=True, exist_ok=True)
OUTBOX_DIR.mkdir(parents=True, exist_ok=True)

print(f"📁 SyftBox directory: {SYFTBOX_DIR}")
print(f"📂 Datasites: {DATASITES_DIR}")
print(f"📤 Outbox: {OUTBOX_DIR}")

# Cell 2: Define the observer function
def create_observer():
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    import time
    import sys
    
    # Force unbuffered output
    sys.stdout.reconfigure(line_buffering=True)
    
    class DataSitesHandler(FileSystemEventHandler):
        def on_any_event(self, event):
            if not event.is_directory and not event.src_path.endswith('.tmp'):
                print(f"[{time.strftime('%H:%M:%S')}] {event.event_type}: {Path(event.src_path).name}", flush=True)
                
                # Create SyftMessage
                if event.event_type in ['created', 'modified']:
                    try:
                        file_path = Path(event.src_path)
                        if file_path.exists() and not file_path.name.startswith('.'):
                            # Create message
                            msg = sc.SyftMessage.create(
                                sender_email=EMAIL,
                                recipient_email="recipient@example.com",
                                message_root=OUTBOX_DIR,
                                message_type="file_update"
                            )
                            
                            # Add file
                            msg.add_file(
                                source_path=file_path,
                                syftbox_path=f"/{EMAIL}/datasites/{file_path.relative_to(DATASITES_DIR)}",
                                permissions={"read": ["recipient@example.com"], "write": [EMAIL], "admin": [EMAIL]}
                            )
                            
                            # Finalize
                            msg.finalize()
                            print(f"   ✅ Created message: {msg.message_id}", flush=True)
                    except Exception as e:
                        print(f"   ❌ Error: {e}", flush=True)
    
    # Create observer
    observer = Observer()
    observer.schedule(DataSitesHandler(), str(DATASITES_DIR), recursive=True)
    observer.start()
    
    return observer

# Cell 3: Create server with observer
ss.servers.terminate_all()

# Global observer reference
observer = None

def start():
    global observer
    if observer is None:
        observer = create_observer()
        return {"status": "Observer started", "watching": str(DATASITES_DIR)}
    return {"status": "Already running"}

def status():
    return {
        "running": observer is not None and observer.is_alive(),
        "datasites_dir": str(DATASITES_DIR),
        "outbox_dir": str(OUTBOX_DIR)
    }

def list_messages():
    messages = []
    for msg_dir in OUTBOX_DIR.iterdir():
        if msg_dir.is_dir() and msg_dir.name.startswith("gdrive_"):
            messages.append(msg_dir.name)
    return {"messages": messages, "count": len(messages)}

# Create server
server = ss.create(
    name="notebook_observer",
    dependencies=["watchdog"],
    endpoints={
        "/start": start,
        "/status": status,
        "/messages": list_messages
    }
)

print(f"\\n🌐 Server: {server.url}")

# Auto-start
response = requests.get(f"{server.url}/start")
print(f"✅ {response.json()['status']}")

# Cell 4: Test the observer
print("\\n📝 Test the observer by creating files:")
print(f"\\n# Create a test file")
print(f"test_file = DATASITES_DIR / 'test.txt'")
print(f"test_file.write_text('Hello SyftBox!')")
print(f"\\n# Check messages")
print(f"requests.get('{server.url}/messages').json()")
print(f"\\n# View logs")
print(f"ss.servers['notebook_observer'].stdout.lines()[-10:]")

# Cell 5: Helper functions
def create_test_file(name="test.csv", content="id,value\\n1,100\\n2,200"):
    """Create a test file in datasites"""
    file_path = DATASITES_DIR / name
    file_path.write_text(content)
    print(f"Created: {file_path}")
    return file_path

def view_logs(n=10):
    """View recent observer logs"""
    logs = ss.servers['notebook_observer'].stdout.lines()
    return logs[-n:] if logs else []

def list_outbox():
    """List messages in outbox with details"""
    for msg_dir in sorted(OUTBOX_DIR.iterdir()):
        if msg_dir.is_dir() and msg_dir.name.startswith("gdrive_"):
            print(f"\\n📩 {msg_dir.name}")
            
            # Check for files
            files_dir = msg_dir / "data" / "files"
            if files_dir.exists():
                files = list(files_dir.iterdir())
                print(f"   Files: {[f.name for f in files]}")
            
            # Check if locked/ready
            if (msg_dir / "lock.json").exists():
                print("   Status: ✅ Ready to send")
            else:
                print("   Status: ⏳ Not finalized")

print("\\n🛠️ Helper functions available:")
print("  create_test_file()  - Create a test file")
print("  view_logs()         - View observer logs")
print("  list_outbox()       - List messages in detail")