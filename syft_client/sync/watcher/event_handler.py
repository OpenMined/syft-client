"""
File system event handler for the watcher
"""

import hashlib
import os
import time
from pathlib import Path
from watchdog.events import FileSystemEventHandler


class SyftBoxEventHandler(FileSystemEventHandler):
    """Handles file system events for SyftBox synchronization"""
    
    def __init__(self, client, sync_history, verbose=True):
        self.client = client
        self.sync_history = sync_history
        self.verbose = verbose
    
    def on_created(self, event):
        if not event.is_directory:
            self._handle_file_event(event, "created")
    
    def on_modified(self, event):
        if not event.is_directory:
            self._handle_file_event(event, "modified")
    
    def on_deleted(self, event):
        # Handle both file and directory deletions
        self._handle_file_event(event, "deleted")
    
    def on_moved(self, event):
        """Handle move events using native move message type"""
        # Skip hidden files (starting with .)
        src_filename = os.path.basename(event.src_path)
        dest_filename = os.path.basename(event.dest_path)
        
        if src_filename.startswith('.') or dest_filename.startswith('.'):
            return
        
        # Skip any path containing hidden directories
        src_parts = event.src_path.split(os.sep)
        dest_parts = event.dest_path.split(os.sep)
        
        for part in src_parts + dest_parts:
            if part.startswith('.'):
                return
        
        # Skip temporary files and system files
        if (src_filename.endswith(('.tmp', '.swp', '.DS_Store', '~', '.lock')) or 
            dest_filename.endswith(('.tmp', '.swp', '.DS_Store', '~', '.lock'))):
            return
        
        # Skip if in .syft_sync directory
        if '.syft_sync' in event.src_path or '.syft_sync' in event.dest_path:
            return
        
        if self.verbose:
            type_str = "directory" if event.is_directory else "file"
            print(f"\n🚚 Move detected ({type_str}): {src_filename} → {dest_filename}", flush=True)
        
        try:
            # Check for move markers first (fastest check)
            source_marker = Path(event.src_path).parent / f".syft_moving_from_{src_filename}"
            dest_marker = Path(event.dest_path).parent / f".syft_moving_to_{dest_filename}"
            
            if self.verbose:
                print(f"\n🔍 Checking for move markers:", flush=True)
                print(f"   Source marker: {source_marker} - {'EXISTS' if source_marker.exists() else 'NOT FOUND'}", flush=True)
                print(f"   Dest marker: {dest_marker} - {'EXISTS' if dest_marker.exists() else 'NOT FOUND'}", flush=True)
            
            if source_marker.exists() or dest_marker.exists():
                if self.verbose:
                    print(f"✋ Skipping move: {src_filename} → {dest_filename} (has move markers)", flush=True)
                return
            
            # Check echo prevention - was this move recently synced from a peer?
            threshold = int(os.environ.get('SYFT_SYNC_ECHO_THRESHOLD', '60'))
            if threshold > 0:
                # Check if source was recently deleted by incoming sync
                try:
                    is_recent_deletion = self.sync_history.is_recent_sync(
                        event.src_path, 
                        direction='incoming', 
                        threshold_seconds=threshold,
                        operation='delete'
                    )
                    if is_recent_deletion:
                        if self.verbose:
                            print(f"✋ Skipping move echo: source was recently deleted by peer", flush=True)
                        return
                except:
                    pass
                
                # Check if destination was recently created by incoming sync
                if os.path.exists(event.dest_path):
                    try:
                        is_recent_creation = self.sync_history.is_recent_sync(
                            event.dest_path,
                            direction='incoming',
                            threshold_seconds=threshold
                        )
                        if is_recent_creation:
                            if self.verbose:
                                print(f"✋ Skipping move echo: destination was recently created by peer", flush=True)
                            return
                    except:
                        pass
            
            # Send move message to all peers
            results = self.client.send_move_to_peers(event.src_path, event.dest_path)
            
            # Record in sync history for echo prevention
            message_id = f"msg_{int(time.time() * 1000)}"
            for peer_email, success in results.items():
                if success:
                    # Record deletion at source
                    source_hash = hashlib.sha256(event.src_path.encode('utf-8')).hexdigest()
                    self.sync_history.record_sync(
                        event.src_path,
                        message_id + "_move_del",
                        peer_email,
                        "auto",
                        "outgoing",
                        0,
                        file_hash=source_hash,
                        operation='delete'
                    )
                    
                    # Record creation at destination (if file exists)
                    if os.path.exists(event.dest_path) and not event.is_directory:
                        try:
                            file_size = os.path.getsize(event.dest_path)
                            self.sync_history.record_sync(
                                event.dest_path,
                                message_id + "_move_create",
                                peer_email,
                                "auto",
                                "outgoing",
                                file_size
                            )
                        except:
                            pass
            
            # Report results
            successful = sum(1 for success in results.values() if success)
            total = len(results)
            if successful > 0:
                if self.verbose:
                    print(f"✓ Move message sent to {successful}/{total} peers", flush=True)
            else:
                if self.verbose:
                    print(f"Failed to send move to any peers", flush=True)
                    
        except Exception as e:
            if self.verbose:
                print(f"❌ Error handling move: {e}", flush=True)
    
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
            
            # Debug logging
            if self.verbose:
                print(f"\n🔍 Checking sync history for: {event.src_path}", flush=True)
                print(f"   Threshold: {threshold} seconds", flush=True)
            
            if threshold > 0:
                is_recent = self.sync_history.is_recent_sync(event.src_path, direction='incoming', threshold_seconds=threshold)
                if self.verbose:
                    print(f"   Is recent incoming sync: {is_recent}", flush=True)
                
                if is_recent:
                    if self.verbose:
                        print(f"✋ Skipping echo: {filename} (was recently received)", flush=True)
                    return
        
        # Send the file or deletion to all peers
        try:
            if event_type == "deleted":
                if self.verbose:
                    print(f"Sending deletion: {filename}", flush=True)
                
                # Check for deletion marker first (fastest check)
                marker_path = Path(event.src_path).parent / f".syft_deleting_{filename}"
                if marker_path.exists():
                    if self.verbose:
                        print(f"✋ Skipping deletion: {filename} (has deletion marker)", flush=True)
                    return
                
                # Check if this deletion was recently synced from a peer (don't echo back)
                threshold = int(os.environ.get('SYFT_SYNC_ECHO_THRESHOLD', '60'))
                if threshold > 0:
                    # Check if file exists in sync history (it won't exist if deleted, but sync history might have it)
                    # We need to check if this was a recent incoming deletion
                    is_recent_deletion = False
                    try:
                        # Try to check with the file that might not exist
                        # This will use the path-only lookup in sync history
                        is_recent_deletion = self.sync_history.is_recent_sync(
                            event.src_path, 
                            direction='incoming', 
                            threshold_seconds=threshold,
                            operation='delete'
                        )
                    except:
                        pass
                    
                    if is_recent_deletion:
                        if self.verbose:
                            print(f"✋ Skipping deletion echo: {filename} (was recently deleted by peer)", flush=True)
                        return
                
                
                # Send deletion to all peers
                results = self.client.send_deletion_to_peers(event.src_path)
                
                # Record the deletion in sync history for echo prevention
                message_id = f"msg_{int(time.time() * 1000)}"
                for peer_email, success in results.items():
                    if success:
                        # For deletions, we need to generate a hash based on the path alone
                        # since the file doesn't exist anymore
                        path_hash = hashlib.sha256(event.src_path.encode('utf-8')).hexdigest()
                        
                        self.sync_history.record_sync(
                            event.src_path,
                            message_id,
                            peer_email,
                            "auto",  # Transport will be selected automatically
                            "outgoing",
                            0,  # Size is 0 for deletions
                            file_hash=path_hash,  # Provide hash so it doesn't try to read the file
                            operation='delete'  # Mark as deletion
                        )
                
                # Report results
                successful = sum(1 for success in results.values() if success)
                total = len(results)
                if successful > 0:
                    if self.verbose:
                        print(f"✓ Sent deletion to {successful}/{total} peers", flush=True)
                else:
                    if self.verbose:
                        print(f"Failed to send deletion to any peers", flush=True)
            else:
                # Use the helper method to send file to peers
                self._send_file_to_peers(event.src_path, event_type)
                
        except Exception as e:
            if self.verbose:
                print(f"Error processing {filename}: {e}", flush=True)
    
    def _send_file_to_peers(self, file_path, event_type):
        """Helper method to send a file to all peers (extracted from _handle_file_event)"""
        filename = os.path.basename(file_path)
        
        if self.verbose:
            print(f"Sending {event_type}: {filename}", flush=True)
        
        # Get all peers
        try:
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
                success = self.client.send_to(file_path, peer_email)
                results[peer_email] = success
                
                if success:
                    # Record the sync in history
                    file_size = os.path.getsize(file_path)
                    message_id = f"msg_{int(time.time() * 1000)}"
                    self.sync_history.record_sync(
                        file_path,
                        message_id,
                        peer_email,
                        "auto",  # Transport will be selected automatically
                        "outgoing",
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
        
        return results