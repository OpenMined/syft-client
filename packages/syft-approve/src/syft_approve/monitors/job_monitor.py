from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from syft_job.client import JobInfo

from syft_approve.handlers.job_handler import JobApprovalHandler, StateManager
from syft_approve.monitors.base import Monitor

if TYPE_CHECKING:
    from syft_approve.core.config import JobApprovalConfig
    from syft_client.sync.syftbox_manager import SyftboxManager


class JobMonitor(Monitor):
    def __init__(
        self,
        client: SyftboxManager,
        config: JobApprovalConfig,
        state: Optional[StateManager] = None,
        on_approve: Optional[Callable[[JobInfo], None]] = None,
        verbose: bool = True,
    ):
        self.handler = JobApprovalHandler(
            client=client,
            config=config,
            state=state,
            on_approve=on_approve,
            verbose=verbose,
        )

    def _check_all_entities(self):
        self.handler.check_and_approve()
