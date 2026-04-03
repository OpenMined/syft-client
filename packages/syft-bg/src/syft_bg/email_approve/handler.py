"""Handler for email-based job approval/rejection."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

from syft_bg.common.state import JsonStateManager

if TYPE_CHECKING:
    from syft_client.sync.syftbox_manager import SyftboxManager


def parse_reply(text: str) -> tuple[Optional[str], Optional[str]]:
    """Parse a reply email for approve/deny commands.

    Returns:
        (action, reason) where action is "approve", "deny", or None.
        reason is only set for "deny".
    """
    if not text:
        return None, None

    # Take first non-empty line
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        lower = line.lower()
        if lower.startswith("approve"):
            return "approve", None

        match = re.match(r"deny\s+(.*)", line, re.IGNORECASE)
        if match:
            reason = match.group(1).strip()
            return "deny", reason if reason else "No reason provided"

        if lower == "deny":
            return "deny", "No reason provided"

        # First non-empty line didn't match any command
        return None, None

    return None, None


class EmailApproveHandler:
    """Processes email replies to approve or reject jobs."""

    def __init__(
        self,
        client: SyftboxManager,
        state: JsonStateManager,
        notify_state: JsonStateManager,
        do_email: str,
    ):
        self.client = client
        self.state = state
        self.notify_state = notify_state
        self.do_email = do_email

    def handle_reply(self, thread_id: str, reply_text: str) -> None:
        """Process a reply email for a job thread."""
        job_name = self.notify_state.get_job_name_by_thread_id(thread_id)
        if not job_name:
            raise ValueError(f"No job found for thread {thread_id}")

        state_key = f"email_reply_{thread_id}"
        if self.state.was_notified(state_key, "processed"):
            return

        action, reason = parse_reply(reply_text)
        if action is None:
            raise ValueError(f"Unrecognized reply for {job_name}: {reply_text[:100]}")

        job = self._find_job(job_name)

        if job.status != "pending":
            raise ValueError(f"Job {job_name} is {job.status}, not pending")

        if action == "approve":
            self._approve_job(job, job_name, state_key)
        elif action == "deny":
            self._reject_job(job, job_name, reason or "", state_key)

    def _find_job(self, job_name: str):
        """Find a job by name in the client's job list."""
        for job in self.client.jobs:
            if job.name == job_name:
                return job
        raise ValueError(f"Job not found: {job_name}")

    def _approve_job(self, job, job_name: str, state_key: str) -> None:
        """Approve a job and process it."""
        job.approve()
        self.state.mark_notified(state_key, "processed")
        self.client.process_approved_jobs()
        print(f"[EmailApproveHandler] Approved job: {job_name}")

    def _reject_job(self, job, job_name: str, reason: str, state_key: str) -> None:
        """Reject a job with a reason."""
        job.reject(reason)
        self.state.mark_notified(state_key, "processed")
        print(f"[EmailApproveHandler] Rejected job: {job_name} (reason: {reason})")
