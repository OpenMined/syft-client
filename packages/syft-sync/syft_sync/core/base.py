"""
Base watcher class for all syft watchers
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List, Dict, Any, Set
import logging
from datetime import datetime

from .events import FileEvent, EventHandler


logger = logging.getLogger(__name__)


class BaseWatcher(ABC):
    """Abstract base class for all watchers"""
    
    def __init__(
        self,
        watch_path: Path,
        exclude_patterns: Optional[List[str]] = None,
        event_handler: Optional[EventHandler] = None,
        verbose: bool = False
    ):
        """
        Initialize base watcher
        
        Args:
            watch_path: Directory to watch
            exclude_patterns: Patterns to exclude from watching
            event_handler: Custom event handler
            verbose: Enable verbose logging
        """
        self.watch_path = Path(watch_path).absolute()
        self.exclude_patterns = exclude_patterns or [
            '.*', '*.tmp', '*.swp', '*.DS_Store', '*~', '*.lock', 
            '__pycache__', '*.pyc', '*.log', '.git'
        ]
        self.event_handler = event_handler or EventHandler()
        self.verbose = verbose
        self.is_running = False
        self._tracked_files: Set[Path] = set()
        self._start_time = datetime.now()
        
        # Statistics
        self.stats = {
            'files_created': 0,
            'files_modified': 0,
            'files_deleted': 0,
            'files_moved': 0,
            'directories_created': 0,
            'directories_deleted': 0,
            'start_time': self._start_time
        }
        
        if not self.watch_path.exists():
            raise ValueError(f"Watch path does not exist: {self.watch_path}")
        
        if verbose:
            logging.basicConfig(level=logging.DEBUG)
            logger.info(f"Initialized watcher for: {self.watch_path}")
    
    @abstractmethod
    def start(self):
        """Start watching for file changes"""
        pass
    
    @abstractmethod
    def stop(self):
        """Stop watching for file changes"""
        pass
    
    @abstractmethod
    def process_event(self, event: FileEvent):
        """Process a file system event"""
        pass
    
    def should_process(self, path: Path) -> bool:
        """Check if file/directory should be processed"""
        path_str = str(path)
        path_parts = path_str.split('/')
        
        for part in path_parts:
            for pattern in self.exclude_patterns:
                if pattern.startswith('*') and part.endswith(pattern[1:]):
                    return False
                elif pattern.endswith('*') and part.startswith(pattern[:-1]):
                    return False
                elif part == pattern:
                    return False
        
        return True
    
    def update_stats(self, event: FileEvent):
        """Update statistics based on event"""
        if event.is_directory:
            if event.event_type.name.endswith('CREATED'):
                self.stats['directories_created'] += 1
            elif event.event_type.name.endswith('DELETED'):
                self.stats['directories_deleted'] += 1
        else:
            if event.event_type.name.endswith('CREATED'):
                self.stats['files_created'] += 1
            elif event.event_type.name.endswith('MODIFIED'):
                self.stats['files_modified'] += 1
            elif event.event_type.name.endswith('DELETED'):
                self.stats['files_deleted'] += 1
            elif event.event_type.name.endswith('MOVED'):
                self.stats['files_moved'] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        runtime = datetime.now() - self._start_time
        return {
            **self.stats,
            'runtime': str(runtime),
            'tracked_files': len(self._tracked_files)
        }
    
    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()
        return False