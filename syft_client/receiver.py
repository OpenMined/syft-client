"""
Auto-sync receiver functionality for automatic message processing
"""

import syft_serve as ss
import os
from pathlib import Path


def create_receiver_endpoint(email, interval_seconds=1.0):
    """
    Create the auto-sync receiver endpoint
    
    Args:
        email: Email address of the user
        interval_seconds: How often to run the sync operations (default: 1 second)
    
    Returns:
        Server object
    """
    # Create unique server name based on email
    server_name = f"receiver_{email.replace('@', '_').replace('.', '_')}"
    
    # Check if endpoint already exists by querying syft_serve state
    existing_servers = list(ss.servers)
    for server in existing_servers:
        if server.name == server_name:
            print("Receiver endpoint already exists")
            return server
    
    def receiver_loop():
        import syft_client as sc
        import time
        import os
        import atexit
        from datetime import datetime
        
        # Login to syft client with provided email (with verbose=False to silence messages)
        print(f"Starting receiver for {email}...", flush=True)
        
        # Check token exists
        # Convert email to token path format (@ -> _at_, . -> _)
        email_for_path = email.replace('@', '_at_').replace('.', '_')
        token_path = os.path.expanduser(f'~/.syft/gdrive/{email_for_path}/token.json')
        if not os.path.exists(token_path):
            return f"Error: Token file not found at {token_path}"
            
        try:
            client = sc.login(email, verbose=False, force_relogin=False)
            print(f"Login successful! Starting auto-sync receiver...", flush=True)
        except Exception as e:
            return f"Login failed: {type(e).__name__}: {str(e)}"
        
        # Track statistics
        stats = {
            "start_time": datetime.now(),
            "last_update": None,
            "update_count": 0,
            "approve_count": 0,
            "merge_count": 0,
            "error_count": 0,
            "last_error": None
        }
        
        # Store stats for access
        import sys
        current_module = sys.modules[__name__]
        current_module.receiver_stats = stats
        
        # Flag to control the loop
        current_module.receiver_running = True
        
        # Register cleanup function
        def cleanup_receiver():
            current_module = sys.modules[__name__]
            if hasattr(current_module, 'receiver_running'):
                print(f"Stopping receiver for {email}...", flush=True)
                current_module.receiver_running = False
                print(f"Receiver stopped.", flush=True)
        
        atexit.register(cleanup_receiver)
        
        # Main receiver loop
        while current_module.receiver_running:
            try:
                # Update inbox from sheets
                try:
                    result = client.update_inbox_from_sheets()
                    if result:
                        stats["update_count"] += 1
                except Exception as e:
                    stats["error_count"] += 1
                    stats["last_error"] = f"update_inbox: {str(e)}"
                
                # Auto-approve inbox items
                try:
                    # Check if the method exists
                    if hasattr(client, 'autoapprove_inbox'):
                        approved = client.autoapprove_inbox()
                        if approved:
                            stats["approve_count"] += len(approved) if isinstance(approved, list) else 1
                except Exception as e:
                    stats["error_count"] += 1
                    stats["last_error"] = f"autoapprove: {str(e)}"
                
                # Merge new syncs
                try:
                    # Check if the method exists
                    if hasattr(client, 'merge_new_syncs'):
                        merged = client.merge_new_syncs()
                        if merged:
                            stats["merge_count"] += len(merged) if isinstance(merged, list) else 1
                except Exception as e:
                    stats["error_count"] += 1
                    stats["last_error"] = f"merge_syncs: {str(e)}"
                
                # Update last run time
                stats["last_update"] = datetime.now()
                
                # Sleep for the specified interval
                time.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                print("Receiver interrupted by user", flush=True)
                break
            except Exception as e:
                stats["error_count"] += 1
                stats["last_error"] = f"main_loop: {str(e)}"
                # Sleep even on error to avoid tight loop
                time.sleep(interval_seconds)
        
        # Return final stats
        return {
            "status": "stopped",
            "message": f"Receiver stopped after {stats['update_count']} updates",
            "stats": stats
        }
    
    # Get the package parent directory path
    import syft_client
    syft_client_module_path = os.path.dirname(os.path.abspath(syft_client.__file__))
    syft_client_parent_path = os.path.dirname(syft_client_module_path)
    
    # Create the server with dependencies
    server = ss.create(server_name, 
                       dependencies=[
                           syft_client_parent_path,  # Use the parent directory containing syft_client
                           "google-api-python-client", 
                           "google-auth", 
                           "google-auth-oauthlib", 
                           "google-auth-httplib2"
                       ],
                       endpoints={"/": receiver_loop})
    
    print(f"Receiver server created at: {server.url}")
    
    # Trigger the receiver to start by accessing the endpoint
    import requests
    try:
        requests.get(server.url, timeout=1)
    except:
        # It's OK if this times out, the receiver loop has started
        pass
    
    return server


def destroy_receiver_endpoint(email):
    """Destroy the receiver endpoint for a specific email"""
    # Create server name to look for
    server_name = f"receiver_{email.replace('@', '_').replace('.', '_')}"
    
    # Find and terminate the specific server
    existing_servers = list(ss.servers)
    for server in existing_servers:
        if server.name == server_name:
            server.terminate()
            print(f"Receiver {server_name} terminated successfully")
            return True
    
    print(f"No receiver found for {email}")
    return False


def get_receiver_stats(email):
    """Get statistics from a running receiver"""
    server_name = f"receiver_{email.replace('@', '_').replace('.', '_')}"
    
    # Find the server
    existing_servers = list(ss.servers)
    for server in existing_servers:
        if server.name == server_name:
            # Try to access the stats endpoint
            import requests
            try:
                response = requests.get(f"{server.url}/stats")
                if response.status_code == 200:
                    return response.json()
            except:
                pass
    
    return None