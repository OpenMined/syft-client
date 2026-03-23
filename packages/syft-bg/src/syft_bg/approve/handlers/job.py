"""Job approval handler."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional, Protocol

from syft_job.job import JobInfo

from syft_bg.approve.config import AutoApprovalsConfig
from syft_bg.approve.criteria import resolve_auto_approval

if TYPE_CHECKING:
    from syft_client.sync.syftbox_manager import SyftboxManager


class StateManager(Protocol):
    """Protocol for state management."""

    def mark_approved(self, job_name: str, submitted_by: str) -> None: ...
    def was_approved(self, job_name: str) -> bool: ...


class JobApprovalHandler:
    """Handles job approval logic."""

    def __init__(
        self,
        client: SyftboxManager,
        config: AutoApprovalsConfig,
        state: Optional[StateManager] = None,
        on_approve: Optional[Callable[[JobInfo], None]] = None,
        on_reject: Optional[Callable[[JobInfo, str], None]] = None,
        verbose: bool = True,
    ):
        self.client = client
        self.config = config
        self.state = state
        self.on_approve = on_approve
        self.on_reject = on_reject
        self.verbose = verbose

    def _get_approved_peers(self) -> list[str]:
        """Get list of approved peer emails."""
        self.client.load_peers()
        return [p.email for p in self.client.peer_manager.approved_peers]

    def check_and_approve(self) -> list[JobInfo]:
        """Check all jobs and approve those matching criteria."""
        if not self.config.enabled:
            return []

        approved_jobs = []

        for job in self.client.jobs:
            if self.state and self.state.was_approved(job.name):
                continue

            matches, reason = resolve_auto_approval(
                job=job,
                config=self.config,
            )

            if not matches:
                if job.status == "inbox":
                    if self.verbose:
                        print(f"Skipped: {job.name} ({reason})")
                    if self.on_reject:
                        self.on_reject(job, reason)
                continue

            try:
                job.approve()
                approved_jobs.append(job)

                if self.state:
                    self.state.mark_approved(job.name, job.submitted_by)

                if self.on_approve:
                    self.on_approve(job)

                if self.verbose:
                    print(f"Approved: {job.name} from {job.submitted_by}")

            except Exception as e:
                if self.verbose:
                    print(f"Failed to approve {job.name}: {e}")

        if approved_jobs:
            self.client.process_approved_jobs(stream_output=self.verbose)

        return approved_jobs
