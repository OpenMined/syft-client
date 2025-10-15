"""
Observer integration with watchdog library
"""
import time
from pathlib import Path
from typing import Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from .events import FileEvent, EventType
from .base import BaseWatcher


class WatchdogHandler(FileSystemEventHandler):
    """Adapter between watchdog events and syft events"""
    
    def __init__(self, watcher: BaseWatcher):
        super().__init__()
        self.watcher = watcher
    
    def _convert_event(self, event: FileSystemEvent) -> Optional[FileEvent]:
        """Convert watchdog event to syft FileEvent"""
        src_path = Path(event.src_path)
        
        if not self.watcher.should_process(src_path):
            return None
        
        # Map watchdog event types to our EventType
        if event.event_type == 'created':
            event_type = EventType.DIRECTORY_CREATED if event.is_directory else EventType.FILE_CREATED
        elif event.event_type == 'modified':
            event_type = EventType.DIRECTORY_MODIFIED if event.is_directory else EventType.FILE_MODIFIED
        elif event.event_type == 'deleted':
            event_type = EventType.DIRECTORY_DELETED if event.is_directory else EventType.FILE_DELETED
        elif event.event_type == 'moved':
            event_type = EventType.DIRECTORY_MOVED if event.is_directory else EventType.FILE_MOVED
        else:
            return None
        
        # Create FileEvent
        dest_path = Path(event.dest_path) if hasattr(event, 'dest_path') else None
        
        # Get file size if it's a file and exists
        size = None
        if not event.is_directory and src_path.exists():
            try:
                size = src_path.stat().st_size
            except:
                pass
        
        return FileEvent(
            event_type=event_type,
            src_path=src_path,
            dest_path=dest_path,
            size=size
        )
    
    def on_any_event(self, event: FileSystemEvent):
        """Handle any file system event"""
        file_event = self._convert_event(event)
        if file_event:
            self.watcher.process_event(file_event)
            self.watcher.update_stats(file_event)
            
            # Call appropriate event handler method
            handler = self.watcher.event_handler
            handler.on_any_event(file_event)
            
            if file_event.event_type == EventType.FILE_CREATED:
                handler.on_file_created(file_event)
            elif file_event.event_type == EventType.FILE_MODIFIED:
                handler.on_file_modified(file_event)
            elif file_event.event_type == EventType.FILE_DELETED:
                handler.on_file_deleted(file_event)
            elif file_event.event_type == EventType.FILE_MOVED:
                handler.on_file_moved(file_event)
            elif file_event.event_type == EventType.DIRECTORY_CREATED:
                handler.on_directory_created(file_event)
            elif file_event.event_type == EventType.DIRECTORY_DELETED:
                handler.on_directory_deleted(file_event)
            elif file_event.event_type == EventType.DIRECTORY_MODIFIED:
                handler.on_directory_modified(file_event)
            elif file_event.event_type == EventType.DIRECTORY_MOVED:
                handler.on_directory_moved(file_event)


class WatcherObserver:
    """Manages the watchdog observer"""
    
    def __init__(self, watcher: BaseWatcher):
        self.watcher = watcher
        self.observer = Observer()
        self.handler = WatchdogHandler(watcher)
    
    def start(self):
        """Start observing"""
        self.observer.schedule(
            self.handler,
            str(self.watcher.watch_path),
            recursive=True
        )
        self.observer.start()
        self.watcher.is_running = True
    
    def stop(self):
        """Stop observing"""
        self.observer.stop()
        self.observer.join()
        self.watcher.is_running = False
    
    def watch(self, duration: Optional[float] = None):
        """Watch for a specific duration"""
        self.start()
        try:
            if duration:
                time.sleep(duration)
            else:
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()