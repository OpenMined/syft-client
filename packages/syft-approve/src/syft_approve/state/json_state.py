import fcntl
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class JsonStateManager:
    def __init__(self, state_file: Path):
        self.state_file = Path(state_file).expanduser()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file = self.state_file.with_suffix(".lock")

        if not self.state_file.exists():
            self._save_all({"approved_jobs": {}, "approved_peers": {}})

    @contextmanager
    def _file_lock(self):
        self._lock_file.touch(exist_ok=True)
        with open(self._lock_file, "r") as lock_handle:
            try:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def _load_all(self) -> dict:
        if not self.state_file.exists():
            return {"approved_jobs": {}, "approved_peers": {}}

        try:
            with open(self.state_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError, IOError):
            return {"approved_jobs": {}, "approved_peers": {}}

    def _save_all(self, data: dict):
        with open(self.state_file, "w") as f:
            json.dump(data, f, indent=2)

        self.state_file.chmod(0o600)

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # Job state methods
    def was_approved(self, job_name: str) -> bool:
        data = self._load_all()
        return job_name in data.get("approved_jobs", {})

    def mark_approved(self, job_name: str, submitted_by: str) -> None:
        with self._file_lock():
            data = self._load_all()

            if "approved_jobs" not in data:
                data["approved_jobs"] = {}

            data["approved_jobs"][job_name] = {
                "approved_at": self._now_iso(),
                "submitted_by": submitted_by,
            }

            self._save_all(data)

    def get_approved_jobs(self) -> dict:
        data = self._load_all()
        return data.get("approved_jobs", {})

    # Peer state methods
    def was_peer_approved(self, peer_email: str) -> bool:
        data = self._load_all()
        return f"peer_{peer_email}" in data.get("approved_peers", {})

    def mark_peer_approved(self, peer_email: str, domain: str) -> None:
        with self._file_lock():
            data = self._load_all()

            if "approved_peers" not in data:
                data["approved_peers"] = {}

            data["approved_peers"][f"peer_{peer_email}"] = {
                "approved_at": self._now_iso(),
                "domain": domain,
            }

            self._save_all(data)

    def get_approved_peers(self) -> dict:
        data = self._load_all()
        return data.get("approved_peers", {})

    # Generic data storage
    def get_data(self, key: str, default: Optional[Any] = None) -> Any:
        data = self._load_all()
        return data.get(key, default)

    def set_data(self, key: str, value: Any) -> None:
        with self._file_lock():
            data = self._load_all()
            data[key] = value
            self._save_all(data)
