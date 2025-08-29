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
               message_root: Path) -> "SyftMessage":
        """Create a new SyftMessage with minimal schema"""
        timestamp = datetime.now().timestamp()
        random_id = hashlib.sha256(f"{timestamp}{sender_email}{recipient_email}".encode()).hexdigest()[:8]
        message_id = f"syft_message_{int(timestamp)}_{random_id}"
        
        message_path = message_root / message_id
        message = cls(message_path)
        
        # Initialize with minimal metadata
        message.set_metadata({
            "id": message_id,
            "from": sender_email,
            "to": recipient_email,
            "ts": int(timestamp),
            "files": []
        })
        
        return message
    
    def add_file(self, 
                 source_path: Path, 
                 path: str,
                 permissions: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
        """Add a file to the message with minimal schema"""
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
            
            # Create minimal file entry
            file_entry = {
                "path": path,
                "hash": file_hash,
                "size": dest_path.stat().st_size,
            }
            
            # Add permissions if provided
            if permissions:
                file_entry["perms"] = {
                    "r": permissions.get("read", ["*"]),
                    "w": permissions.get("write", []),
                }
            
            # Store internal filename for extraction
            file_entry["_internal_name"] = filename
            
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
    
    def get_file_metadata(self, path: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a single file by path"""
        for file_entry in self.get_files():
            if file_entry["path"] == path:
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
                    # Use internal name if available, otherwise derive from path
                    internal_name = file_entry.get("_internal_name")
                    if not internal_name:
                        # Extract filename from path
                        internal_name = os.path.basename(file_entry["path"])
                    
                    clean_name = self._sanitize_filename(internal_name)
                    file_path = self.files_dir / clean_name
                    file_path = self._validate_path(file_path)
                    
                    if not file_path.exists():
                        return False, f"Missing file: {file_entry['path']}"
                    
                    # Verify hash using streaming
                    actual_hash = self.calculate_file_hash(file_path)
                    if actual_hash != file_entry["hash"]:
                        return False, f"Hash mismatch for {file_entry['path']}"
                        
                except ValueError as e:
                    return False, f"Invalid file entry: {e}"
            
            return True, None
    
    def extract_file(self, path: str, destination: Path, verify_hash: bool = True):
        """Extract a single file by path with validation and optional hash verification"""
        with self.shared_access():
            # Find file metadata (use no-lock version)
            metadata = self._get_metadata_no_lock()
            files = metadata.get("files", [])
            
            file_meta = None
            for entry in files:
                if entry["path"] == path:
                    file_meta = entry
                    break
            
            if not file_meta:
                raise ValueError(f"File not found in message: {path}")
            
            # Get internal name
            internal_name = file_meta.get("_internal_name")
            if not internal_name:
                internal_name = os.path.basename(path)
            
            clean_name = self._sanitize_filename(internal_name)
            
            # Validate source path
            source_path = self.files_dir / clean_name
            source_path = self._validate_path(source_path)
            
            if not source_path.exists():
                raise ValueError(f"File data missing: {path}")
            
            # Verify hash if requested
            if verify_hash:
                actual_hash = self.calculate_file_hash(source_path)
                if actual_hash != file_meta["hash"]:
                    raise ValueError(f"Hash mismatch for {path}")
            
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
        return self.get_metadata().get("id")
    
    @property
    def sender_email(self) -> Optional[str]:
        return self.get_metadata().get("from")
    
    @property
    def recipient_email(self) -> Optional[str]:
        return self.get_metadata().get("to")
    
    @property
    def timestamp(self) -> Optional[int]:
        return self.get_metadata().get("ts")
    
    @property
    def is_ready(self) -> bool:
        """Check if message is ready to send"""
        lock_info = self.get_lock_info()
        return lock_info.get("ready", False) if lock_info else False