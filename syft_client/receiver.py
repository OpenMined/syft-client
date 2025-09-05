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
        interval_seconds: How often to check for changes with Sheets API
    
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
            print(f"   Polling interval: {interval_seconds}s", flush=True)
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
            "last_error": None,
            "sheets_api_calls": 0,
            "changes_detected": 0
        }
        
        # Track API states for change detection
        api_states = {}  # Will store {friend_email: {sheet_id, last_content_hash, last_row_count}}
        
        # Timing control
        last_call_time = 0
        
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
        
        # Helper function to compute hash of content
        def compute_content_hash(content):
            import hashlib
            if isinstance(content, str):
                content = content.encode('utf-8')
            elif isinstance(content, list):
                content = str(content).encode('utf-8')
            return hashlib.md5(content).hexdigest()
        
        # Main receiver loop
        while current_module.receiver_running:
            try:
                current_time = time.time()
                elapsed = current_time - last_call_time
                
                # Check if enough time has passed for next call
                if elapsed >= interval_seconds:
                    changes_detected = False
                    
                    # Get friends list
                    if not hasattr(client, 'friends') or not client.friends:
                        # No friends to check
                        last_call_time = current_time
                        time.sleep(interval_seconds)
                        continue
                    
                    # Use Sheets API to check for changes
                    try:
                        stats["sheets_api_calls"] += 1
                        
                        # Get sheets service
                        sheets_service = client._get_sheets_service()
                        
                        for friend_email in client.friends:
                            try:
                                # Find friend's sheet
                                sheet_name = f"syft_{friend_email}_to_{client.my_email}_messages"
                                sheet_id = client._find_message_sheet(sheet_name, from_email=friend_email)
                                
                                if not sheet_id:
                                    continue
                                
                                # Get current content
                                result = sheets_service.spreadsheets().values().get(
                                    spreadsheetId=sheet_id,
                                    range='messages!A:D'
                                ).execute()
                                
                                rows = result.get('values', [])
                                current_row_count = len(rows)
                                current_hash = compute_content_hash(rows)
                                
                                # Get previous state
                                friend_state = api_states.get(friend_email, {})
                                last_hash = friend_state.get("last_content_hash")
                                last_row_count = friend_state.get("last_row_count", 0)
                                
                                # Check for changes
                                if last_hash is None or current_hash != last_hash:
                                    changes_detected = True
                                    stats["changes_detected"] += 1
                                    print(f"📊 Change detected from {friend_email}: {last_row_count} → {current_row_count} rows", flush=True)
                                
                                # Update state
                                api_states[friend_email] = {
                                    "sheet_id": sheet_id,
                                    "last_content_hash": current_hash,
                                    "last_row_count": current_row_count
                                }
                                
                            except Exception as e:
                                # Log but don't fail the whole check
                                print(f"Error checking {friend_email}: {e}", flush=True)
                        
                        # Update timing
                        last_call_time = current_time
                        
                        # If changes detected, process them
                        if changes_detected:
                            # Update inbox from sheets
                            result = client.update_inbox_from_sheets()
                            if result:
                                stats["update_count"] += 1
                        
                    except Exception as e:
                        stats["error_count"] += 1
                        stats["last_error"] = f"api_check: {str(e)}"
                        print(f"Error during API check: {e}", flush=True)
                        # Update timing even on error to avoid tight loop
                        last_call_time = current_time
                    
                else:
                    # Not enough time elapsed, small sleep
                    time.sleep(0.01)  # 10ms
                
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