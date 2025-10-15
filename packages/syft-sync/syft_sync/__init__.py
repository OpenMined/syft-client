"""
Syft Sync - A file synchronization system with append-only logging
"""

__version__ = "0.1.0"

from .watchers.syft_append_only import SyftWatcher
from .receiver.log_receiver import LogReceiver
from .receiver.syft_log_receiver import SyftLogReceiver
from .receiver.multi_log_receiver import SyftReceiver
from .core.base import BaseWatcher
from .core.events import FileEvent, EventType

__all__ = [
    "SyftWatcher",
    "LogReceiver",
    "SyftLogReceiver",
    "SyftReceiver",
    "BaseWatcher", 
    "FileEvent",
    "EventType",
]