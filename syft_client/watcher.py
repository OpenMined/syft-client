"""
File watcher functionality for automatic synchronization
"""

import syft_serve as ss
import os
from pathlib import Path


def create_watcher_sender_endpoint(email):
    """Create the file watcher sender endpoint with syft client integration"""
    # Create unique server name based on email
    server_name = f"watcher_sender_{email.replace('@', '_').replace('.', '_')}"
    
    # Check if endpoint already exists by querying syft_serve state
    existing_servers = list(ss.servers)
    for server in existing_servers:
        if server.name == server_name:
            print("Endpoint already exists")
            return server
    
    def hello():
        import syft_client as sc
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        import time
        import os
        import atexit
        from pathlib import Path
        
        # Login to syft client with provided email (with verbose=False to silence messages)
        print(f"Attempting login for {email}...", flush=True)
        
        # Check token exists
        # Convert email to token path format (@ -> _at_, . -> _)
        email_for_path = email.replace('@', '_at_').replace('.', '_')
        token_path = os.path.expanduser(f'~/.syft/gdrive/{email_for_path}/token.json')
        if not os.path.exists(token_path):
            return f"Error: Token file not found at {token_path}"
            
        try:
            client = sc.login(email, verbose=False, force_relogin=False)
            print(f"Login successful!", flush=True)
        except Exception as e:
            return f"Login failed: {type(e).__name__}: {str(e)}"
        
        # Get the SyftBox datasites directory to watch
        syftbox_dir = client.get_syftbox_directory()
        if syftbox_dir is None:
            return "Error: Could not determine SyftBox directory"
        
        watch_path = str(syftbox_dir / "datasites")
        
        # Define what happens when files change
        class Handler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory:
                    self._handle_file_event(event, "created")
            
            def on_modified(self, event):
                if not event.is_directory:
                    self._handle_file_event(event, "modified")
            
            def _handle_file_event(self, event, event_type):
                # Skip hidden files (starting with .)
                filename = os.path.basename(event.src_path)
                if filename.startswith('.'):
                    return
                
                # Skip temporary files and system files
                if filename.endswith(('.tmp', '.swp', '.DS_Store', '~')):
                    return
                
                # Silent mode - no print
                
                # Send the file to all friends
                try:
                    # Silent mode - no print
                    print("sending:" + str(event), flush=True)
                    # Send using the batch method if available, otherwise fallback
                    if hasattr(client, 'send_file_or_folder_to_friends'):
                        results = client.send_file_or_folder_to_friends(event.src_path)
                    else:
                        # Fallback: send to each friend individually
                        # Silent mode - no print
                        results = {}
                        for friend in client.friends:
                            # Silent mode - no print
                            success = client.send_file_or_folder_auto(event.src_path, friend)
                            results[friend] = success
                    
                    # Report results
                    successful = sum(1 for success in results.values() if success)
                    total = len(results)
                    # Silent mode - no print
                    
                except Exception as e:
                    # Silent mode - no print
                    pass
        
        # Create observer and start watching
        observer = Observer()
        observer.schedule(Handler(), watch_path, recursive=True)
        observer.start()
        
        # Store observer reference for cleanup
        # We'll store it as a module-level variable to ensure it persists
        import sys
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
        
        return {
            "status": "started",
            "message": f"Watcher is now monitoring: {watch_path}",
            "email": email
        }
    
    # Get the package installation path
    import syft_client
    syft_client_path = os.path.dirname(os.path.abspath(syft_client.__file__))
    
    # Create the server with dependencies
    server = ss.create(server_name, 
                       dependencies=[
                           syft_client_path,  # Use the installed package path
                           "watchdog", 
                           "google-api-python-client", 
                           "google-auth", 
                           "google-auth-oauthlib", 
                           "google-auth-httplib2"
                       ],
                       endpoints={"/": hello})
    
    print(f"Server created at: {server.url}")
    return server


def destroy_watcher_sender_endpoint(email):
    """Destroy the watcher sender endpoint for a specific email"""
    # Create server name to look for
    server_name = f"watcher_sender_{email.replace('@', '_').replace('.', '_')}"
    
    # Find and terminate the specific server
    existing_servers = list(ss.servers)
    for server in existing_servers:
        if server.name == server_name:
            server.terminate()
            print(f"Server {server_name} terminated successfully")
            return True
    
    print(f"No server found for {email}")
    return False