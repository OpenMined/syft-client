"""Writes sync snapshot to disk with file locking."""

import fcntl
import json
from pathlib import Path

from syft_bg.sync.snapshot import SyncSnapshot


class SnapshotWriter:
    def __init__(self, path: Path):
        self.path = Path(path).expanduser()
        self._lock_file = self.path.with_suffix(".lock")

    def write(self, snapshot: SyncSnapshot) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file.touch(exist_ok=True)

        with open(self._lock_file, "r") as lock_handle:
            try:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
                with open(self.path, "w") as f:
                    json.dump(snapshot.model_dump(), f, indent=2)
                self.path.chmod(0o600)
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
