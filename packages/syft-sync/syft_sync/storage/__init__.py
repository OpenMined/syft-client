"""
Storage backends for syft-watcher
"""

from .log_storage import LogStorage
from .syft_storage import SyftLogStorage

__all__ = [
    "LogStorage",
    "SyftLogStorage",
]