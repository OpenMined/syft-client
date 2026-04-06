"""Sync orchestrator — runs the sync loop and writes snapshots."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from syft_bg.common.config import get_default_paths
from syft_bg.sync.config import SyncConfig
from syft_bg.sync.snapshot import SyncSnapshot
from syft_bg.sync.snapshot_writer import SnapshotWriter

if TYPE_CHECKING:
    from syft_bg.sync.drive_inbox_scanner import DriveInboxScanner
    from syft_client.sync.syftbox_manager import SyftboxManager


class SyncOrchestrator:
    def __init__(
        self,
        client: SyftboxManager,
        inbox_scanner: Optional[DriveInboxScanner],
        snapshot_writer: SnapshotWriter,
        config: SyncConfig,
    ):
        self.client = client
        self.inbox_scanner = inbox_scanner
        self.snapshot_writer = snapshot_writer
        self.config = config
        self._stop_event = threading.Event()
        self._sync_count = 0

    @classmethod
    def from_config(cls, config: SyncConfig) -> SyncOrchestrator:
        if not config.do_email:
            raise ValueError("SyncConfig missing 'do_email'")
        if not config.syftbox_root:
            raise ValueError("SyncConfig missing 'syftbox_root'")

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

        inbox_scanner = _build_inbox_scanner(token_path, config.do_email)
        writer = SnapshotWriter(paths.sync_state)

        return cls(
            client=client,
            inbox_scanner=inbox_scanner,
            snapshot_writer=writer,
            config=config,
        )

    def run(self) -> None:
        self._print_startup_info()
        try:
            while not self._stop_event.is_set():
                self._sync_and_snapshot()
                self._stop_event.wait(self.config.interval)
        except KeyboardInterrupt:
            print("\nShutting down...")
        self._stop_event.set()

    def run_once(self) -> None:
        self._sync_and_snapshot()

    def stop(self) -> None:
        self._stop_event.set()

    def _sync_and_snapshot(self) -> None:
        start = time.time()
        sync_error = None

        try:
            self._sync_with_retry()
        except Exception as e:
            sync_error = str(e)

        snapshot = self._build_snapshot(start, sync_error)
        self.snapshot_writer.write(snapshot)

        duration_ms = snapshot.sync_duration_ms
        count = snapshot.sync_count
        if sync_error:
            print(
                f"[SyncOrchestrator] Cycle {count} failed in {duration_ms}ms: {sync_error}"
            )
        else:
            job_count = len(snapshot.job_names)
            peer_count = len(snapshot.approved_peer_emails)
            print(
                f"[SyncOrchestrator] Cycle {count} completed in {duration_ms}ms "
                f"({job_count} jobs, {peer_count} peers)"
            )

    def _sync_with_retry(self) -> None:
        for attempt in range(self.config.max_retries):
            try:
                self.client.sync()
                return
            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    raise
                wait = self.config.retry_backoff**attempt
                print(
                    f"[SyncOrchestrator] Retry {attempt + 1}/{self.config.max_retries}: {e}"
                )
                time.sleep(wait)

    def _build_snapshot(
        self, start_time: float, sync_error: Optional[str]
    ) -> SyncSnapshot:
        job_names = []
        approved_peers = []
        try:
            job_names = [j.name for j in self.client.job_client.jobs]
            approved_peers = [p.email for p in self.client.peer_manager.approved_peers]
        except Exception as e:
            print(f"[SyncOrchestrator] Error reading client state: {e}")

        inbox_messages = []
        drive_peer_emails: list[str] = []
        drive_approved_peers: list[str] = []
        if self.inbox_scanner:
            try:
                inbox_messages = self.inbox_scanner.scan_inbox_messages()
                drive_peer_emails = self.inbox_scanner.scan_peer_emails()
                drive_approved_peers = self.inbox_scanner.scan_approved_peers()
            except Exception as e:
                print(f"[SyncOrchestrator] Error scanning inbox: {e}")

        self._sync_count += 1

        return SyncSnapshot(
            sync_time=time.time(),
            sync_count=self._sync_count,
            sync_error=sync_error,
            sync_duration_ms=int((time.time() - start_time) * 1000),
            job_names=job_names,
            approved_peer_emails=approved_peers,
            inbox_messages=inbox_messages,
            drive_peer_emails=drive_peer_emails,
            drive_approved_peers=drive_approved_peers,
        )

    def _print_startup_info(self) -> None:
        print("Starting sync daemon...")
        print(f"  DO: {self.config.do_email}")
        print(f"  Interval: {self.config.interval}s")
        print(f"  Max retries: {self.config.max_retries}")
        print()


def _build_inbox_scanner(
    token_path: Optional[Path], do_email: str
) -> Optional[DriveInboxScanner]:
    try:
        from syft_bg.common.drive import create_drive_service, is_colab
        from syft_bg.sync.drive_inbox_scanner import DriveInboxScanner

        token = Path(token_path) if token_path else None
        if is_colab() or (token and token.exists()):
            drive_service = create_drive_service(token)
            if drive_service:
                return DriveInboxScanner(drive_service, do_email)
    except Exception as e:
        print(f"[SyncOrchestrator] Could not create inbox scanner: {e}")
    return None
