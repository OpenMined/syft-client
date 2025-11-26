"""
JSON-based state tracking to prevent duplicate notifications.
"""

import json
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
        self.notified_jobs: Dict[str, List[str]] = self._load()

        if not self.state_file.exists():
            self._save()

    def _load(self) -> Dict[str, List[str]]:
        """Load state from JSON file"""
        if not self.state_file.exists():
            return {}

        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)
                return data.get("notified_jobs", {})
        except Exception:
            return {}

    def _load_all(self) -> Dict:
        """Load complete state data from JSON file"""
        if not self.state_file.exists():
            return {"notified_jobs": {}}

        try:
            with open(self.state_file, "r") as f:
                return json.load(f)
        except Exception:
            return {"notified_jobs": {}}

    def _save(self):
        """Save state to JSON file"""
        # Load all data first to preserve custom data
        all_data = self._load_all()
        all_data["notified_jobs"] = self.notified_jobs

        with open(self.state_file, "w") as f:
            json.dump(all_data, f, indent=2)

        self.state_file.chmod(0o600)

    def was_notified(self, job_id: str, notification_type: str) -> bool:
        """Check if job was notified for specific type"""
        return notification_type in self.notified_jobs.get(job_id, [])

    def mark_notified(self, job_id: str, notification_type: str):
        """Mark job as notified for specific type"""
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
        all_data = self._load_all()
        all_data[key] = value

        with open(self.state_file, "w") as f:
            json.dump(all_data, f, indent=2)

        self.state_file.chmod(0o600)
