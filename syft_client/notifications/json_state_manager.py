"""
JSON-based state tracking to prevent duplicate notifications.
"""

import fcntl
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List

try:
    from .base import StateManager
except ImportError:
    from notifications_base import StateManager


class JsonStateManager(StateManager):
    def __init__(self, state_file: Path):
        self.state_file = Path(state_file).expanduser()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file = self.state_file.with_suffix(".lock")
        self.notified_jobs: Dict[str, List[str]] = self._load()

        if not self.state_file.exists():
            self._save()

    @contextmanager
    def _file_lock(self):
        """Context manager for file locking to prevent race conditions."""
        self._lock_file.touch(exist_ok=True)
        with open(self._lock_file, "r") as lock_handle:
            try:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def _load(self) -> Dict[str, List[str]]:
        """Load state from JSON file"""
        if not self.state_file.exists():
            return {}

        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)
                return data.get("notified_jobs", {})
        except (json.JSONDecodeError, OSError, IOError) as e:
            print(f"⚠️  StateManager: Error loading state file: {e}")
            return {}

    def _load_all(self) -> Dict:
        """Load complete state data from JSON file"""
        if not self.state_file.exists():
            return {"notified_jobs": {}}

        try:
            with open(self.state_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError, IOError) as e:
            print(f"⚠️  StateManager: Error loading state file: {e}")
            return {"notified_jobs": {}}

    def _save(self):
        """Save state to JSON file (call within _file_lock context)."""
        # Load all data first to preserve custom data
        all_data = self._load_all()
        all_data["notified_jobs"] = self.notified_jobs

        with open(self.state_file, "w") as f:
            json.dump(all_data, f, indent=2)

        self.state_file.chmod(0o600)

    def was_notified(self, job_id: str, notification_type: str) -> bool:
        """Check if job was notified for specific type"""
        # Reload from disk to catch external state changes
        self.notified_jobs = self._load()
        return notification_type in self.notified_jobs.get(job_id, [])

    def mark_notified(self, job_id: str, notification_type: str):
        """Mark job as notified for specific type"""
        with self._file_lock():
            # Reload from disk to catch external state changes
            self.notified_jobs = self._load()

            if job_id not in self.notified_jobs:
                self.notified_jobs[job_id] = []

            if notification_type not in self.notified_jobs[job_id]:
                self.notified_jobs[job_id].append(notification_type)

            self._save()

    def get_data(self, key: str, default=None):
        """Get arbitrary data from state storage"""
        all_data = self._load_all()
        return all_data.get(key, default)

    def set_data(self, key: str, value):
        """Set arbitrary data in state storage"""
        with self._file_lock():
            all_data = self._load_all()
            all_data[key] = value

            with open(self.state_file, "w") as f:
                json.dump(all_data, f, indent=2)

            self.state_file.chmod(0o600)
