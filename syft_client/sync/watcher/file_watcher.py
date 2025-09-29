"""
File watcher server endpoint implementation using syft-serve
"""
import time
import os
from pathlib import Path


def create_watcher_endpoint(email: str, verbose: bool = True):
    """Create the file watcher server endpoint with syft client integration"""
    try:
        import syft_serve as ss
    except ImportError:
        raise ImportError("syft-serve is required for file watching. Install with: pip install syft-serve")
    
    import requests
    
    # Create unique server name based on email
    server_name = f"watcher_sender_{email.replace('@', '_').replace('.', '_')}"
    
    # Check if endpoint already exists
    existing_servers = list(ss.servers)
    for server in existing_servers:
        if server.name == server_name:
            if verbose:
                print(f"Watcher endpoint already exists for {email}")
            return server
    
    def watcher_main():
        """Main watcher function that runs in the server"""
        import os
        import sys
        import time
        import atexit
        from pathlib import Path
        
        # Add the local syft_client to Python path dynamically
        # Look for syft_client in common locations
        possible_paths = [
            os.environ.get('SYFT_CLIENT_PATH'),
            os.path.expanduser('~/Desktop/Laboratory/syft-client'),
            os.path.expanduser('~/syft-client'),
            os.path.expanduser('~/projects/syft-client'),
            '/opt/syft-client',
        ]
        
        # Also check parent directories of current file
        current_file = os.path.abspath(__file__)
        for i in range(5):  # Go up to 5 levels
            current_file = os.path.dirname(current_file)
            if os.path.exists(os.path.join(current_file, 'syft_client', '__init__.py')):
                possible_paths.insert(0, current_file)
                break
        
        # Find and add the first valid path
        for path in possible_paths:
            if path and os.path.exists(path) and os.path.exists(os.path.join(path, 'syft_client', '__init__.py')):
                if path not in sys.path:
                    sys.path.insert(0, path)
                break
        else:
            # If no path found, try importing anyway (might be installed via pip)
            pass
        
        import syft_client as sc
        from watchdog.observers import Observer
        
        # Import our local modules
        from syft_client.sync.watcher.event_handler import SyftBoxEventHandler
        from syft_client.sync.watcher.sync_history import SyncHistory
        
        # Login to syft client with provided email
        print(f"Starting watcher for {email}...", flush=True)
        
        # Try to login - if no credentials exist, create a minimal client
        client = sc.login(email, verbose=False, force_relogin=False, skip_server_setup=True)
        print(f"Login successful!", flush=True)
    
        
        # Get the SyftBox directory to watch
        # Always use client's syftbox directory to ensure consistency
        syftbox_dir = client.get_syftbox_directory()
        
        # Watch the entire datasites folder instead of just the user's own folder
        watch_path = syftbox_dir / "datasites"
        watch_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize sync history
        sync_history = SyncHistory(syftbox_dir)
        
        # Create event handler
        handler = SyftBoxEventHandler(client, sync_history, verbose=verbose)
        
        # Create observer and start watching
        observer = Observer()
        observer.schedule(handler, str(watch_path), recursive=True)
        observer.start()
        
        # Store observer reference for cleanup
        current_module = sys.modules[__name__]
        current_module.observer = observer
        
        # Register cleanup function
        def cleanup_observer():
            current_module = sys.modules[__name__]
            if hasattr(current_module, 'observer') and current_module.observer:
                print(f"Stopping file watcher for {email}...", flush=True)
                current_module.observer.stop()
                current_module.observer.join()
                print(f"File watcher stopped.", flush=True)
        
        atexit.register(cleanup_observer)
        
        # Also start inbox polling for bidirectional sync
        def poll_inbox():
            while True:
                try:
                    # Check inbox for all peers
                    peers = []
                    try:
                        if hasattr(client, 'peers'):
                            # The client.peers is a property that returns a list-like object
                            peers = list(client.peers)  # Convert to list
                    except:
                        pass
                    
                    if peers:
                        for peer in peers:
                            try:
                                if hasattr(peer, 'check_inbox'):
                                    messages = peer.check_inbox(download_dir=str(watch_path), verbose=False)
                                    if messages:
                                        # Record syncs in history
                                        for transport, msgs in messages.items():
                                            for msg in msgs:
                                                if 'file_path' in msg:
                                                    sync_history.record_sync(
                                                        msg['file_path'],
                                                        msg.get('message_id', 'unknown'),
                                                        peer.email,
                                                        transport,
                                                        'received',
                                                        msg.get('size', 0)
                                                    )
                            except Exception as e:
                                if verbose:
                                    print(f"Error checking inbox for peer: {e}", flush=True)
                
                except Exception as e:
                    if verbose:
                        print(f"Error in inbox polling: {e}", flush=True)
                
                # Wait before next poll
                poll_interval = int(os.environ.get('SYFT_INBOX_POLL_INTERVAL', '30'))
                time.sleep(poll_interval)
        
        # Start inbox polling in a separate thread
        import threading
        inbox_thread = threading.Thread(target=poll_inbox, daemon=True)
        inbox_thread.start()
        
        return {
            "status": "started",
            "message": f"Watcher is now monitoring: {watch_path}",
            "email": email,
            "watch_path": str(watch_path),
            "server_name": server_name
        }
    
    # Get the current syft_client path and set it as environment variable
    import syft_client
    syft_client_path = os.path.dirname(os.path.dirname(os.path.abspath(syft_client.__file__)))
    os.environ['SYFT_CLIENT_PATH'] = syft_client_path
    
    # Create the server without local path in dependencies
    # The watcher_main function will add it to sys.path
    server = ss.create(
        server_name,
        dependencies=[
            "watchdog",
            "google-api-python-client",
            "google-auth",
            "google-auth-oauthlib",
            "google-auth-httplib2",
            "rich",
            "dnspython",
            "cryptography",
            "syft-serve"
        ],
        endpoints={"/": watcher_main}
    )
    
    # Trigger the watcher to start
    response = requests.get(server.url)
    if response.status_code == 200:
        # if verbose:
        #     print(f"✓ Watcher started successfully at {server.url}")
        """continue"""
    else:
        print(f"Error starting watcher: {response}")
    
    return server


def destroy_watcher_endpoint(email: str, verbose: bool = True):
    """Destroy the watcher server endpoint for a specific email"""
    try:
        import syft_serve as ss
    except ImportError:
        raise ImportError("syft-serve is required. Install with: pip install syft-serve")
    
    # Create server name to look for
    server_name = f"watcher_sender_{email.replace('@', '_').replace('.', '_')}"
    
    # Find and terminate the specific server
    existing_servers = list(ss.servers)
    for server in existing_servers:
        if server.name == server_name:
            server.terminate()
            if verbose:
                print(f"✓ Watcher for {email} stopped successfully")
            return True
    
    if verbose:
        print(f"No watcher found for {email}")
    return False