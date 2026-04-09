"""Orchestrator for email-based job approval service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from syft_bg.common.config import get_default_paths
from syft_bg.common.state import JsonStateManager
from syft_bg.email_approve.config import EmailApproveConfig
from syft_bg.email_approve.gmail_watch import GmailWatcher
from syft_bg.email_approve.handler import EmailApproveHandler
from syft_bg.email_approve.monitor import EmailApproveMonitor
from syft_bg.email_approve.pubsub_setup import setup_pubsub
from syft_bg.notify.gmail.auth import GmailAuth

if TYPE_CHECKING:
    from syft_client.sync.syftbox_manager import SyftboxManager


class EmailApproveOrchestrator:
    """Orchestrator for email-based job approval via Gmail push notifications."""

    def __init__(
        self,
        client: SyftboxManager,
        config: EmailApproveConfig,
        monitor: Optional[EmailApproveMonitor] = None,
    ):
        self.syft_client = client
        self.config = config
        self._monitor: Optional[EmailApproveMonitor] = monitor

    @classmethod
    def from_config(
        cls,
        config: EmailApproveConfig,
    ) -> EmailApproveOrchestrator:
        """Create orchestrator from an EmailApproveConfig."""
        if not config.do_email:
            raise ValueError("Config missing 'do_email' field")
        if not config.syftbox_root:
            raise ValueError("Config missing 'syftbox_root' field")

        client = _create_syft_client(config)
        credentials = GmailAuth().load_credentials(config.gmail_token_path)

        watcher = GmailWatcher(credentials)
        state = JsonStateManager(config.email_approve_state_path)
        notify_state = JsonStateManager(config.notify_state_path)

        handler = EmailApproveHandler(
            client=client,
            state=state,
            notify_state=notify_state,
            do_email=config.do_email,
        )

        monitor = EmailApproveMonitor(
            watcher=watcher,
            handler=handler,
            state=state,
            credentials=credentials,
            subscription_path=config.pubsub_subscription,
            topic_name=config.pubsub_topic,
            do_email=config.do_email,
        )

        # Auto-create Pub/Sub resources if needed
        if not config.pubsub_topic or not config.pubsub_subscription:
            topic_path, sub_path = setup_pubsub(credentials, config.gcp_project_id)
            config.pubsub_topic = topic_path
            config.pubsub_subscription = sub_path
            config.save_pubsub_config()

        if not config.gmail_token_path.exists():
            raise FileNotFoundError(
                f"Gmail token not found: {config.gmail_token_path}\nRun 'syft-bg init' first."
            )

        return cls(client=client, config=config, monitor=monitor)

    def run_loop(self) -> None:
        """Run the email approval service (blocking)."""
        assert self._monitor is not None

        print("Starting email approval daemon...")
        print(f"  DO: {self.config.do_email}")
        print(f"  Topic: {self.config.pubsub_topic}")
        print(f"  Subscription: {self.config.pubsub_subscription}")
        print()

        thread = self._monitor.start()
        try:
            thread.join()
        except KeyboardInterrupt:
            print("\nShutting down...")
            self._monitor.stop()

    def run_once(self) -> None:
        """Run a single check (for --once mode). Not meaningful for push-based."""
        self._init()
        print(
            "[EmailApproveOrchestrator] Push-based service does not support "
            "--once. Use 'run' instead."
        )

    def stop(self) -> None:
        """Stop the service."""
        if self._monitor:
            self._monitor.stop()


def _create_syft_client(config: EmailApproveConfig) -> SyftboxManager:
    """Create a SyftboxManager client from config."""
    from syft_client.sync.environments.environment import Environment
    from syft_client.sync.syftbox_manager import SyftboxManager
    from syft_client.sync.utils.syftbox_utils import check_env

    paths = get_default_paths()
    env = check_env()
    if env == Environment.COLAB:
        return SyftboxManager.for_colab(
            email=config.do_email,
            has_do_role=True,
        )
    else:
        return SyftboxManager.for_jupyter(
            email=config.do_email,
            has_do_role=True,
            token_path=paths.drive_token,
        )
