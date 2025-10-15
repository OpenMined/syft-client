"""
Log Receiver - Watches a syft log and recreates files locally
"""
import os
import shutil
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Set, Any, Union
import logging

from ..core.base import BaseWatcher
from ..core.events import FileEvent, EventType, EventHandler
from ..core.observer import WatcherObserver


logger = logging.getLogger(__name__)


class LogReceiver(BaseWatcher):
    """
    Watches a syft log directory and recreates/syncs files to a local directory
    """
    
    def __init__(
        self,
        log_path: Union[str, List[str]],
        output_path: str,
        exclude_patterns: Optional[List[str]] = None,
        verbose: bool = False,
        sync_mode: str = "latest",  # "latest" or "all_versions"
        lock_file_suffix: str = ".sync_lock",
        lock_file_delay: float = 1.0
    ):
        """
        Initialize the log receiver
        
        Args:
            log_path: Path or list of paths to syft log directories to watch
            output_path: Directory where files will be recreated
            exclude_patterns: Patterns to exclude from syncing
            verbose: Print detailed output
            sync_mode: "latest" (only sync latest version) or "all_versions"
            lock_file_suffix: Suffix for lock files (default: .sync_lock)
            lock_file_delay: Delay before removing lock file (seconds)
        """
        # Handle multiple log paths
        if isinstance(log_path, str):
            log_paths = [log_path]
        elif isinstance(log_path, list):
            log_paths = log_path
        else:
            raise ValueError("log_path must be a string or list of strings")
        
        # Convert to Path objects
        self.log_paths = [Path(p) for p in log_paths]
        
        # For backward compatibility, use first path as primary
        self.log_path = self.log_paths[0]
        
        # Use first log path as watch path for base class
        super().__init__(self.log_path, exclude_patterns, verbose=verbose)
        
        self.output_path = Path(output_path)
        self.sync_mode = sync_mode
        self.lock_file_suffix = lock_file_suffix
        self.lock_file_delay = lock_file_delay
        
        # Create output directory
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        # Track processed versions to avoid duplicates
        self._processed_versions: Set[str] = set()
        
        # Track file versions
        self._file_versions: Dict[str, List[Dict[str, Any]]] = {}
        
        # Load existing state
        self._load_state()
        
        # Set up observer
        self.observer = WatcherObserver(self)
        
        if verbose:
            logger.info(f"📥 Log Receiver initialized")
            if len(self.log_paths) > 1:
                logger.info(f"   Watching {len(self.log_paths)} log paths:")
                for lp in self.log_paths:
                    logger.info(f"     - {lp}")
            else:
                logger.info(f"   Log path: {self.log_path}")
            logger.info(f"   Output path: {self.output_path}")
            logger.info(f"   Sync mode: {self.sync_mode}")
    
    def start(self):
        """Start watching the log directory"""
        # First, sync existing log entries
        self._sync_existing_log()
        
        # Then start watching for new entries
        self.observer.start()
        
        if self.verbose:
            logger.info("👀 Receiver watching for log changes")
    
    def stop(self):
        """Stop watching"""
        self.observer.stop()
        
        # Save state
        self._save_state()
        
        if self.verbose:
            stats = self.get_stats()
            logger.info("🛑 Receiver stopped")
            logger.info(f"   Files synced: {len(self._file_versions)}")
            logger.info(f"   Versions processed: {len(self._processed_versions)}")
    
    def process_event(self, event: FileEvent):
        """Process a file system event from the log directory"""
        # We only care about new files/directories in the log
        if event.event_type in [EventType.FILE_CREATED, EventType.FILE_MODIFIED]:
            # Check if it's a metadata.json file
            if event.src_path.name == "metadata.json":
                self._process_log_entry(event.src_path.parent)
        elif event.event_type == EventType.DIRECTORY_CREATED:
            # New version directory created
            metadata_path = event.src_path / "metadata.json"
            if metadata_path.exists():
                self._process_log_entry(event.src_path)
    
    def _sync_existing_log(self):
        """Sync all existing entries in the log"""
        if self.verbose:
            logger.info("🔄 Syncing existing log entries...")
        
        synced_count = 0
        
        # Process all version directories in the log
        for version_dir in sorted(self.log_path.iterdir()):
            if version_dir.is_dir() and version_dir.name not in self._processed_versions:
                metadata_file = version_dir / "metadata.json"
                if metadata_file.exists():
                    if self._process_log_entry(version_dir):
                        synced_count += 1
        
        if self.verbose and synced_count > 0:
            logger.info(f"   Synced {synced_count} new entries")
    
    def _process_log_entry(self, version_dir: Path) -> bool:
        """Process a single log entry"""
        version_id = version_dir.name
        
        # Skip if already processed
        if version_id in self._processed_versions:
            return False
        
        try:
            # Read metadata
            metadata_file = version_dir / "metadata.json"
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            # Extract file information
            file_path = metadata.get('file_path', '')
            event_type = metadata.get('event_type', '')
            
            if not file_path:
                return False
            
            # Update file versions tracking
            if file_path not in self._file_versions:
                self._file_versions[file_path] = []
            
            self._file_versions[file_path].append(metadata)
            
            # Process based on sync mode
            if self.sync_mode == "latest":
                # Only sync if this is the latest version
                if self._is_latest_version(file_path, metadata):
                    self._sync_file(metadata, version_dir)
            else:
                # Sync all versions (with version suffix)
                self._sync_file_version(metadata, version_dir)
            
            # Mark as processed
            self._processed_versions.add(version_id)
            
            if self.verbose:
                logger.info(f"✅ Processed: {version_id} ({event_type})")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to process log entry {version_dir}: {e}")
            return False
    
    def _is_latest_version(self, file_path: str, metadata: Dict[str, Any]) -> bool:
        """Check if this is the latest version of a file"""
        versions = self._file_versions.get(file_path, [])
        if not versions:
            return True
        
        # Sort by timestamp
        sorted_versions = sorted(versions, key=lambda v: v.get('timestamp', ''))
        return metadata == sorted_versions[-1]
    
    def _sync_file(self, metadata: Dict[str, Any], version_dir: Path):
        """Sync a file to the output directory with lock file support"""
        file_path = metadata.get('file_path', '')
        event_type = metadata.get('event_type', '')
        
        # Calculate relative path
        original_path = Path(file_path)
        relative_path = original_path.name  # Just filename for now
        output_file = self.output_path / relative_path
        lock_path = output_file.parent / f"{output_file.name}{self.lock_file_suffix}"
        
        if event_type == 'file_deleted':
            # Remove file if it exists
            if output_file.exists():
                output_file.unlink()
                if self.verbose:
                    logger.info(f"   🗑️  Deleted: {relative_path}")
        else:
            # Create lock file before syncing
            lock_path.touch()
            if self.verbose:
                logger.info(f"   🔒 Created lock for {output_file.name}")
            
            try:
                # Find the actual file content
                stored_file = None
                for item in version_dir.iterdir():
                    if item.is_file() and item.name not in ['metadata.json', '*.tar.gz']:
                        stored_file = item
                        break
                
                if stored_file:
                    # Copy file to output
                    shutil.copy2(stored_file, output_file)
                    if self.verbose:
                        logger.info(f"   📄 Synced: {relative_path}")
                else:
                    # Try to extract from archive if present
                    archive_files = list(version_dir.glob("*.tar.gz"))
                    if archive_files:
                        self._extract_from_archive(archive_files[0], output_file, metadata)
                
                # Remove lock after delay
                time.sleep(self.lock_file_delay)
                if lock_path.exists():
                    lock_path.unlink()
                    if self.verbose:
                        logger.info(f"   🔓 Removed lock for {output_file.name}")
                        
            except Exception as e:
                # Clean up lock on error
                if lock_path.exists():
                    lock_path.unlink()
                raise
    
    def _sync_file_version(self, metadata: Dict[str, Any], version_dir: Path):
        """Sync a specific version of a file (with version suffix)"""
        file_path = metadata.get('file_path', '')
        version_id = metadata.get('version_id', '')
        
        # Calculate versioned filename
        original_path = Path(file_path)
        name_parts = original_path.stem, original_path.suffix
        versioned_name = f"{name_parts[0]}.{version_id[:8]}{name_parts[1]}"
        output_file = self.output_path / versioned_name
        
        # Same logic as _sync_file but with versioned filename
        self._sync_file(metadata, version_dir)
    
    def _extract_from_archive(self, archive_path: Path, output_file: Path, metadata: Dict[str, Any]):
        """Extract file from archive"""
        # This will be implemented when we handle archives
        pass
    
    def _load_state(self):
        """Load receiver state from disk"""
        state_file = self.output_path / ".syft_sync_state.json"
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                
                self._processed_versions = set(state.get('processed_versions', []))
                self._file_versions = state.get('file_versions', {})
                
                if self.verbose:
                    logger.info(f"   Loaded state: {len(self._processed_versions)} processed versions")
                    
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
    
    def _save_state(self):
        """Save receiver state to disk"""
        state_file = self.output_path / ".syft_sync_state.json"
        
        state = {
            'processed_versions': list(self._processed_versions),
            'file_versions': self._file_versions,
            'last_sync': datetime.now().isoformat()
        }
        
        try:
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status"""
        return {
            'files_tracked': len(self._file_versions),
            'versions_processed': len(self._processed_versions),
            'output_path': str(self.output_path),
            'sync_mode': self.sync_mode
        }