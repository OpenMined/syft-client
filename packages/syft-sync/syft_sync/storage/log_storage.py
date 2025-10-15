"""
Log storage implementation for append-only logging
"""
import os
import shutil
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
import logging

from ..core.events import FileEvent, EventType


logger = logging.getLogger(__name__)


class LogStorage:
    """Handles storage and retrieval of file versions in append-only log"""
    
    def __init__(self, log_path: Path, verbose: bool = False):
        """Initialize log storage"""
        self.log_path = Path(log_path)
        self.verbose = verbose
        
        # Create log directory
        self.log_path.mkdir(parents=True, exist_ok=True)
        
        # Track version count
        self._version_count = 0
        
        # Index for fast lookups
        self._index: Dict[str, List[Dict[str, Any]]] = {}
        
        # Load existing log entries
        self._load_existing_log()
    
    def log_event(self, event: FileEvent) -> Optional[str]:
        """Log a file event to storage"""
        if event.is_directory:
            return None
        
        # Generate version ID
        timestamp = event.timestamp.strftime("%Y%m%d_%H%M%S_%f")[:-3]
        file_name = event.src_path.name
        unique_id = hashlib.md5(f"{timestamp}_{file_name}".encode()).hexdigest()[:8]
        version_id = f"{timestamp}_{file_name.replace('.', '_')}_{unique_id}"
        
        # For base LogStorage, we just create metadata without storing files
        # The SyftLogStorage subclass will handle actual file storage
        file_hash = None
        if event.event_type != EventType.FILE_DELETED and event.src_path.exists():
            file_hash = self._calculate_file_hash(event.src_path)
        
        # Create metadata
        metadata = {
            "version_id": version_id,
            "timestamp": event.timestamp.isoformat(),
            "event_type": event.event_type.value,
            "file_path": str(event.src_path),
            "file_name": event.src_path.name,
            "size": event.size,
            "hash": file_hash,
        }
        
        if event.dest_path:
            metadata["dest_path"] = str(event.dest_path)
        
        # In base class, we don't store anything - just track metadata
        # Subclasses can override to add storage
        
        # Update index
        self._update_index(str(event.src_path), metadata)
        
        self._version_count += 1
        
        if self.verbose:
            logger.info(f"📸 Logged version: {version_id}")
        
        return version_id
    
    def get_file_history(self, file_path: str) -> List[Dict[str, Any]]:
        """Get all versions of a file"""
        return self._index.get(file_path, [])
    
    def restore_version(self, file_path: str, version_id: str, restore_path: Optional[str] = None) -> bool:
        """Restore a specific version of a file"""
        # Base class doesn't support restoration
        # Subclasses should override this method
        logger.error(f"Base LogStorage doesn't support file restoration")
        return False
    
    def get_version_count(self) -> int:
        """Get total number of versions stored"""
        return self._version_count
    
    def get_total_size(self) -> int:
        """Get total size of log storage"""
        total_size = 0
        for item in self.log_path.rglob('*'):
            if item.is_file():
                total_size += item.stat().st_size
        return total_size
    
    def _load_existing_log(self):
        """Load existing log entries into index"""
        # Base class doesn't have any persistent storage
        # Subclasses should override this method
        pass
    
    def _update_index(self, file_path: str, metadata: Dict[str, Any]):
        """Update the index with new version info"""
        if file_path not in self._index:
            self._index[file_path] = []
        
        self._index[file_path].append(metadata)
        
        # Sort by timestamp
        self._index[file_path].sort(key=lambda x: x['timestamp'])
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file"""
        sha256 = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate hash for {file_path}: {e}")
            return ""