"""
Sync history management for echo prevention
"""

import json
import os
import hashlib
import time
from pathlib import Path
from typing import Optional, Dict, List


class SyncHistory:
    """Manages sync history to prevent echo loops"""
    
    def __init__(self, syftbox_dir: Path):
        self.syftbox_dir = syftbox_dir
        self.history_dir = syftbox_dir / ".syft_sync" / "history"
        self.history_dir.mkdir(parents=True, exist_ok=True)
    
    def compute_file_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def is_recent_sync(self, file_path: str, direction: Optional[str] = None, threshold_seconds: int = 60) -> bool:
        """Check if a file was recently synced in a specific direction (to prevent echoes)
        
        Args:
            file_path: Path to the file to check
            direction: Optional direction to check ('incoming' or 'outgoing'). 
                      If None, checks any recent sync regardless of direction.
            threshold_seconds: Time window to consider as "recent"
            
        Returns:
            True if file was recently synced in the specified direction
        """
        try:
            print(f"   🔍 Checking sync history for: {file_path}, direction={direction}", flush=True)
            file_hash = self.compute_file_hash(file_path)
            metadata_path = self.history_dir / file_hash / "metadata.json"
            
            if not metadata_path.exists():
                print(f"      No metadata found for hash {file_hash}", flush=True)
                return False
            
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            
            print(f"      Found metadata with {len(metadata.get('sync_history', []))} sync records", flush=True)
            
            # If no direction specified, check last sync regardless of direction
            if direction is None:
                last_sync = metadata.get("last_sync", {})
                if not last_sync:
                    return False
                
                last_sync_time = last_sync.get("timestamp", 0)
                current_time = time.time()
                return (current_time - last_sync_time) < threshold_seconds
            
            # If direction specified, check sync history for recent syncs in that direction
            sync_history = metadata.get("sync_history", [])
            current_time = time.time()
            
            # Debug: print all directions found
            directions = [s.get("direction", "unknown") for s in sync_history]
            print(f"      Directions in history: {directions}", flush=True)
            
            # Check from most recent to oldest
            for sync in reversed(sync_history):
                if sync.get("direction") == direction:
                    sync_time = sync.get("timestamp", 0)
                    age = current_time - sync_time
                    print(f"      Found {direction} sync, age: {age:.1f}s (threshold: {threshold_seconds}s)", flush=True)
                    if age < threshold_seconds:
                        return True
                    else:
                        # If the most recent sync in this direction is old, no need to check further
                        return False
            
            print(f"      No {direction} sync found in history", flush=True)
            return False
            
        except Exception:
            return False
    
    def record_sync(self, file_path: str, message_id: str, peer_email: str, 
                    transport: str, direction: str, file_size: int, file_hash: Optional[str] = None):
        """Record a sync operation in history
        
        Args:
            file_path: Path to the file
            message_id: Message ID
            peer_email: Email of the peer
            transport: Transport used
            direction: 'incoming' or 'outgoing'
            file_size: Size of the file
            file_hash: Optional pre-computed hash (useful when recording before file exists)
        """
        # Always print for debugging
        import sys
        print(f"📝 Recording sync: {file_path} direction={direction} peer={peer_email}", file=sys.stderr, flush=True)
        
        # Use provided hash or compute it
        if file_hash is None:
            file_hash = self.compute_file_hash(file_path)
            
        hash_dir = self.history_dir / file_hash
        hash_dir.mkdir(exist_ok=True)
        
        metadata_path = hash_dir / "metadata.json"
        
        # Load existing metadata or create new
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
        else:
            metadata = {
                "file_path": file_path,
                "file_hash": file_hash,
                "sync_history": []
            }
        
        # Update with latest sync
        sync_record = {
            "message_id": message_id,
            "timestamp": time.time(),
            "peer": peer_email,
            "transport": transport,
            "direction": direction,
            "file_size": file_size
        }
        
        metadata["last_sync"] = sync_record
        metadata["sync_history"].append(sync_record)
        
        # Keep only last 100 sync records
        metadata["sync_history"] = metadata["sync_history"][-100:]
        
        # Save metadata
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        
        # Also save individual sync record
        sync_record_path = hash_dir / f"{message_id}.json"
        with open(sync_record_path, "w") as f:
            json.dump(sync_record, f, indent=2)
    
    def get_history(self, file_path: str, limit: int = 10) -> List[Dict]:
        """Get sync history for a file"""
        try:
            file_hash = self.compute_file_hash(file_path)
            metadata_path = self.history_dir / file_hash / "metadata.json"
            
            if not metadata_path.exists():
                return []
            
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            
            history = metadata.get("sync_history", [])
            return history[-limit:] if limit else history
            
        except Exception:
            return []