"""
Syft-integrated Append-Only Log Watcher
Creates SyftMessage archives for all file changes
"""

from pathlib import Path
from typing import Optional, List, Dict, Any, Union
import logging

from .append_only import AppendOnlyLogWatcher
from ..storage.syft_storage import SyftLogStorage
from ..core.events import FileEvent, EventType, EventHandler


logger = logging.getLogger(__name__)


class MulticastEventHandler(EventHandler):
    """Event handler that broadcasts to multiple log storages"""
    
    def __init__(self, log_storages, watcher):
        super().__init__()
        self.log_storages = log_storages
        self.watcher = watcher
    
    def on_file_created(self, event: FileEvent):
        """Log file creation to all storages"""
        if self.watcher._is_duplicate(event.src_path):
            return
        for storage in self.log_storages:
            storage.log_event(event)
    
    def on_file_modified(self, event: FileEvent):
        """Log file modification to all storages"""
        if self.watcher._is_duplicate(event.src_path):
            return
        for storage in self.log_storages:
            storage.log_event(event)
    
    def on_file_deleted(self, event: FileEvent):
        """Log file deletion to all storages"""
        for storage in self.log_storages:
            storage.log_event(event)
    
    def on_file_moved(self, event: FileEvent):
        """Log file move to all storages"""
        for storage in self.log_storages:
            storage.log_event(event)
    
    # Directory events - we don't log these but need to implement them
    def on_directory_created(self, event: FileEvent):
        """Ignore directory creation"""
        pass
    
    def on_directory_modified(self, event: FileEvent):
        """Ignore directory modification"""
        pass
    
    def on_directory_deleted(self, event: FileEvent):
        """Ignore directory deletion"""
        pass
    
    def on_directory_moved(self, event: FileEvent):
        """Ignore directory move"""
        pass


class SyftWatcher(AppendOnlyLogWatcher):
    """
    Watcher that creates SyftMessage objects for each file change.
    Each change is stored as a SyftMessage archive that can be shared/synchronized.
    Supports broadcasting to multiple log paths for P2P scenarios.
    """
    
    def __init__(
        self,
        watch_path: str,
        log_path: Optional[Union[str, List[str]]] = None,
        exclude_patterns: Optional[List[str]] = None,
        verbose: bool = False,
        lock_file_suffix: str = ".sync_lock"
    ):
        """
        Initialize the Syft-integrated append-only log watcher
        
        Args:
            watch_path: Directory to watch
            log_path: Directory or list of directories to store logs (for broadcasting)
            exclude_patterns: Patterns to exclude from watching
            verbose: Print detailed output
            lock_file_suffix: Suffix for lock files (default: .sync_lock)
        """
        self.lock_file_suffix = lock_file_suffix
        
        # Handle multiple log paths for broadcasting
        if isinstance(log_path, str):
            log_paths = [log_path]
        elif isinstance(log_path, list):
            log_paths = log_path
        else:
            # Default: single log next to watch path
            log_paths = [None]
        
        # Create storage for each log path first
        self.log_storages = []
        self.log_paths = []
        
        for lp in log_paths:
            if lp is None:
                lp = str(Path(watch_path).parent / f"{Path(watch_path).name}_log")
            path = Path(lp)
            self.log_paths.append(path)
            storage = SyftLogStorage(path, verbose=verbose)
            self.log_storages.append(storage)
        
        # Initialize base class with first log path
        super().__init__(watch_path, log_paths[0], exclude_patterns, verbose)
        
        # Replace the single storage with our first multi-storage
        # (parent class creates its own, but we replace it)
        self.log_storage = self.log_storages[0]
        self.log_path = self.log_paths[0]
        
        # Replace event handler with multicast version
        self.event_handler = MulticastEventHandler(self.log_storages, self)
        
        if verbose:
            logger.info(f"🔷 Syft Append-Only Log Watcher initialized")
            logger.info(f"   Watch path: {watch_path}")
            if len(self.log_paths) > 1:
                logger.info(f"   Broadcasting to {len(self.log_paths)} logs:")
                for lp in self.log_paths:
                    logger.info(f"     - {lp}")
            else:
                logger.info(f"   Log path: {self.log_paths[0]}")
            logger.info(f"   Creating SyftMessage archives for all changes")
    
    def should_process(self, path):
        """Override to skip files with lock suffix"""
        path = Path(path)
        
        # Skip if there's a lock file
        lock_path = path.parent / f"{path.name}{self.lock_file_suffix}"
        if lock_path.exists():
            if self.verbose:
                logger.info(f"⏭️  Skipping {path.name} - lock file exists")
            return False
            
        # Skip lock files themselves
        if path.name.endswith(self.lock_file_suffix):
            return False
            
        # Call parent's should_process
        return super().should_process(path)
    
    def _initial_scan(self):
        """Override to broadcast initial scan to all storages"""
        if self.verbose:
            logger.info(f"📂 Performing initial scan of {self.watch_path}")
        
        file_count = 0
        for path in self.watch_path.rglob('*'):
            if path.is_file() and self.should_process(path):
                # Create initial event
                event = FileEvent(
                    event_type=EventType.FILE_CREATED,
                    src_path=path,
                    size=path.stat().st_size
                )
                
                # Process through all storages
                if not self._is_duplicate(path):
                    for storage in self.log_storages:
                        storage.log_event(event)
                    self._tracked_files.add(path)
                    file_count += 1
        
        if self.verbose:
            logger.info(f"   Found {file_count} files to track")
    
    def process_event(self, event: FileEvent):
        """Override to broadcast events to all storages"""
        if event.is_directory:
            return
        
        # Check for duplicates
        if event.event_type in [EventType.FILE_CREATED, EventType.FILE_MODIFIED]:
            if self._is_duplicate(event.src_path):
                if self.verbose:
                    logger.debug(f"Skipping duplicate: {event.src_path}")
                return
        
        # Track the file
        self._tracked_files.add(event.src_path)
        
        # Log to all storages
        for storage in self.log_storages:
            storage.log_event(event)
    
    def get_syft_message(self, file_path: str, version_id: str):
        """Get the SyftMessage for a specific version"""
        return self.log_storage.get_syft_message(version_id)
    
    def restore_from_syft(self, version_id: str, restore_path: str) -> bool:
        """Restore a file from its SyftMessage"""
        return self.log_storage.restore_from_syft(version_id, restore_path)
    
    def get_all_syft_messages(self, file_path: str) -> List[Dict[str, Any]]:
        """Get all SyftMessages for a file's history"""
        history = self.get_file_history(file_path)
        messages = []
        
        for version in history:
            if version.get('has_syft_archive'):
                message = self.get_syft_message(file_path, version['version_id'])
                if message:
                    messages.append({
                        'version_id': version['version_id'],
                        'timestamp': version['timestamp'],
                        'event_type': version['event_type'],
                        'message': message
                    })
        
        return messages
    
    def export_syft_archive(self, version_id: str, export_path: str) -> bool:
        """Export a SyftMessage archive to a file"""
        archive_path = self.log_storage._message_archives.get(version_id)
        if not archive_path or not Path(archive_path).exists():
            logger.error(f"No archive found for version {version_id}")
            return False
        
        try:
            import shutil
            shutil.copy2(archive_path, export_path)
            if self.verbose:
                logger.info(f"📤 Exported SyftMessage archive to: {export_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export archive: {e}")
            return False
    
    def import_syft_archive(self, archive_path: str) -> Optional[str]:
        """Import a SyftMessage archive into the log"""
        try:
            from syft import SyftArchive
            
            # Load the archive
            with open(archive_path, 'rb') as f:
                archive_data = f.read()
            
            archive = SyftArchive.from_bytes(archive_data)
            message = archive.message
            
            # Extract metadata from message
            if not hasattr(message, 'contents') or not isinstance(message.contents, dict):
                logger.error("Invalid SyftMessage format")
                return None
            
            contents = message.contents
            version_id = contents.get('version_id')
            if not version_id:
                logger.error("No version_id in SyftMessage")
                return None
            
            # Create version directory
            version_dir = self.log_path / version_id
            version_dir.mkdir(parents=True, exist_ok=True)
            
            # Save archive
            import shutil
            dest_archive = version_dir / "syft_archive.zip"
            shutil.copy2(archive_path, dest_archive)
            
            # Update tracking
            self.log_storage._message_archives[version_id] = str(dest_archive)
            
            # Create metadata
            metadata = {
                "version_id": version_id,
                "timestamp": contents.get('timestamp'),
                "event_type": contents.get('event_type'),
                "file_path": contents.get('file_path'),
                "file_name": contents.get('file_name'),
                "size": contents.get('size'),
                "hash": contents.get('hash'),
                "syft_message_id": str(message.id),
                "has_syft_archive": True,
                "archive_path": str(dest_archive),
                "imported": True
            }
            
            # Write metadata
            metadata_file = version_dir / "metadata.json"
            import json
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Update index
            file_path = contents.get('file_path', '')
            self.log_storage._update_index(file_path, metadata)
            
            if self.verbose:
                logger.info(f"📥 Imported SyftMessage archive: {version_id}")
            
            return version_id
            
        except Exception as e:
            logger.error(f"Failed to import archive: {e}")
            return None