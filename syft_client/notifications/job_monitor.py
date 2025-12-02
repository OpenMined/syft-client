"""
Job Monitor: Detects and notifies about job events in SyftBox.
"""

import yaml
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING

try:
    from .base import Monitor, NotificationSender, StateManager
except ImportError:
    from notifications_base import Monitor, NotificationSender, StateManager

if TYPE_CHECKING:
    from syft_client.sync.syftbox_manager import SyftboxManager


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
        # TODO: Add logging for monitoring activity
        # logger.debug(f"Checking job directory: {self.job_dir}")
        if not self.job_dir.exists():
            return

        for job_path in self.job_dir.iterdir():
            if not job_path.is_dir():
                continue
            try:
                self._check_job(job_path)
            except Exception:
                # TODO: Add logging for error tracking
                # except Exception as e:
                #     logger.error(f"Error checking job {job_path}: {e}")
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

        # Default paths for package-managed files
        DEFAULT_NOTIFICATION_DIR = Path.home() / ".syft-notifications"
        DEFAULT_TOKEN_FILE = DEFAULT_NOTIFICATION_DIR / "gmail_token.json"
        DEFAULT_STATE_FILE = DEFAULT_NOTIFICATION_DIR / "state.json"

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # Only business config is required from user
        required_keys = ["syftbox_root", "do_email"]
        missing = [k for k in required_keys if k not in config]
        if missing:
            raise ValueError(
                f"Configuration missing required keys: {missing}\n"
                f"Config file: {config_path}"
            )

        # Use defaults for token_file and state_file if not provided
        token_path = (
            Path(config["token_file"]).expanduser()
            if "token_file" in config
            else DEFAULT_TOKEN_FILE
        )
        state_path = (
            Path(config["state_file"]).expanduser()
            if "state_file" in config
            else DEFAULT_STATE_FILE
        )

        from .gmail_auth import GmailAuth

        auth = GmailAuth()
        credentials = auth.load_credentials(token_path)

        from .gmail_sender import GmailSender

        # email_format: "html" (default), "text", or "both"
        email_format = config.get("email_format", "html")
        use_html = email_format in ["html", "both"]
        sender = GmailSender(credentials, use_html=use_html)

        from .json_state_manager import JsonStateManager

        state = JsonStateManager(state_path)

        return cls(
            syftbox_root=Path(config["syftbox_root"]),
            do_email=config["do_email"],
            sender=sender,
            state=state,
            config=config,
        )

    @classmethod
    def from_client(
        cls,
        client: "SyftboxManager",
        gmail_token_path: Optional[str] = None,
        notifications: bool = True,
    ):
        """
        Factory method: create monitor from syft-client.

        This is the recommended way to create a JobMonitor when working
        in a notebook with an existing client.

        Args:
            client: SyftboxManager from sc.login_do()
            gmail_token_path: Path to Gmail token (default: ~/.syft-notifications/gmail_token.json)
            notifications: Enable/disable notifications (default True)

        Returns:
            Configured JobMonitor instance

        Example:
            client_do = sc.login_do(email=email_do, token_path=token_path_do)
            monitor = JobMonitor.from_client(client_do)
            monitor.start(interval=5)
        """
        if not client.is_do:
            raise ValueError(
                "JobMonitor should only run on Data Owner (DO) side. "
                "Use sc.login_do() instead of sc.login()."
            )

        # Default paths
        DEFAULT_NOTIFICATION_DIR = Path.home() / ".syft-notifications"
        DEFAULT_TOKEN_FILE = DEFAULT_NOTIFICATION_DIR / "gmail_token.json"
        DEFAULT_STATE_FILE = DEFAULT_NOTIFICATION_DIR / "state.json"

        token_path = (
            Path(gmail_token_path).expanduser()
            if gmail_token_path
            else DEFAULT_TOKEN_FILE
        )

        if not token_path.exists():
            raise FileNotFoundError(
                f"Gmail token not found at: {token_path}\n\n"
                "Run OAuth setup first:\n"
                "  from syft_client.notifications import GmailAuth\n"
                "  auth = GmailAuth()\n"
                "  creds = auth.setup_auth('path/to/credentials.json')\n"
                "  # Save token to ~/.syft-notifications/gmail_token.json"
            )

        from .gmail_auth import GmailAuth
        from .gmail_sender import GmailSender
        from .json_state_manager import JsonStateManager

        auth = GmailAuth()
        credentials = auth.load_credentials(token_path)
        sender = GmailSender(credentials, use_html=True)
        state = JsonStateManager(DEFAULT_STATE_FILE)

        config = {
            "notify_on_new_job": notifications,
            "notify_on_approved": notifications,
            "notify_on_executed": notifications,
        }

        return cls(
            syftbox_root=client.syftbox_folder,
            do_email=client.email,
            sender=sender,
            state=state,
            config=config,
        )
