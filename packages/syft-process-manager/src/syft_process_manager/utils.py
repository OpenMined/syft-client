import re
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
