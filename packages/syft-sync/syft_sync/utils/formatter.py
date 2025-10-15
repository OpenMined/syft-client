"""
Formatting utilities
"""
from datetime import datetime
from typing import Union


def format_size(size: int) -> str:
    """Format file size in human-readable format"""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"


def format_timestamp(timestamp: Union[str, datetime]) -> str:
    """Format timestamp in human-readable format"""
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp)
    
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")