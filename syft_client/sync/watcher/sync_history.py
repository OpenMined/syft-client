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
    
    def is_recent_sync(self, file_path: str, threshold_seconds: int = 60) -> bool:
        """Check if a file was recently synced (to prevent echoes)"""
        try:
            file_hash = self.compute_file_hash(file_path)
            metadata_path = self.history_dir / file_hash / "metadata.json"
            
            if not metadata_path.exists():
                return False
            
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            
            last_sync = metadata.get("last_sync", {})
            if not last_sync:
                return False
            
            # Check if the sync was recent
            last_sync_time = last_sync.get("timestamp", 0)
            current_time = time.time()
            
            return (current_time - last_sync_time) < threshold_seconds
            
        except Exception:
            return False
    
    def record_sync(self, file_path: str, message_id: str, peer_email: str, 
                    transport: str, direction: str, file_size: int):
        """Record a sync operation in history"""
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