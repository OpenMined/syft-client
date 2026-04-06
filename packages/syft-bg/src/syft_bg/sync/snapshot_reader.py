"""Reads sync snapshot from disk."""

import json
import time
from pathlib import Path
from typing import Optional

from syft_bg.sync.snapshot import SyncSnapshot


class SnapshotReader:
    def __init__(self, path: Path):
        self.path = Path(path).expanduser()

    def read(self) -> Optional[SyncSnapshot]:
        if not self.path.exists():
            return None
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            return SyncSnapshot.model_validate(data)
        except (json.JSONDecodeError, OSError, ValueError):
            return None

    def is_healthy(self, max_age_seconds: int = 60) -> bool:
        snapshot = self.read()
        if snapshot is None:
            return False
        return time.time() - snapshot.sync_time < max_age_seconds

    def wait_for_first_sync(self, timeout: float = 30) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.read() is not None:
                return True
            time.sleep(0.5)
        return False
