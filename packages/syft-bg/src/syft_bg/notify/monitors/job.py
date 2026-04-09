"""Job monitor for detecting new jobs and status changes."""

import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import yaml

from syft_bg.common.monitor import Monitor
from syft_bg.common.state import JsonStateManager
from syft_bg.notify.handlers.job import JobHandler

if TYPE_CHECKING:
    from syft_bg.sync.snapshot_reader import SnapshotReader


class JobMonitor(Monitor):
    """Monitors for new jobs and job status changes via local filesystem."""

    def __init__(
        self,
        syftbox_root: Path,
        do_email: str,
        handler: JobHandler,
        state: JsonStateManager,
        snapshot_reader: Optional["SnapshotReader"] = None,
    ):
        super().__init__()
        self.syftbox_root = Path(syftbox_root).expanduser()
        self.do_email = do_email
        self.handler = handler
        self.state = state
        self.job_dir = self.syftbox_root / do_email / "app_data" / "job"
        self.snapshot_reader = snapshot_reader
        self._startup_time = time.time()
        self._is_fresh_state = self.state.is_empty()

    def _check_all_entities(self):
        self._check_local_for_status_changes()

    def _check_local_for_status_changes(self):
        inbox_dir = self.job_dir / "inbox"
        if not inbox_dir.exists():
            return

        for ds_dir in inbox_dir.iterdir():
            if not ds_dir.is_dir():
                continue
            ds_email = ds_dir.name
            for job_path in ds_dir.iterdir():
                if not job_path.is_dir():
                    continue
                try:
                    self._check_job_status(job_path, ds_email)
                except Exception as e:
                    print(f"[JobMonitor] Error checking job {job_path.name}: {e}")

    def _check_job_status(self, job_path: Path, ds_email: str):
        config = self._load_job_config(job_path)
        if not config:
            return

        job_name = config.get("name", job_path.name)

        # Skip old jobs on fresh state (avoid spamming about pre-existing jobs)
        if self._is_fresh_state:
            config_file = job_path / "config.yaml"
            if config_file.exists():
                job_created = config_file.stat().st_mtime
                if job_created < self._startup_time:
                    return

        if not self.state.was_notified(job_name, "new"):
            success = self.handler.on_new_job(self.do_email, job_name, ds_email)
            if success:
                print(f"[JobMonitor] Sent new job notification: {job_name}")

        review_state = self._load_review_state(job_path.name, ds_email)
        if not review_state:
            return

        if review_state.get("approved_at"):
            success = self.handler.on_job_approved(ds_email, job_name)
            if success:
                print(f"[JobMonitor] Sent job approved notification: {job_name}")

        if review_state.get("completed_at"):
            success = self.handler.on_job_executed(ds_email, job_name)
            if success:
                print(f"[JobMonitor] Sent job executed notification: {job_name}")

    def _load_review_state(self, job_name: str, ds_email: str) -> Optional[dict]:
        state_file = self.job_dir / "review" / ds_email / job_name / "state.yaml"
        if not state_file.exists():
            return None
        try:
            with open(state_file, "r") as f:
                return yaml.safe_load(f)
        except (yaml.YAMLError, OSError) as e:
            print(f"[JobMonitor] Error reading review state {state_file}: {e}")
            return None

    def _load_job_config(self, job_path: Path) -> Optional[dict]:
        config_file = job_path / "config.yaml"
        if not config_file.exists():
            return None

        try:
            with open(config_file, "r") as f:
                return yaml.safe_load(f)
        except (yaml.YAMLError, OSError, IOError) as e:
            print(f"[JobMonitor] Error reading job config {config_file}: {e}")
            return None
