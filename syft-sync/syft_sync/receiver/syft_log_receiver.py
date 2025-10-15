"""
Syft Log Receiver - Processes SyftMessage archives from log
"""
import json
import tarfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from .log_receiver import LogReceiver
from syft_client.sync.message import SyftMessage

SYFT_CLIENT_AVAILABLE = True


logger = logging.getLogger(__name__)


class SyftLogReceiver(LogReceiver):
    """
    Receiver that processes SyftMessage archives from the log
    """
    
    def __init__(
        self,
        log_path: str,
        output_path: str,
        exclude_patterns: Optional[list] = None,
        verbose: bool = False,
        sync_mode: str = "latest",
        lock_file_suffix: str = ".sync_lock",
        lock_file_delay: float = 1.0
    ):
        """Initialize Syft log receiver"""
        super().__init__(log_path, output_path, exclude_patterns, verbose, sync_mode)
        
        self.lock_file_suffix = lock_file_suffix
        self.lock_file_delay = lock_file_delay
        
        if not SYFT_CLIENT_AVAILABLE:
            raise ImportError("syft_client is required for SyftLogReceiver")
        
        if verbose:
            logger.info("🔷 Syft Log Receiver initialized")
    
    def _sync_file(self, metadata: Dict[str, Any], version_dir: Path):
        """Sync a file from SyftMessage archive"""
        # Check if this has a SyftMessage archive
        if metadata.get('has_syft_archive'):
            archive_files = list(version_dir.glob("*.tar.gz"))
            if archive_files:
                self._sync_from_syft_archive(archive_files[0], metadata)
                return
        
        # Fall back to regular sync
        super()._sync_file(metadata, version_dir)
    
    def _sync_from_syft_archive(self, archive_path: Path, metadata: Dict[str, Any]):
        """Extract and sync file from SyftMessage archive with lock file support"""
        try:
            file_path = metadata.get('file_path', '')
            event_type = metadata.get('event_type', '')
            version_id = metadata.get('version_id', '')
            
            # Calculate output path
            original_path = Path(file_path)
            relative_path = original_path.name
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
                    # Extract from SyftMessage archive
                    import tempfile
                    with tempfile.TemporaryDirectory() as temp_dir:
                        # Extract archive
                        with tarfile.open(archive_path, 'r:gz') as tar:
                            tar.extractall(temp_dir)
                        
                        # Find the data directory
                        message_dir = Path(temp_dir) / version_id
                        data_dir = message_dir / "data"
                        
                        if data_dir.exists():
                            # Copy files from data directory
                            for src_file in data_dir.iterdir():
                                if src_file.is_file():
                                    shutil.copy2(src_file, output_file)
                                    if self.verbose:
                                        logger.info(f"   📦 Synced from SyftMessage: {relative_path}")
                                    break
                        
                        # Also check for metadata
                        metadata_file = message_dir / f"{version_id}.json"
                        if metadata_file.exists() and self.verbose:
                            with open(metadata_file, 'r') as f:
                                msg_metadata = json.load(f)
                            logger.debug(f"   Message metadata: {msg_metadata}")
                    
                    # Remove lock after delay
                    import time
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
                        
        except Exception as e:
            logger.error(f"Failed to sync from SyftMessage archive: {e}")
            # Try regular sync as fallback
            super()._sync_file(metadata, archive_path.parent)
    
    def process_syft_message(self, message: SyftMessage):
        """Process a SyftMessage directly"""
        try:
            # Extract metadata
            metadata = message.metadata
            version_id = metadata.get('version_id', message.message_id)
            
            # Create a temporary version directory
            temp_version_dir = self.log_path / f"temp_{version_id}"
            temp_version_dir.mkdir(exist_ok=True)
            
            # Save metadata
            metadata_file = temp_version_dir / "metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Process the entry
            self._process_log_entry(temp_version_dir)
            
            # Clean up
            shutil.rmtree(temp_version_dir)
            
        except Exception as e:
            logger.error(f"Failed to process SyftMessage: {e}")
    
    def import_syft_archive(self, archive_path: str) -> bool:
        """Import and process a SyftMessage archive file"""
        try:
            # Load the message from archive
            message = SyftMessage.load_from_archive(archive_path)
            
            # Process it
            self.process_syft_message(message)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to import SyftMessage archive: {e}")
            return False