"""Orchestrator for email-based job approval service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from syft_bg.common.config import get_default_paths
from syft_bg.common.state import JsonStateManager
from syft_bg.email_approve.config import EmailApproveConfig
from syft_bg.email_approve.gmail_watch import GmailWatcher
from syft_bg.email_approve.handler import EmailApproveHandler
from syft_bg.email_approve.monitor import EmailApproveMonitor
from syft_bg.email_approve.pubsub_setup import (
    get_project_id_from_credentials,
    setup_pubsub,
)
from syft_bg.notify.gmail.auth import GmailAuth

if TYPE_CHECKING:
    from syft_client.sync.syftbox_manager import SyftboxManager


class EmailApproveOrchestrator:
    """Orchestrator for email-based job approval via Gmail push notifications."""

    def __init__(
        self,
        client: SyftboxManager,
        config: EmailApproveConfig,
    ):
        self.client = client
        self.config = config
        self._monitor: Optional[EmailApproveMonitor] = None
        self._initialized = False

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

        client = _create_client(config)
        return cls(client=client, config=config)

    def _init(self):
        """Initialize Gmail watcher, Pub/Sub, handler, and monitor."""
        if self._initialized:
            return

        paths = get_default_paths()
        config = self.config

        # Load Gmail credentials
        gmail_token_path = paths.gmail_token
        if not gmail_token_path.exists():
            raise FileNotFoundError(
                f"Gmail token not found: {gmail_token_path}\nRun 'syft-bg init' first."
            )

        auth = GmailAuth()
        credentials = auth.load_credentials(gmail_token_path)

        # Auto-detect project ID if needed
        if not config.gcp_project_id:
            config.gcp_project_id = get_project_id_from_credentials(paths.credentials)

        # Auto-create Pub/Sub resources if needed
        if not config.pubsub_topic or not config.pubsub_subscription:
            topic_path, sub_path = setup_pubsub(credentials, config.gcp_project_id)
            config.pubsub_topic = topic_path
            config.pubsub_subscription = sub_path
            config.save_pubsub_config()

        # Create components
        watcher = GmailWatcher(credentials)
        state = JsonStateManager(paths.email_approve_state)
        notify_state = JsonStateManager(paths.notify_state)

        handler = EmailApproveHandler(
            client=self.client,
            state=state,
            notify_state=notify_state,
            do_email=config.do_email,
        )

        self._monitor = EmailApproveMonitor(
            watcher=watcher,
            handler=handler,
            state=state,
            credentials=credentials,
            subscription_path=config.pubsub_subscription,
            topic_name=config.pubsub_topic,
            do_email=config.do_email,
        )

        self._initialized = True

    def run(self) -> None:
        """Run the email approval service (blocking)."""
        self._init()
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

    def check(self) -> None:
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


def _create_client(config: EmailApproveConfig) -> SyftboxManager:
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
