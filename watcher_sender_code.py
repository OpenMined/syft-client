import syft_serve as ss
import requests

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
        import sys
        import os
        
        # Add the syft-client directory to Python path to use the live code
        syft_client_path = "/Users/atrask/Desktop/Laboratory/syft-client"
        if syft_client_path not in sys.path:
            sys.path.insert(0, syft_client_path)
        
        # Force reload to get latest code
        import importlib
        if 'syft_client' in sys.modules:
            del sys.modules['syft_client']
        if 'syft_client.gdrive_unified' in sys.modules:
            del sys.modules['syft_client.gdrive_unified']
        
        import syft_client as sc
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        import time
        from pathlib import Path
        
        # Login to syft client with provided email
        client = sc.login(email, verbose=False)
        
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
                
                print(f"📁 File {event_type}: {event.src_path}", flush=True)
                
                # Send the file to all friends
                try:
                    print(f"📤 Sending to friends...", flush=True)
                    
                    # Debug: Check if method exists
                    if hasattr(client, 'send_file_or_folder_to_friends'):
                        results = client.send_file_or_folder_to_friends(event.src_path)
                    else:
                        # Fallback: send to each friend individually
                        print("⚠️  Using fallback: send_file_or_folder_to_friends not found", flush=True)
                        results = {}
                        for friend in client.friends:
                            print(f"   → Sending to {friend}...", flush=True)
                            success = client.send_file_or_folder_auto(event.src_path, friend)
                            results[friend] = success
                    
                    # Report results
                    successful = sum(1 for success in results.values() if success)
                    total = len(results)
                    print(f"✅ Sent to {successful}/{total} friends", flush=True)
                    
                except Exception as e:
                    print(f"❌ Error sending file: {str(e)}", flush=True)
        
        # Create observer and start watching
        observer = Observer()
        observer.schedule(Handler(), watch_path, recursive=True)
        observer.start()
        
        print(f"👀 Watching for changes in: {watch_path}", flush=True)
        
        # Keep the observer running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
        
        return "Watcher stopped"
    
    # Create the server with dependencies
    server = ss.create(server_name, 
                       dependencies=["watchdog", "google-api-python-client", "google-auth", "google-auth-oauthlib", "google-auth-httplib2"],
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

# # Usage examples:
# if __name__ == "__main__":
#     # Create endpoint for Andrew
#     server = create_watcher_sender_endpoint("andrew@openmined.org")
#     
#     # Test the endpoint
#     # response = requests.get(server.url)
#     # print(response.text)
#     
#     # Destroy the endpoint when done
#     # destroy_watcher_sender_endpoint("andrew@openmined.org")