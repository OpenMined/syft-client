"""
Base class for file-backed views in SyftBox with safety features
"""
import json
import yaml
import hashlib
import fcntl
import contextlib
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class SyftFileBackedView:
    """Base class for file-backed views with safety features"""
    
    def __init__(self, object_path: Path, schema_version: str = "1.0.0"):
        """
        Initialize a file-backed view.
        
        Args:
            object_path: Path to the view directory
            schema_version: Version of the view schema
        """
        self.path = Path(object_path).resolve()  # Always use absolute paths
        self.path.mkdir(parents=True, exist_ok=True)
        self.schema_version = schema_version
        
        # Define standard paths
        self.metadata_path = self.path / "metadata.yaml"
        self.lock_path = self.path / "lock.json"
        self.data_dir = self.path / "data"
        self.data_dir.mkdir(exist_ok=True)
        
        # Lock file for concurrent access
        self._lock_file_path = self.path / ".write_lock"
    
    # Concurrency control
    @contextlib.contextmanager
    def exclusive_access(self):
        """Acquire exclusive lock for write operations"""
        self._lock_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._lock_file_path, 'w') as lock_file:
            try:
                # Acquire exclusive lock (blocking)
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                yield
            finally:
                # Release lock
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    
    @contextlib.contextmanager
    def shared_access(self):
        """Acquire shared lock for read operations"""
        self._lock_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._lock_file_path, 'w') as lock_file:
            try:
                # Acquire shared lock (blocking)
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_SH)
                yield
            finally:
                # Release lock
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    
    # Atomic metadata management
    def set_metadata(self, metadata: Dict[str, Any]):
        """Write metadata atomically with exclusive lock"""
        with self.exclusive_access():
            self._set_metadata_no_lock(metadata)
    
    def _set_metadata_no_lock(self, metadata: Dict[str, Any]):
        """Internal method to write metadata without acquiring a lock"""
        metadata["_schema_version"] = self.schema_version
        metadata["_updated_at"] = datetime.now().isoformat()
        
        # Write to temporary file first
        with tempfile.NamedTemporaryFile(mode='w', dir=self.path, 
                                       delete=False, suffix='.tmp') as tmp:
            yaml.dump(metadata, tmp, default_flow_style=False)
            tmp_path = tmp.name
        
        # Atomic rename (POSIX compliant)
        os.replace(tmp_path, self.metadata_path)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Read metadata with shared lock"""
        with self.shared_access():
            return self._get_metadata_no_lock()
    
    def _get_metadata_no_lock(self) -> Dict[str, Any]:
        """Internal method to read metadata without acquiring a lock"""
        if not self.metadata_path.exists():
            return {"_schema_version": self.schema_version}
        with open(self.metadata_path, 'r') as f:
            return yaml.safe_load(f) or {}
    
    def update_metadata(self, updates: Dict[str, Any]):
        """Update specific metadata fields atomically"""
        with self.exclusive_access():
            # Read current metadata (no lock needed, we already have exclusive)
            metadata = self._get_metadata_no_lock()
            
            # Update
            metadata.update(updates)
            metadata["_updated_at"] = datetime.now().isoformat()
            
            # Write atomically
            with tempfile.NamedTemporaryFile(mode='w', dir=self.path, 
                                           delete=False, suffix='.tmp') as tmp:
                yaml.dump(metadata, tmp, default_flow_style=False)
                tmp_path = tmp.name
            
            os.replace(tmp_path, self.metadata_path)
    
    def update_metadata_atomic(self, updater_func):
        """Atomically update metadata using a function
        
        Args:
            updater_func: A function that takes the current metadata dict and returns
                          the updated metadata dict. This function will be called
                          while holding an exclusive lock.
                          
        Example:
            # Atomically increment a counter
            def increment(metadata):
                metadata['counter'] = metadata.get('counter', 0) + 1
                return metadata
            
            obj.update_metadata_atomic(increment)
        """
        with self.exclusive_access():
            # Read current metadata
            metadata = self._get_metadata_no_lock()
            
            # Apply the update function
            updated_metadata = updater_func(metadata)
            
            # Ensure metadata is still a dict
            if not isinstance(updated_metadata, dict):
                raise ValueError("Updater function must return a dictionary")
            
            # Add timestamp
            updated_metadata["_updated_at"] = datetime.now().isoformat()
            
            # Write atomically
            with tempfile.NamedTemporaryFile(mode='w', dir=self.path, 
                                           delete=False, suffix='.tmp') as tmp:
                yaml.dump(updated_metadata, tmp, default_flow_style=False)
                tmp_path = tmp.name
            
            os.replace(tmp_path, self.metadata_path)
    
    # Secure data file management
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal"""
        # First check for any path traversal attempts in the original filename
        if '..' in filename or filename.startswith('/') or filename.startswith('\\'):
            raise ValueError(f"Path traversal attempt detected: {filename}")
        
        # Check for any path separators (we only want filenames, not paths)
        if '/' in filename or '\\' in filename:
            raise ValueError(f"Path separators not allowed in filename: {filename}")
        
        # Now safe to get just the filename component
        clean_name = Path(filename).name
        
        # Double-check for empty or dot files
        if not clean_name or clean_name == '.' or clean_name == '..':
            raise ValueError(f"Invalid filename: {filename}")
        
        # Check for hidden files
        if clean_name.startswith('.') and clean_name != '.gitkeep':
            raise ValueError(f"Hidden files not allowed: {filename}")
        
        return clean_name
    
    def _validate_path(self, path: Path) -> Path:
        """Ensure path is within our data directory"""
        resolved = path.resolve()
        allowed_base = self.data_dir.resolve()
        
        if not str(resolved).startswith(str(allowed_base)):
            raise ValueError(f"Path traversal detected: {path}")
        
        return resolved
    
    def write_data_file(self, filename: str, content: bytes) -> Path:
        """Write a data file atomically with path validation"""
        clean_name = self._sanitize_filename(filename)
        
        with self.exclusive_access():
            file_path = self.data_dir / clean_name
            file_path = self._validate_path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write atomically
            with tempfile.NamedTemporaryFile(mode='wb', dir=file_path.parent,
                                           delete=False, suffix='.tmp') as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            os.replace(tmp_path, file_path)
            return file_path
    
    def read_data_file(self, filename: str) -> Optional[bytes]:
        """Read a data file with validation"""
        clean_name = self._sanitize_filename(filename)
        
        with self.shared_access():
            file_path = self.data_dir / clean_name
            file_path = self._validate_path(file_path)
            
            if file_path.exists():
                return file_path.read_bytes()
            return None
    
    def list_data_files(self) -> List[Path]:
        """List all data files"""
        with self.shared_access():
            return list(self.data_dir.rglob("*")) if self.data_dir.exists() else []
    
    # Streaming operations for large files
    def calculate_file_hash(self, file_path: Path, chunk_size: int = 8192) -> str:
        """Calculate hash of a file using streaming"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def write_data_file_stream(self, filename: str, stream, chunk_size: int = 8192) -> Path:
        """Write a data file from a stream"""
        clean_name = self._sanitize_filename(filename)
        
        with self.exclusive_access():
            file_path = self.data_dir / clean_name
            file_path = self._validate_path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to temp file first
            with tempfile.NamedTemporaryFile(mode='wb', dir=file_path.parent,
                                           delete=False, suffix='.tmp') as tmp:
                while chunk := stream.read(chunk_size):
                    tmp.write(chunk)
                tmp_path = tmp.name
            
            # Atomic rename
            os.replace(tmp_path, file_path)
            return file_path
    
    # Enhanced checksum calculation
    def calculate_checksum(self, exclude_patterns: List[str] = None) -> str:
        """Calculate checksum of entire object using streaming"""
        exclude_patterns = exclude_patterns or ["lock.json", ".write_lock"]
        checksums = []
        
        # Walk through all files (no lock needed for reading our own files)
        for file_path in sorted(self.path.rglob("*")):
            if file_path.is_file():
                # Skip excluded files
                if any(pattern in str(file_path) for pattern in exclude_patterns):
                    continue
                
                # Calculate file hash using streaming
                file_hash = self.calculate_file_hash(file_path)
                checksums.append(file_hash)
        
        combined = "".join(checksums)
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def _calculate_checksum_locked(self, exclude_patterns: List[str] = None) -> str:
        """Internal version of calculate_checksum that assumes we already have a lock"""
        exclude_patterns = exclude_patterns or ["lock.json", ".write_lock"]
        checksums = []
        
        # Walk through all files (caller must ensure proper locking)
        for file_path in sorted(self.path.rglob("*")):
            if file_path.is_file():
                # Skip excluded files
                if any(pattern in str(file_path) for pattern in exclude_patterns):
                    continue
                
                # Calculate file hash using streaming
                file_hash = self.calculate_file_hash(file_path)
                checksums.append(file_hash)
        
        combined = "".join(checksums)
        return hashlib.sha256(combined.encode()).hexdigest()
    
    # Atomic lock operations
    def lock(self, **kwargs):
        """Create a lock file atomically"""
        with self.exclusive_access():
            lock_data = {
                "checksum": self._calculate_checksum_locked(),  # Use internal version
                "locked_at": datetime.now().isoformat(),
                "schema_version": self.schema_version,
                **kwargs
            }
            
            # Write atomically
            with tempfile.NamedTemporaryFile(mode='w', dir=self.path,
                                           delete=False, suffix='.tmp') as tmp:
                json.dump(lock_data, tmp, indent=2)
                tmp_path = tmp.name
            
            os.replace(tmp_path, self.lock_path)
    
    def unlock(self):
        """Remove lock file atomically"""
        with self.exclusive_access():
            if self.lock_path.exists():
                self.lock_path.unlink()
    
    def is_locked(self) -> bool:
        """Check if object is locked"""
        return self.lock_path.exists()
    
    def get_lock_info(self) -> Optional[Dict[str, Any]]:
        """Get lock information"""
        with self.shared_access():
            return self._get_lock_info_no_lock()
    
    def _get_lock_info_no_lock(self) -> Optional[Dict[str, Any]]:
        """Internal method to get lock info without acquiring a lock"""
        if not self.lock_path.exists():
            return None
        with open(self.lock_path, 'r') as f:
            return json.load(f)
    
    def validate_checksum(self) -> bool:
        """Validate object integrity against lock checksum"""
        # Don't acquire a lock here - let the caller handle locking
        lock_info = self._get_lock_info_no_lock()
        if not lock_info:
            return False
        
        current_checksum = self.calculate_checksum()
        return current_checksum == lock_info.get("checksum")
    
    # Safe JSON operations
    def write_json(self, filename: str, data: Any) -> Path:
        """Write JSON data file atomically"""
        content = json.dumps(data, indent=2).encode()
        return self.write_data_file(filename, content)
    
    def read_json(self, filename: str) -> Optional[Any]:
        """Read JSON data file safely"""
        content = self.read_data_file(filename)
        if content:
            return json.loads(content)
        return None
    
    # Properties
    @property
    def exists(self) -> bool:
        """Check if object exists on disk"""
        return self.metadata_path.exists()
    
    @property
    def created_at(self) -> Optional[str]:
        """Get creation timestamp"""
        if self.metadata_path.exists():
            return datetime.fromtimestamp(self.metadata_path.stat().st_ctime).isoformat()
        return None
    
    @property
    def modified_at(self) -> Optional[str]:
        """Get modification timestamp"""
        return self.get_metadata().get("_updated_at")