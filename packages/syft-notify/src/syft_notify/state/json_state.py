import fcntl
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

from syft_notify.core.base import StateManager


class JsonStateManager(StateManager):
    def __init__(self, state_file: Path):
        self.state_file = Path(state_file).expanduser()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file = self.state_file.with_suffix(".lock")
        self.notified_jobs: dict[str, list[str]] = self._load()

        if not self.state_file.exists():
            self._save()

    @contextmanager
    def _file_lock(self):
        self._lock_file.touch(exist_ok=True)
        with open(self._lock_file, "r") as lock_handle:
            try:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def _load(self) -> dict[str, list[str]]:
        if not self.state_file.exists():
            return {}

        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)
                return data.get("notified_jobs", {})
        except (json.JSONDecodeError, OSError, IOError):
            return {}

    def _load_all(self) -> dict:
        if not self.state_file.exists():
            return {"notified_jobs": {}}

        try:
            with open(self.state_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError, IOError):
            return {"notified_jobs": {}}

    def _save(self):
        all_data = self._load_all()
        all_data["notified_jobs"] = self.notified_jobs

        with open(self.state_file, "w") as f:
            json.dump(all_data, f, indent=2)

        self.state_file.chmod(0o600)

    def was_notified(self, entity_id: str, event_type: str) -> bool:
        self.notified_jobs = self._load()
        return event_type in self.notified_jobs.get(entity_id, [])

    def mark_notified(self, entity_id: str, event_type: str) -> None:
        with self._file_lock():
            self.notified_jobs = self._load()

            if entity_id not in self.notified_jobs:
                self.notified_jobs[entity_id] = []

            if event_type not in self.notified_jobs[entity_id]:
                self.notified_jobs[entity_id].append(event_type)

            self._save()

    def get_data(self, key: str, default: Optional[Any] = None) -> Any:
        all_data = self._load_all()
        return all_data.get(key, default)

    def set_data(self, key: str, value: Any) -> None:
        with self._file_lock():
            all_data = self._load_all()
            all_data[key] = value

            with open(self.state_file, "w") as f:
                json.dump(all_data, f, indent=2)

            self.state_file.chmod(0o600)
