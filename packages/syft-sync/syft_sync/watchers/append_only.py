"""
Append-Only Log Watcher
Creates a versioned history of all file changes by storing copies in a log
"""

import shutil
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
import logging

from ..core.base import BaseWatcher
from ..core.events import FileEvent, EventType, EventHandler
from ..core.observer import WatcherObserver
from ..storage.log_storage import LogStorage


logger = logging.getLogger(__name__)


class AppendOnlyEventHandler(EventHandler):
    """Event handler for append-only logging"""
    
    def __init__(self, log_storage: LogStorage):
        self.log_storage = log_storage
    
    def on_file_created(self, event: FileEvent):
        """Log file creation"""
        self.log_storage.log_event(event)
    
    def on_file_modified(self, event: FileEvent):
        """Log file modification"""
        self.log_storage.log_event(event)
    
    def on_file_deleted(self, event: FileEvent):
        """Log file deletion (preserve last version)"""
        self.log_storage.log_event(event)
    
    def on_file_moved(self, event: FileEvent):
        """Log file move"""
        self.log_storage.log_event(event)


class AppendOnlyLogWatcher(BaseWatcher):
    """
    Watches a directory and maintains an append-only log of all file changes.
    Each change creates a new version stored with metadata.
    """
    
    def __init__(
        self,
        watch_path: str,
        log_path: Optional[str] = None,
        exclude_patterns: Optional[List[str]] = None,
        verbose: bool = False
    ):
        """
        Initialize the append-only log watcher
        
        Args:
            watch_path: Directory to watch
            log_path: Directory to store the log (default: next to watch_path)
            exclude_patterns: Patterns to exclude from watching
            verbose: Print detailed output
        """
        super().__init__(Path(watch_path), exclude_patterns, verbose=verbose)
        
        # Set up log storage
        if log_path:
            self.log_path = Path(log_path)
        else:
            # Put log directory next to the watched directory
            parent = self.watch_path.parent
            watch_name = self.watch_path.name
            self.log_path = parent / f"{watch_name}_log"
        
        # Initialize storage
        self.log_storage = LogStorage(self.log_path, verbose=verbose)
        
        # Set up event handler
        self.event_handler = AppendOnlyEventHandler(self.log_storage)
        
        # Set up observer
        self.observer = WatcherObserver(self)
        
        # Track file hashes to detect duplicates
        self._file_hashes: Dict[Path, str] = {}
        
        if verbose:
            logger.info(f"📝 Append-Only Log Watcher initialized")
            logger.info(f"   Watch path: {self.watch_path}")
            logger.info(f"   Log path: {self.log_path}")
    
    def start(self):
        """Start watching for changes"""
        # Initial scan of directory
        self._initial_scan()
        
        # Start observer
        self.observer.start()
        
        if self.verbose:
            logger.info("👀 Watcher started")
    
    def stop(self):
        """Stop watching"""
        self.observer.stop()
        
        if self.verbose:
            stats = self.get_stats()
            logger.info("🛑 Watcher stopped")
            logger.info(f"   Files tracked: {stats['tracked_files']}")
            logger.info(f"   Versions created: {self.log_storage.get_version_count()}")
    
    def process_event(self, event: FileEvent):
        """Process a file system event"""
        if event.is_directory:
            # We only log files, not directories
            return
        
        # Check for duplicates
        if event.event_type in [EventType.FILE_CREATED, EventType.FILE_MODIFIED]:
            if self._is_duplicate(event.src_path):
                if self.verbose:
                    logger.debug(f"Skipping duplicate: {event.src_path}")
                return
        
        # Track the file
        self._tracked_files.add(event.src_path)
    
    def _initial_scan(self):
        """Perform initial scan of watch directory"""
        if self.verbose:
            logger.info("📂 Performing initial directory scan...")
        
        file_count = 0
        for path in self.watch_path.rglob('*'):
            if path.is_file() and self.should_process(path):
                # Create initial event
                event = FileEvent(
                    event_type=EventType.FILE_CREATED,
                    src_path=path,
                    size=path.stat().st_size
                )
                
                # Process through storage
                if not self._is_duplicate(path):
                    self.log_storage.log_event(event)
                    self._tracked_files.add(path)
                    file_count += 1
        
        if self.verbose:
            logger.info(f"   Found {file_count} files to track")
    
    def _is_duplicate(self, file_path: Path) -> bool:
        """Check if file content is duplicate"""
        if not file_path.exists():
            return False
        
        try:
            # Calculate file hash
            current_hash = self._calculate_file_hash(file_path)
            
            # Check if we've seen this content before
            if file_path in self._file_hashes:
                if self._file_hashes[file_path] == current_hash:
                    return True
            
            # Update hash
            self._file_hashes[file_path] = current_hash
            return False
            
        except Exception as e:
            logger.error(f"Error checking duplicate for {file_path}: {e}")
            return False
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file"""
        sha256 = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                # Read in chunks for large files
                for chunk in iter(lambda: f.read(4096), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            # For files we can't read, use size and mtime as hash
            stat = file_path.stat()
            return f"size:{stat.st_size}_mtime:{stat.st_mtime}"
    
    def get_file_history(self, file_path: str) -> List[Dict[str, Any]]:
        """Get version history for a specific file"""
        return self.log_storage.get_file_history(file_path)
    
    def restore_version(self, file_path: str, version_id: str, restore_path: Optional[str] = None):
        """Restore a specific version of a file"""
        return self.log_storage.restore_version(file_path, version_id, restore_path)
    
    def explore_log(self):
        """Launch interactive log explorer"""
        from ..utils.explorer import LogExplorer
        explorer = LogExplorer(self.log_storage)
        explorer.run()