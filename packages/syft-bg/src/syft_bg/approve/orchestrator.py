"""Approval orchestrator for auto-approving jobs and peers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from syft_bg.approve.config import ApproveConfig
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
        config: ApproveConfig,
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
        if not client.is_do:
            raise ValueError(
                "ApprovalOrchestrator should only run on Data Owner (DO) side."
            )

        config = ApproveConfig.load()
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
        config = ApproveConfig.load(Path(config_path) if config_path else None)

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
                only_datasite_owner=True,
            )
        else:
            client = SyftboxManager.for_jupyter(
                email=config.do_email,
                only_datasite_owner=True,
                token_path=token_path,
            )

        return cls(client=client, config=config)

    def _init_monitors(self):
        """Initialize job and peer monitors."""
        if self._monitors_initialized:
            return

        if self.config.jobs.enabled:
            self._job_monitor = JobMonitor(
                client=self.client,
                config=self.config.jobs,
                state=self._state,
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
        print(f"  Jobs: {'enabled' if self.config.jobs.enabled else 'disabled'}")
        print(f"  Peers: {'enabled' if self.config.peers.enabled else 'disabled'}")
        print()
