"""
SyftMessage implementation for transport-agnostic file syncing
"""
import shutil
import tempfile
import os
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from .syft_file_backed_view import SyftFileBackedView


class SyftMessage(SyftFileBackedView):
    """A message for syncing files between SyftBox users with enhanced safety"""
    
    def __init__(self, message_path: Path):
        super().__init__(message_path, schema_version="1.0.0")
        self.files_dir = self.data_dir / "files"
        self.files_dir.mkdir(exist_ok=True)
    
    @classmethod
    def create(cls, 
               sender_email: str, 
               recipient_email: str,
               message_root: Path,
               message_type: str = "file_sync") -> "SyftMessage":
        """Create a new SyftMessage"""
        timestamp = datetime.now().timestamp()
        random_id = hashlib.sha256(f"{timestamp}{sender_email}{recipient_email}".encode()).hexdigest()[:8]
        message_id = f"gdrive_{sender_email}_{recipient_email}_{int(timestamp)}_{random_id}"
        
        message_path = message_root / message_id
        message = cls(message_path)
        
        # Initialize metadata using parent class method
        message.set_metadata({
            "message_id": message_id,
            "sender_email": sender_email,
            "recipient_email": recipient_email,
            "timestamp": timestamp,
            "message_type": message_type,
            "transport": "gdrive",
            "files": []
        })
        
        return message
    
    def add_file(self, 
                 source_path: Path, 
                 syftbox_path: str,
                 permissions: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
        """Add a file to the message with streaming and validation"""
        source_path = Path(source_path).resolve()
        
        # Validate source exists
        if not source_path.exists():
            raise ValueError(f"Source file not found: {source_path}")
        
        # Sanitize filename
        filename = self._sanitize_filename(source_path.name)
        
        with self.exclusive_access():
            dest_path = self.files_dir / filename
            dest_path = self._validate_path(dest_path)
            
            # Copy file atomically using streaming
            with tempfile.NamedTemporaryFile(mode='wb', dir=self.files_dir,
                                           delete=False, suffix='.tmp') as tmp:
                # Stream copy to avoid loading large files in memory
                with open(source_path, 'rb') as src:
                    shutil.copyfileobj(src, tmp, length=8192)
                tmp_path = tmp.name
            
            # Calculate hash using streaming
            file_hash = self.calculate_file_hash(Path(tmp_path))
            
            # Atomic rename
            os.replace(tmp_path, dest_path)
            
            # Copy file stats
            shutil.copystat(source_path, dest_path)
            
            # Create file entry
            file_entry = {
                "filename": filename,
                "syftbox_path": syftbox_path,
                "file_hash": file_hash,
                "file_size": dest_path.stat().st_size,
                "permissions": permissions or {"read": ["*"], "write": [], "admin": []},
                "change_timestamp": datetime.now().timestamp()
            }
            
            # Update metadata atomically (we already have exclusive lock)
            metadata = self._get_metadata_no_lock()
            metadata.setdefault("files", []).append(file_entry)
            self._set_metadata_no_lock(metadata)
            
            return file_entry
    
    def get_files(self) -> List[Dict[str, Any]]:
        """Get list of files in the message"""
        return self.get_metadata().get("files", [])
    
    def get_file_path(self, filename: str) -> Optional[Path]:
        """Get the path to a specific file in the message"""
        clean_name = self._sanitize_filename(filename)
        file_path = self.files_dir / clean_name
        return file_path if file_path.exists() else None
    
    def get_file_metadata(self, filename: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a single file without loading all files"""
        clean_name = self._sanitize_filename(filename)
        for file_entry in self.get_files():
            if file_entry["filename"] == clean_name:
                return file_entry
        return None
    
    def finalize(self):
        """Finalize the message (ready for sending)"""
        self.lock(ready=True, message_id=self.message_id)
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate message integrity with streaming hash verification"""
        with self.shared_access():
            # Check basic structure
            if not self.is_locked():
                return False, "Message not finalized (no lock file)"
            
            if not self.validate_checksum():
                return False, "Checksum mismatch"
            
            # Get files metadata (use no-lock version since we have shared access)
            metadata = self._get_metadata_no_lock()
            files = metadata.get("files", [])
            
            # Verify all files exist and match hashes
            for file_entry in files:
                try:
                    clean_name = self._sanitize_filename(file_entry["filename"])
                    file_path = self.files_dir / clean_name
                    file_path = self._validate_path(file_path)
                    
                    if not file_path.exists():
                        return False, f"Missing file: {file_entry['filename']}"
                    
                    # Verify hash using streaming
                    actual_hash = self.calculate_file_hash(file_path)
                    if actual_hash != file_entry["file_hash"]:
                        return False, f"Hash mismatch for {file_entry['filename']}"
                        
                except ValueError as e:
                    return False, f"Invalid file entry: {e}"
            
            return True, None
    
    def extract_file(self, filename: str, destination: Path, verify_hash: bool = True):
        """Extract a single file with validation and optional hash verification"""
        clean_name = self._sanitize_filename(filename)
        
        with self.shared_access():
            # Find file metadata (use no-lock version)
            metadata = self._get_metadata_no_lock()
            files = metadata.get("files", [])
            
            file_meta = None
            for entry in files:
                if entry["filename"] == clean_name:
                    file_meta = entry
                    break
            
            if not file_meta:
                raise ValueError(f"File not found in message: {filename}")
            
            # Validate source path
            source_path = self.files_dir / clean_name
            source_path = self._validate_path(source_path)
            
            if not source_path.exists():
                raise ValueError(f"File data missing: {filename}")
            
            # Verify hash if requested
            if verify_hash:
                actual_hash = self.calculate_file_hash(source_path)
                if actual_hash != file_meta["file_hash"]:
                    raise ValueError(f"Hash mismatch for {filename}")
            
            # Stream copy to destination
            destination = Path(destination).resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            with tempfile.NamedTemporaryFile(mode='wb', dir=destination.parent,
                                           delete=False, suffix='.tmp') as tmp:
                with open(source_path, 'rb') as src:
                    shutil.copyfileobj(src, tmp, length=8192)
                tmp_path = tmp.name
            
            # Atomic rename
            os.replace(tmp_path, destination)
            
            # Copy file stats
            shutil.copystat(source_path, destination)
    
    def add_readme(self, content: str):
        """Add a README.html file to the message"""
        readme_path = self.path / "README.html"
        with self.exclusive_access():
            with tempfile.NamedTemporaryFile(mode='w', dir=self.path,
                                           delete=False, suffix='.tmp') as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            os.replace(tmp_path, readme_path)
    
    # Convenience properties
    @property
    def message_id(self) -> Optional[str]:
        return self.get_metadata().get("message_id")
    
    @property
    def sender_email(self) -> Optional[str]:
        return self.get_metadata().get("sender_email")
    
    @property
    def recipient_email(self) -> Optional[str]:
        return self.get_metadata().get("recipient_email")
    
    @property
    def timestamp(self) -> Optional[float]:
        return self.get_metadata().get("timestamp")
    
    @property
    def message_type(self) -> Optional[str]:
        return self.get_metadata().get("message_type")
    
    @property
    def is_ready(self) -> bool:
        """Check if message is ready to send"""
        lock_info = self.get_lock_info()
        return lock_info.get("ready", False) if lock_info else False