"""Job monitor for detecting new jobs and status changes."""

import time
from pathlib import Path
from typing import Optional

from syft_job.config import SyftJobConfig
from syft_job.models.config import JobSubmissionMetadata

from syft_bg.common.monitor import Monitor
from syft_bg.common.state import JsonStateManager
from syft_bg.notify.handlers.job import JobHandler


class JobMonitor(Monitor):
    """Monitors for new jobs and job status changes via local filesystem."""

    def __init__(
        self,
        syftbox_root: Path,
        do_email: str,
        handler: JobHandler,
        state: JsonStateManager,
    ):
        super().__init__()
        self.syftbox_root = Path(syftbox_root).expanduser()
        self.do_email = do_email
        self.handler = handler
        self.state = state
        self.job_config = SyftJobConfig.from_syftbox_folder(
            str(self.syftbox_root), do_email
        )
        self._startup_time = time.time()
        self._is_fresh_state = self.state.is_empty()

    def _check_all_entities(self):
        self.process_local_status_changes()

    def process_local_status_changes(self):
        inbox_dir = self.job_config.get_all_submissions_dir(self.do_email)
        if not inbox_dir.exists():
            return

        for ds_dir in inbox_dir.iterdir():
            if not ds_dir.is_dir():
                continue
            for job_path in ds_dir.iterdir():
                if not job_path.is_dir():
                    continue
                try:
                    self._maybe_process_job(job_path)
                except Exception as e:
                    print(f"[JobMonitor] Error checking job {job_path.name}: {e}")

    def _maybe_process_job(self, job_path: Path):
        metadata = self._load_job_metadata(job_path)
        if not metadata:
            return

        job_name = metadata.name
        ds_email = metadata.submitted_by

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

        if (job_path / "approved").exists():
            success = self.handler.on_job_approved(ds_email, job_name)
            if success:
                print(f"[JobMonitor] Sent job approved notification: {job_name}")

        if (job_path / "done").exists():
            success = self.handler.on_job_executed(ds_email, job_name)
            if success:
                print(f"[JobMonitor] Sent job executed notification: {job_name}")

    def _load_job_metadata(self, job_path: Path) -> Optional[JobSubmissionMetadata]:
        config_file = job_path / "config.yaml"
        if not config_file.exists():
            return None

        try:
            return JobSubmissionMetadata.load(config_file)
        except Exception as e:
            print(f"[JobMonitor] Error reading job config {config_file}: {e}")
            return None
