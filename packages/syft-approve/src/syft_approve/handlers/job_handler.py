from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional, Protocol

from syft_job.client import JobInfo

from syft_approve.core.config import JobApprovalConfig
from syft_approve.core.criteria import job_matches_criteria

if TYPE_CHECKING:
    from syft_client.sync.syftbox_manager import SyftboxManager


class StateManager(Protocol):
    def mark_approved(self, job_name: str, submitted_by: str) -> None: ...
    def was_approved(self, job_name: str) -> bool: ...


class JobApprovalHandler:
    def __init__(
        self,
        client: SyftboxManager,
        config: JobApprovalConfig,
        state: Optional[StateManager] = None,
        on_approve: Optional[Callable[[JobInfo], None]] = None,
        verbose: bool = True,
    ):
        self.client = client
        self.config = config
        self.state = state
        self.on_approve = on_approve
        self.verbose = verbose

    def _get_approved_peers(self) -> list[str]:
        self.client.load_peers()
        return [p.email for p in self.client.version_manager.approved_peers]

    def check_and_approve(self) -> list[JobInfo]:
        if not self.config.enabled:
            return []

        approved_peers = None
        if self.config.peers_only:
            approved_peers = self._get_approved_peers()

        approved_jobs = []

        for job in self.client.jobs:
            if self.state and self.state.was_approved(job.name):
                continue

            matches, reason = job_matches_criteria(
                job=job,
                config=self.config,
                approved_peers=approved_peers,
            )

            if not matches:
                if self.verbose and job.status == "inbox":
                    print(f"⏭️  Skipped: {job.name} ({reason})")
                continue

            try:
                job.approve()
                approved_jobs.append(job)

                if self.state:
                    self.state.mark_approved(job.name, job.submitted_by)

                if self.on_approve:
                    self.on_approve(job)

                if self.verbose:
                    print(f"✅ Approved: {job.name} from {job.submitted_by}")

            except Exception as e:
                if self.verbose:
                    print(f"❌ Failed to approve {job.name}: {e}")

        if approved_jobs:
            self.client.process_approved_jobs(stream_output=self.verbose)

        return approved_jobs
