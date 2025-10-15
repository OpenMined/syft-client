"""
Syft-integrated storage implementation for append-only logging
"""
import json
import hashlib
import uuid
import tarfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Union
import logging

from syft_client.sync.message import SyftMessage
SYFT_CLIENT_AVAILABLE = True

from ..core.events import FileEvent, EventType
from .log_storage import LogStorage


logger = logging.getLogger(__name__)


class SyftLogStorage(LogStorage):
    """Storage backend that creates SyftMessage objects for file events"""
    
    def __init__(self, log_path: Path, verbose: bool = False):
        """Initialize Syft-integrated log storage"""
        super().__init__(log_path, verbose)
        
        if not SYFT_CLIENT_AVAILABLE:
            raise ImportError("syft_client is required for SyftLogStorage. Make sure syft-client is in your Python path")
        
        # Track message archives
        self._message_archives: Dict[str, str] = {}
        
        # Messages root directory for syft_client
        self.messages_root = self.log_path / "syft_messages"
        self.messages_root.mkdir(exist_ok=True)
        
        # Load existing archives
        self._load_existing_archives()
    
    def log_event(self, event: FileEvent) -> Optional[str]:
        """Log a file event as a SyftMessage"""
        if event.is_directory:
            return None
        
        # Generate version ID
        timestamp = event.timestamp.strftime("%Y%m%d_%H%M%S_%f")[:-3]
        file_name = event.src_path.name
        unique_id = hashlib.md5(f"{timestamp}_{file_name}".encode()).hexdigest()[:8]
        version_id = f"{timestamp}_{file_name.replace('.', '_')}_{unique_id}"
        
        try:
            # Create SyftMessage for this event
            syft_message = self._create_syft_message(event, version_id)
            
            if syft_message:
                # Copy file to message data directory if it exists
                if event.event_type != EventType.FILE_DELETED and event.src_path.exists():
                    syft_message.add_file(event.src_path)
                
                # Add event metadata to the message
                event_metadata = self._create_metadata(event, version_id, syft_message)
                syft_message.metadata.update(event_metadata)
                
                # Write metadata
                syft_message.write_metadata()
                
                # Create archive - this returns the path
                created_archive_path = syft_message.create_archive()
                
                if created_archive_path:
                    # Move archive directly to log directory with version ID as filename
                    import shutil
                    archive_path = self.log_path / f"{version_id}.tar.gz"
                    shutil.move(created_archive_path, str(archive_path))
                    
                    # Track archive location
                    self._message_archives[version_id] = str(archive_path)
                    
                    if self.verbose:
                        logger.info(f"📦 Created SyftMessage archive: {archive_path}")
            
            # Update index with the metadata we added to the message
            self._update_index(str(event.src_path), event_metadata)
            
            self._version_count += 1
            
            if self.verbose:
                logger.info(f"📸 Logged Syft version: {version_id}")
            
            return version_id
            
        except Exception as e:
            logger.error(f"Failed to create SyftMessage for {event.src_path}: {e}")
            # Fall back to regular logging
            return super().log_event(event)
    
    def _create_syft_message(self, event: FileEvent, version_id: str) -> Optional[SyftMessage]:
        """Create a SyftMessage for a file event"""
        try:
            # Create metadata for the message
            metadata = {
                "version_id": version_id,
                "event_type": event.event_type.value,
                "timestamp": event.timestamp.isoformat(),
                "file_path": str(event.src_path),
                "file_name": event.src_path.name,
                "size": event.size,
                "hash": event.hash or self._calculate_file_hash(event.src_path),
            }
            
            if event.dest_path:
                metadata["dest_path"] = str(event.dest_path)
            
            # Use a dummy sender/recipient for file events
            sender_email = "syft-watcher@local"
            recipient_email = "log@local"
            
            # Create SyftMessage using the create class method
            message = SyftMessage.create(
                sender_email=sender_email,
                recipient_email=recipient_email,
                message_root=self.messages_root,
                metadata=metadata
            )
            
            return message
            
        except Exception as e:
            logger.error(f"Failed to create SyftMessage: {e}")
            return None
    
    def _create_metadata(self, event: FileEvent, version_id: str, 
                        syft_message: Optional[SyftMessage]) -> Dict[str, Any]:
        """Create metadata including Syft information"""
        metadata = {
            "version_id": version_id,
            "timestamp": event.timestamp.isoformat(),
            "event_type": event.event_type.value,
            "file_path": str(event.src_path),
            "file_name": event.src_path.name,
            "size": event.size,
            "hash": event.hash or self._calculate_file_hash(event.src_path),
        }
        
        if event.dest_path:
            metadata["dest_path"] = str(event.dest_path)
        
        if syft_message:
            metadata["syft_message_id"] = syft_message.message_id
            metadata["has_syft_archive"] = True
            metadata["archive_path"] = self._message_archives.get(version_id)
            metadata["sender_email"] = syft_message.sender_email
            metadata["recipient_email"] = syft_message.recipient_email
        else:
            metadata["has_syft_archive"] = False
        
        return metadata
    
    def get_syft_message(self, version_id: str) -> Optional[SyftMessage]:
        """Retrieve a SyftMessage from archive"""
        archive_path = self._message_archives.get(version_id)
        if not archive_path or not Path(archive_path).exists():
            return None
        
        try:
            # Load message from archive
            message = SyftMessage.load_from_archive(str(archive_path))
            return message
            
        except Exception as e:
            logger.error(f"Failed to load SyftMessage from archive: {e}")
            return None
    
    def get_file_content_from_syft(self, version_id: str) -> Optional[Union[str, bytes]]:
        """Extract file content from SyftMessage archive"""
        archive_path = self._message_archives.get(version_id)
        if not archive_path or not Path(archive_path).exists():
            return None
        
        try:
            # Extract archive to temporary location
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract tar.gz
                with tarfile.open(archive_path, 'r:gz') as tar:
                    tar.extractall(temp_dir)
                
                # Find the data directory
                message_dir = Path(temp_dir) / version_id
                data_dir = message_dir / "data"
                
                if data_dir.exists():
                    # Get the first file in data directory
                    for file_path in data_dir.iterdir():
                        if file_path.is_file():
                            try:
                                return file_path.read_text()
                            except UnicodeDecodeError:
                                return file_path.read_bytes()
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to extract file content from SyftMessage: {e}")
            return None
    
    def restore_from_syft(self, version_id: str, restore_path: str) -> bool:
        """Restore a file from its SyftMessage"""
        content = self.get_file_content_from_syft(version_id)
        if content is None:
            # Try to restore from stored file in version directory
            version_dir = self.log_path / version_id
            for file_path in version_dir.iterdir():
                if file_path.is_file() and file_path.suffix not in ['.json', '.gz']:
                    try:
                        import shutil
                        shutil.copy2(file_path, restore_path)
                        if self.verbose:
                            logger.info(f"✅ Restored from version directory: {restore_path}")
                        return True
                    except Exception:
                        pass
            
            return False
        
        try:
            restore_file = Path(restore_path)
            restore_file.parent.mkdir(parents=True, exist_ok=True)
            
            if isinstance(content, bytes):
                restore_file.write_bytes(content)
            else:
                restore_file.write_text(content)
            
            if self.verbose:
                logger.info(f"✅ Restored from SyftMessage: {restore_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore from SyftMessage: {e}")
            return False
    
    def _load_existing_archives(self):
        """Load metadata from existing tar.gz archives"""
        import tarfile
        import tempfile
        
        for archive_path in sorted(self.log_path.glob("*.tar.gz")):
            try:
                # Extract version ID from filename
                version_id = archive_path.stem  # Remove .tar.gz
                
                # Track the archive
                self._message_archives[version_id] = str(archive_path)
                
                # Extract metadata from archive
                with tempfile.TemporaryDirectory() as temp_dir:
                    with tarfile.open(archive_path, 'r:gz') as tar:
                        tar.extractall(temp_dir, filter='data')
                    
                    # Find and read metadata JSON files
                    temp_path = Path(temp_dir)
                    for json_file in temp_path.rglob("*.json"):
                        with open(json_file, 'r') as f:
                            metadata = json.load(f)
                        
                        # Look for our event metadata
                        if 'file_path' in metadata and 'version_id' in metadata:
                            self._update_index(metadata['file_path'], metadata)
                            self._version_count += 1
                            break
                
            except Exception as e:
                logger.error(f"Failed to load metadata from archive {archive_path}: {e}")