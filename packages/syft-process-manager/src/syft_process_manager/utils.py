import re
import socket
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def validate_process_name(name: Any) -> str:
    if not isinstance(name, str):
        raise ValueError("Name must be a string")
    if not name:
        raise ValueError("Name cannot be empty")
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        raise ValueError(
            "Name can only contain alphanumeric characters, hyphens, and underscores"
        )
    return name


def find_free_port() -> int:
    """
    Find a free port by letting the OS choose one
    avoids race conditions that can occur when manually checking for free ports
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))  # Port 0 = OS assigns a free port
        s.listen(1)
        port = s.getsockname()[1]
    return port
