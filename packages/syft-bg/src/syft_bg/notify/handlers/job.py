"""Job event handler for notifications."""

from typing import Optional

from syft_bg.common.state import JsonStateManager
from syft_bg.notify.gmail.sender import GmailSender


class JobHandler:
    """Handles job-related notification events."""

    def __init__(
        self,
        sender: GmailSender,
        state: JsonStateManager,
        notify_on_new: bool = True,
        notify_on_approved: bool = True,
        notify_on_executed: bool = True,
    ):
        self.sender = sender
        self.state = state
        self.notify_on_new = notify_on_new
        self.notify_on_approved = notify_on_approved
        self.notify_on_executed = notify_on_executed

    def on_new_job(
        self,
        do_email: str,
        job_name: str,
        submitter: str,
        job_url: Optional[str] = None,
    ) -> bool:
        """Notify DO about a new job."""
        if not self.notify_on_new:
            return False

        if self.state.was_notified(job_name, "new"):
            print(f"[JobHandler] Skip {job_name}/new: already notified")
            return False

        success = self.sender.notify_new_job(
            do_email, job_name, submitter, job_url=job_url
        )

        if success:
            self.state.mark_notified(job_name, "new")
        else:
            print(f"[JobHandler] Failed to send new job notification for {job_name}")

        return success

    def on_job_approved(
        self,
        ds_email: str,
        job_name: str,
        job_url: Optional[str] = None,
    ) -> bool:
        """Notify DS that their job was approved."""
        if not self.notify_on_approved:
            return False

        if self.state.was_notified(job_name, "approved"):
            print(f"[JobHandler] Skip {job_name}/approved: already notified")
            return False

        success = self.sender.notify_job_approved(ds_email, job_name, job_url=job_url)

        if success:
            self.state.mark_notified(job_name, "approved")
        else:
            print(
                f"[JobHandler] Failed to send approved notification for {job_name} to {ds_email}"
            )

        return success

    def on_job_executed(
        self,
        ds_email: str,
        job_name: str,
        duration: Optional[int] = None,
        results_url: Optional[str] = None,
    ) -> bool:
        """Notify DS that their job finished."""
        if not self.notify_on_executed:
            return False

        if self.state.was_notified(job_name, "executed"):
            print(f"[JobHandler] Skip {job_name}/executed: already notified")
            return False

        success = self.sender.notify_job_executed(
            ds_email, job_name, duration=duration, results_url=results_url
        )

        if success:
            self.state.mark_notified(job_name, "executed")
        else:
            print(
                f"[JobHandler] Failed to send executed notification for {job_name} to {ds_email}"
            )

        return success
