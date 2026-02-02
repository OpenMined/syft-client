from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Optional

from syft_approve.core.config import ApproveConfig, get_default_paths
from syft_approve.monitors import JobMonitor, PeerMonitor
from syft_approve.state import JsonStateManager

if TYPE_CHECKING:
    from syft_client.sync.syftbox_manager import SyftboxManager

MonitorType = Literal["jobs", "peers"]


class ApprovalOrchestrator:
    def __init__(
        self,
        client: SyftboxManager,
        config: ApproveConfig,
    ):
        self.client = client
        self.config = config

        # Initialize state manager to track approved jobs/peers
        paths = get_default_paths()
        self._state = JsonStateManager(paths.state)

        self._job_monitor: Optional[JobMonitor] = None
        self._peer_monitor: Optional[PeerMonitor] = None
        self._threads: list[threading.Thread] = []
        self._stop_event = threading.Event()

        self._init_monitors()

    def _init_monitors(self):
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

    @classmethod
    def from_client(
        cls,
        client: SyftboxManager,
        interval: int = 5,
    ) -> ApprovalOrchestrator:
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
        config = ApproveConfig.load(Path(config_path) if config_path else None)

        if not config.do_email:
            raise ValueError("Config missing 'do_email' field")
        if not config.syftbox_root:
            raise ValueError("Config missing 'syftbox_root' field")

        if interval is not None:
            config.interval = interval

        paths = get_default_paths()
        token_path = config.drive_token_path or paths.drive_token

        from syft_client.sync.syftbox_manager import SyftboxManager
        from syft_client.sync.utils.syftbox_utils import check_env
        from syft_client.sync.environments.environment import Environment

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

    def check(self, monitor_type: Optional[MonitorType] = None) -> None:
        if monitor_type is None or monitor_type == "jobs":
            if self._job_monitor:
                self._job_monitor._check_all_entities()

        if monitor_type is None or monitor_type == "peers":
            if self._peer_monitor:
                self._peer_monitor._check_all_entities()

    def start(self, monitor_type: Optional[MonitorType] = None) -> ApprovalOrchestrator:
        self._stop_event.clear()

        if monitor_type is None or monitor_type == "jobs":
            if self._job_monitor:
                thread = self._job_monitor.start(interval=self.config.interval)
                self._threads.append(thread)

        if monitor_type is None or monitor_type == "peers":
            if self._peer_monitor:
                thread = self._peer_monitor.start(interval=self.config.interval)
                self._threads.append(thread)

        return self

    def stop(self) -> None:
        if self._job_monitor:
            self._job_monitor.stop()
        if self._peer_monitor:
            self._peer_monitor.stop()
        self._threads.clear()

    @property
    def is_running(self) -> bool:
        return any(t.is_alive() for t in self._threads)

    def run(self, monitor_type: Optional[MonitorType] = None) -> None:
        self._stop_event.clear()

        print("🔐 Starting approval daemon...")
        print(f"   DO: {self.config.do_email}")
        print(f"   SyftBox: {self.config.syftbox_root}")
        print(f"   Interval: {self.config.interval}s")
        print(f"   Jobs: {'enabled' if self.config.jobs.enabled else 'disabled'}")
        print(f"   Peers: {'enabled' if self.config.peers.enabled else 'disabled'}")
        print()

        try:
            while not self._stop_event.is_set():
                if monitor_type is None or monitor_type == "jobs":
                    if self._job_monitor:
                        try:
                            self._job_monitor._check_all_entities()
                        except Exception as e:
                            print(f"⚠️  JobMonitor error: {e}")

                if monitor_type is None or monitor_type == "peers":
                    if self._peer_monitor:
                        try:
                            self._peer_monitor._check_all_entities()
                        except Exception as e:
                            print(f"⚠️  PeerMonitor error: {e}")

                self._stop_event.wait(self.config.interval)

        except KeyboardInterrupt:
            print("\n⏹️  Shutting down...")

        self._stop_event.set()
        print("✅ Approval daemon stopped")
