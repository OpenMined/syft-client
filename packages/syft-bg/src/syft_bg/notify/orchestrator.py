"""Notification orchestrator for email notifications."""

from pathlib import Path
from typing import Optional

from syft_bg.common.drive import is_colab
from syft_bg.common.orchestrator import BaseOrchestrator
from syft_bg.common.state import JsonStateManager
from syft_bg.notify.config import NotifyConfig
from syft_bg.notify.gmail.auth import GmailAuth
from syft_bg.notify.gmail.sender import GmailSender
from syft_bg.notify.handlers.job import JobHandler
from syft_bg.notify.handlers.peer import PeerHandler
from syft_bg.notify.monitors.job import JobMonitor
from syft_bg.notify.monitors.peer import PeerMonitor


class NotificationOrchestrator(BaseOrchestrator):
    """Orchestrator for email notification service."""

    def __init__(
        self,
        do_email: str,
        syftbox_root: Path,
        drive_token_path: Optional[Path] = None,
        gmail_token_path: Optional[Path] = None,
        state_path: Optional[Path] = None,
        interval: int = 30,
    ):
        super().__init__()
        self.do_email = do_email
        self.syftbox_root = Path(syftbox_root).expanduser()
        self.drive_token_path = (
            Path(drive_token_path).expanduser() if drive_token_path else None
        )
        self.gmail_token_path = (
            Path(gmail_token_path).expanduser() if gmail_token_path else None
        )
        self.state_path = Path(state_path).expanduser() if state_path else None
        self.interval = interval
        self._monitors_initialized = False

    @classmethod
    def from_config(
        cls,
        config_path: Optional[str] = None,
        interval: Optional[int] = None,
    ) -> "NotificationOrchestrator":
        """Create orchestrator from config file."""
        from syft_bg.common.config import get_default_paths

        config = NotifyConfig.load(Path(config_path) if config_path else None)
        paths = get_default_paths()

        if not config.do_email:
            raise ValueError("Config missing 'email' field")
        if not config.syftbox_root:
            raise ValueError("Config missing 'syftbox_root' field")

        return cls(
            do_email=config.do_email,
            syftbox_root=config.syftbox_root,
            drive_token_path=config.drive_token_path or paths.drive_token,
            gmail_token_path=config.gmail_token_path or paths.gmail_token,
            state_path=paths.notify_state,
            interval=interval or config.interval,
        )

    def _init_monitors(self):
        """Initialize job and peer monitors."""
        if self._monitors_initialized:
            return

        if not self.gmail_token_path or not self.gmail_token_path.exists():
            raise FileNotFoundError(
                f"Gmail token not found: {self.gmail_token_path}\n\n"
                "Run setup to configure Gmail authentication first."
            )

        auth = GmailAuth()
        credentials = auth.load_credentials(self.gmail_token_path)
        sender = GmailSender(credentials)

        if self.state_path:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
        state = JsonStateManager(self.state_path)

        job_handler = JobHandler(sender, state)
        peer_handler = PeerHandler(sender, state)

        self._job_monitor = JobMonitor(
            syftbox_root=self.syftbox_root,
            do_email=self.do_email,
            handler=job_handler,
            state=state,
            drive_token_path=self.drive_token_path,
        )

        if is_colab() or (self.drive_token_path and self.drive_token_path.exists()):
            self._peer_monitor = PeerMonitor(
                do_email=self.do_email,
                drive_token_path=self.drive_token_path,
                handler=peer_handler,
                state=state,
            )

        self._monitors_initialized = True

    def notify_peer_granted(self, ds_email: str) -> bool:
        """Notify DS that their peer request was granted."""
        self._init_monitors()
        if self._peer_monitor:
            return self._peer_monitor.notify_peer_granted(ds_email)
        return False

    def _print_startup_info(self):
        """Print startup info for notify service."""
        print("Starting notification daemon...")
        print(f"  DO: {self.do_email}")
        print(f"  SyftBox: {self.syftbox_root}")
        print(f"  Interval: {self.interval}s")
        print()
