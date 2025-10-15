"""
Event definitions for file system watching
"""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


class EventType(Enum):
    """Types of file system events"""
    FILE_CREATED = "file_created"
    FILE_MODIFIED = "file_modified"
    FILE_DELETED = "file_deleted"
    FILE_MOVED = "file_moved"
    DIRECTORY_CREATED = "directory_created"
    DIRECTORY_DELETED = "directory_deleted"
    DIRECTORY_MODIFIED = "directory_modified"
    DIRECTORY_MOVED = "directory_moved"


@dataclass
class FileEvent:
    """Represents a file system event"""
    event_type: EventType
    src_path: Path
    dest_path: Optional[Path] = None
    timestamp: datetime = None
    size: Optional[int] = None
    hash: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if isinstance(self.src_path, str):
            self.src_path = Path(self.src_path)
        if self.dest_path and isinstance(self.dest_path, str):
            self.dest_path = Path(self.dest_path)
    
    @property
    def is_directory(self) -> bool:
        """Check if event is for a directory"""
        return self.event_type in [
            EventType.DIRECTORY_CREATED,
            EventType.DIRECTORY_DELETED,
            EventType.DIRECTORY_MODIFIED,
            EventType.DIRECTORY_MOVED
        ]
    
    @property
    def is_move(self) -> bool:
        """Check if event is a move operation"""
        return self.event_type in [EventType.FILE_MOVED, EventType.DIRECTORY_MOVED]


class EventHandler:
    """Base class for handling file events"""
    
    def on_file_created(self, event: FileEvent):
        """Called when a file is created"""
        pass
    
    def on_file_modified(self, event: FileEvent):
        """Called when a file is modified"""
        pass
    
    def on_file_deleted(self, event: FileEvent):
        """Called when a file is deleted"""
        pass
    
    def on_file_moved(self, event: FileEvent):
        """Called when a file is moved"""
        pass
    
    def on_directory_created(self, event: FileEvent):
        """Called when a directory is created"""
        pass
    
    def on_directory_deleted(self, event: FileEvent):
        """Called when a directory is deleted"""
        pass
    
    def on_directory_modified(self, event: FileEvent):
        """Called when a directory is modified"""
        pass
    
    def on_directory_moved(self, event: FileEvent):
        """Called when a directory is moved"""
        pass
    
    def on_any_event(self, event: FileEvent):
        """Called for any event"""
        pass