"""Configuration for the sync service."""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class SyncConfig(BaseModel):
    interval: int = 10
    max_retries: int = 3
    retry_backoff: float = 2.0
    do_email: Optional[str] = None
    syftbox_root: Optional[Path] = None
    drive_token_path: Optional[Path] = None
