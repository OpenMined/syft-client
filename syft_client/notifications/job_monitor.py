"""
Job Monitor: Detects and notifies about job events in SyftBox.
"""

import yaml
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from .base import Monitor, NotificationSender, StateManager
except ImportError:
    from notifications_base import Monitor, NotificationSender, StateManager


class JobMonitor(Monitor):
    """Monitor jobs in SyftBox for notification events"""

    def __init__(
        self,
        syftbox_root: Path,
        do_email: str,
        sender: NotificationSender,
        state: StateManager,
        config: Dict[str, Any],
    ):
        """
        Initialize Job Monitor.

        Args:
            syftbox_root: Path to SyftBox root directory
            do_email: Data Owner email address
            sender: Notification sender implementation
            state: State manager implementation
            config: Configuration dictionary with notification toggles
        """
        super().__init__(sender, state, config)
        self.syftbox_root = Path(syftbox_root).expanduser()
        self.do_email = do_email
        self.job_dir = self.syftbox_root / do_email / "app_data" / "job"

    def _check_all_entities(self):
        """Check all jobs for notification events"""
        if not self.job_dir.exists():
            return

        for job_path in self.job_dir.iterdir():
            if not job_path.is_dir():
                continue
            try:
                self._check_job(job_path)
            except Exception:
                pass

    def _check_job(self, job_path: Path):
        """Check single job for all notification events"""
        config = self._load_job_config(job_path)
        if not config:
            return

        job_name = config.get("name", job_path.name)
        ds_email = config.get("submitted_by")

        if not ds_email:
            return

        if self.config.get("notify_on_new_job", True):
            if not self.state.was_notified(job_name, "new"):
                if hasattr(self.sender, "notify_new_job"):
                    success = self.sender.notify_new_job(
                        self.do_email, job_name, ds_email
                    )
                else:
                    success = self.sender.send_notification(
                        self.do_email,
                        f"New Job: {job_name}",
                        f"New job from {ds_email}",
                    )

                if success:
                    self.state.mark_notified(job_name, "new")

        if self.config.get("notify_on_approved", True):
            if (job_path / "approved").exists():
                if not self.state.was_notified(job_name, "approved"):
                    if hasattr(self.sender, "notify_job_approved"):
                        success = self.sender.notify_job_approved(ds_email, job_name)
                    else:
                        success = self.sender.send_notification(
                            ds_email,
                            f"Job Approved: {job_name}",
                            "Your job has been approved",
                        )

                    if success:
                        self.state.mark_notified(job_name, "approved")

        if self.config.get("notify_on_executed", True):
            if (job_path / "done").exists():
                if not self.state.was_notified(job_name, "executed"):
                    if hasattr(self.sender, "notify_job_executed"):
                        success = self.sender.notify_job_executed(ds_email, job_name)
                    else:
                        success = self.sender.send_notification(
                            ds_email,
                            f"Job Completed: {job_name}",
                            "Your job has finished",
                        )

                    if success:
                        self.state.mark_notified(job_name, "executed")

    def _load_job_config(self, job_path: Path) -> Optional[Dict]:
        """Load job config.yaml"""
        config_file = job_path / "config.yaml"
        if not config_file.exists():
            return None

        try:
            with open(config_file, "r") as f:
                return yaml.safe_load(f)
        except Exception:
            return None

    @classmethod
    def from_config(cls, config_path: str):
        """
        Factory method: create monitor from YAML config file.

        Args:
            config_path: Path to configuration YAML file

        Returns:
            Configured JobMonitor instance
        """
        import yaml
        from pathlib import Path

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        from .gmail_auth import GmailAuth

        auth = GmailAuth()
        token_path = Path(config["token_file"]).expanduser()
        credentials = auth.load_credentials(token_path)

        from .gmail_sender import GmailSender

        sender = GmailSender(credentials)

        from .json_state_manager import JsonStateManager

        state_path = Path(config["state_file"]).expanduser()
        state = JsonStateManager(state_path)

        return cls(
            syftbox_root=Path(config["syftbox_root"]),
            do_email=config["do_email"],
            sender=sender,
            state=state,
            config=config,
        )
