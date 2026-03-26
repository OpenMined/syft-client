"""Approval orchestrator for auto-approving jobs and peers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from syft_bg.approve.config import AutoApproveConfig
from syft_bg.approve.monitors.job import JobMonitor
from syft_bg.approve.monitors.peer import PeerMonitor
from syft_bg.common.config import get_default_paths
from syft_bg.common.orchestrator import BaseOrchestrator
from syft_bg.common.state import JsonStateManager

if TYPE_CHECKING:
    from syft_client.sync.syftbox_manager import SyftboxManager


class ApprovalOrchestrator(BaseOrchestrator):
    """Orchestrator for job and peer auto-approval service."""

    def __init__(
        self,
        client: SyftboxManager,
        config: AutoApproveConfig,
    ):
        super().__init__()
        self.client = client
        self.config = config
        self.interval = config.interval

        paths = get_default_paths()
        self._state = JsonStateManager(paths.approve_state)
        self._monitors_initialized = False

    @classmethod
    def from_client(
        cls,
        client: SyftboxManager,
        interval: int = 5,
    ) -> ApprovalOrchestrator:
        """Create orchestrator from a SyftboxManager client."""
        if not client.has_do_role:
            raise ValueError(
                "ApprovalOrchestrator should only run on Data Owner (DO) side."
            )

        config = AutoApproveConfig.load()
        config.do_email = client.email
        config.syftbox_root = client.syftbox_folder
        config.interval = interval

        return cls(client=client, config=config)

    @classmethod
    def from_config(
        cls,
        config_path: Optional[str] = None,
        interval: Optional[int] = None,
    ) -> ApprovalOrchestrator:
        """Create orchestrator from config file."""
        config = AutoApproveConfig.load(Path(config_path) if config_path else None)

        if not config.do_email:
            raise ValueError("Config missing 'do_email' field")
        if not config.syftbox_root:
            raise ValueError("Config missing 'syftbox_root' field")

        if interval is not None:
            config.interval = interval

        paths = get_default_paths()
        token_path = config.drive_token_path or paths.drive_token

        from syft_client.sync.environments.environment import Environment
        from syft_client.sync.syftbox_manager import SyftboxManager
        from syft_client.sync.utils.syftbox_utils import check_env

        env = check_env()
        if env == Environment.COLAB:
            client = SyftboxManager.for_colab(
                email=config.do_email,
                has_do_role=True,
            )
        else:
            client = SyftboxManager.for_jupyter(
                email=config.do_email,
                has_do_role=True,
                token_path=token_path,
            )

        return cls(client=client, config=config)

    def _build_reject_callback(self):
        """Build rejection callback that notifies DS via Gmail, if available."""
        paths = get_default_paths()
        gmail_token_path = paths.creds_dir / "gmail_token.json"

        if not gmail_token_path.exists():
            print(
                "[ApprovalOrchestrator] Gmail token not found, skipping DS rejection notifications"
            )
            return None

        try:
            from google.oauth2.credentials import Credentials

            from syft_bg.notify.gmail.sender import GmailSender
            from syft_bg.notify.handlers.job import JobHandler

            creds = Credentials.from_authorized_user_file(str(gmail_token_path))
            sender = GmailSender(creds)
            notify_state = JsonStateManager(paths.notify_state)
            notify_handler = JobHandler(
                sender=sender,
                state=notify_state,
                do_email=self.config.do_email or "",
            )

            def _on_reject(job, reason):
                notify_handler.on_job_rejected(
                    do_email=self.config.do_email or "",
                    job_name=job.name,
                    ds_email=job.submitted_by,
                    reason=reason,
                )

            return _on_reject
        except Exception as e:
            print(
                f"[ApprovalOrchestrator] Could not set up rejection notifications: {e}"
            )
            return None

    def _init_monitors(self):
        """Initialize job and peer monitors."""
        if self._monitors_initialized:
            return

        on_reject = None
        if self.config.auto_approvals.enabled:
            on_reject = self._build_reject_callback()
            self._job_monitor = JobMonitor(
                client=self.client,
                config=self.config.auto_approvals,
                state=self._state,
                on_reject=on_reject,
                verbose=True,
            )

        if self.config.peers.enabled:
            self._peer_monitor = PeerMonitor(
                client=self.client,
                config=self.config.peers,
                state=self._state,
                verbose=True,
            )

        self._monitors_initialized = True

    def _print_startup_info(self):
        """Print startup info for approval service."""
        print("Starting approval daemon...")
        print(f"  DO: {self.config.do_email}")
        print(f"  SyftBox: {self.config.syftbox_root}")
        print(f"  Interval: {self.config.interval}s")
        print(
            f"  Auto-approvals: {'enabled' if self.config.auto_approvals.enabled else 'disabled'}"
        )
        print(f"  Peers: {'enabled' if self.config.peers.enabled else 'disabled'}")
        print()
