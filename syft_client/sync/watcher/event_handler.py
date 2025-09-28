"""
File system event handler for the watcher
"""

import os
from pathlib import Path
from watchdog.events import FileSystemEventHandler


class SyftBoxEventHandler(FileSystemEventHandler):
    """Handles file system events for SyftBox synchronization"""
    
    def __init__(self, client, sync_history, verbose=True):
        self.client = client
        self.sync_history = sync_history
        self.verbose = verbose
        self.processed_events = set()  # Track processed events to avoid duplicates
    
    def on_created(self, event):
        if not event.is_directory:
            self._handle_file_event(event, "created")
    
    def on_modified(self, event):
        if not event.is_directory:
            self._handle_file_event(event, "modified")
    
    def on_deleted(self, event):
        if not event.is_directory:
            self._handle_file_event(event, "deleted")
    
    def _handle_file_event(self, event, event_type):
        """Process a file system event"""
        # Skip hidden files (starting with .)
        filename = os.path.basename(event.src_path)
        if filename.startswith('.'):
            return
        
        # Skip any path containing hidden directories
        path_parts = event.src_path.split(os.sep)
        for part in path_parts:
            if part.startswith('.'):
                return
        
        # Skip temporary files and system files
        if filename.endswith(('.tmp', '.swp', '.DS_Store', '~', '.lock')):
            return
        
        # Skip if in .syft_sync directory
        if '.syft_sync' in event.src_path:
            return
        
        # For deletions, we can't check file content (it's gone)
        if event_type != "deleted":
            # Check if this file change is from a recent sync to prevent echo
            threshold = int(os.environ.get('SYFT_SYNC_ECHO_THRESHOLD', '60'))
            
            if threshold > 0 and self.sync_history.is_recent_sync(event.src_path, threshold_seconds=threshold):
                if self.verbose:
                    print(f"Skipping echo: {filename} (matches recent sync)", flush=True)
                return
        
        # Send the file or deletion to all peers
        try:
            if event_type == "deleted":
                if self.verbose:
                    print(f"Sending deletion: {filename}", flush=True)
                # TODO: Implement deletion sending when available
                print(f"Warning: Deletion sending not yet implemented", flush=True)
            else:
                if self.verbose:
                    print(f"Sending {event_type}: {filename}", flush=True)
                
                # Get all peers
                try:
                    # Get peers list
                    peers = list(self.client.peers)
                        
                    if not peers:
                        print("No peers configured", flush=True)
                        return
                except Exception as e:
                    print(f"Warning: Could not get peers: {e}", flush=True)
                    print("Watcher running in demo mode - file changes detected but not sent", flush=True)
                    return
                
                # Send to each peer
                results = {}
                for peer in peers:
                    try:
                        # Get peer email
                        if isinstance(peer, str):
                            peer_email = peer
                        elif hasattr(peer, 'email'):
                            peer_email = peer.email
                        elif hasattr(peer, 'peer_email'):
                            peer_email = peer.peer_email
                        else:
                            print(f"Warning: Cannot determine email for peer: {peer}", flush=True)
                            continue
                            
                        # Use send_to method
                        success = self.client.send_to(event.src_path, peer_email)
                        results[peer_email] = success
                        
                        if success:
                            # Record the sync in history
                            file_size = os.path.getsize(event.src_path)
                            message_id = f"msg_{int(time.time() * 1000)}"
                            self.sync_history.record_sync(
                                event.src_path,
                                message_id,
                                peer_email,
                                "auto",  # Transport will be selected automatically
                                "sent",
                                file_size
                            )
                    except Exception as e:
                        if self.verbose:
                            print(f"Error sending to {peer_email if 'peer_email' in locals() else peer}: {e}", flush=True)
                        if 'peer_email' in locals():
                            results[peer_email] = False
                
                # Report results
                successful = sum(1 for success in results.values() if success)
                total = len(results)
                if successful > 0:
                    if self.verbose:
                        print(f"✓ Sent to {successful}/{total} peers", flush=True)
                else:
                    if self.verbose:
                        print(f"Failed to send to any peers", flush=True)
                
        except Exception as e:
            if self.verbose:
                print(f"Error processing {filename}: {e}", flush=True)


import time  # Add this import at the top of the file