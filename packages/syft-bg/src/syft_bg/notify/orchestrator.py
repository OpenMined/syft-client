"""Notification orchestrator for email notifications."""

from typing import Optional

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
        config: NotifyConfig,
        job_monitor: JobMonitor,
        peer_monitor: Optional[PeerMonitor] = None,
    ):
        super().__init__()
        self.config = config
        self._job_monitor = job_monitor
        self._peer_monitor: Optional[PeerMonitor] = peer_monitor

    def _init_monitors(self):
        """No-op: monitors are created in from_config."""
        pass

    def setup(self) -> None:
        """Verify Gmail credentials are valid."""
        self._job_monitor.handler.sender.verify()

    @classmethod
    def from_config(
        cls,
        config: NotifyConfig,
    ) -> "NotificationOrchestrator":
        """Create orchestrator from a NotifyConfig."""
        if not config.do_email:
            raise ValueError("Config missing 'do_email' field")
        if not config.syftbox_root:
            raise ValueError("Config missing 'syftbox_root' field")

        if not config.gmail_token_path or not config.gmail_token_path.exists():
            raise FileNotFoundError(
                f"Gmail token not found: {config.gmail_token_path}\n\n"
                "Run setup to configure Gmail authentication first."
            )
        credentials = GmailAuth().load_credentials(config.gmail_token_path)
        sender = GmailSender(credentials)

        state_manager = JsonStateManager(config.notify_state_path)

        job_handler = JobHandler(
            sender,
            state_manager,
            do_email=config.do_email,
            syftbox_root=config.syftbox_root,
        )
        peer_handler = PeerHandler(sender, state_manager)

        job_monitor = JobMonitor(
            syftbox_root=config.syftbox_root,
            do_email=config.do_email,
            handler=job_handler,
            state=state_manager,
        )

        sync_state = JsonStateManager(config.sync_state_path)

        peer_monitor = PeerMonitor(
            do_email=config.do_email,
            handler=peer_handler,
            state=state_manager,
            sync_state=sync_state,
        )

        return cls(
            config=config,
            job_monitor=job_monitor,
            peer_monitor=peer_monitor,
        )

    def notify_peer_granted(self, ds_email: str) -> bool:
        """Notify DS that their peer request was granted."""
        if self._peer_monitor:
            return self._peer_monitor.notify_peer_granted(ds_email)
        return False

    def _print_startup_info(self):
        """Print startup info for notify service."""
        print("Starting notification daemon...")
        print(f"  DO: {self.config.do_email}")
        print(f"  SyftBox: {self.config.syftbox_root}")
        print(f"  Interval: {self.config.interval}s")
        print()
