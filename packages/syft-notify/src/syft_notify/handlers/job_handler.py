from typing import Optional

from syft_notify.core.base import NotificationSender, StateManager


class JobHandler:
    def __init__(
        self,
        sender: NotificationSender,
        state: StateManager,
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
        if not self.notify_on_new:
            return False

        if self.state.was_notified(job_name, "new"):
            return False

        if hasattr(self.sender, "notify_new_job"):
            success = self.sender.notify_new_job(
                do_email, job_name, submitter, job_url=job_url
            )
        else:
            success = self.sender.send_notification(
                do_email,
                f"New Job: {job_name}",
                f"New job from {submitter}",
            )

        if success:
            self.state.mark_notified(job_name, "new")

        return success

    def on_job_approved(
        self,
        ds_email: str,
        job_name: str,
        job_url: Optional[str] = None,
    ) -> bool:
        if not self.notify_on_approved:
            return False

        if self.state.was_notified(job_name, "approved"):
            return False

        if hasattr(self.sender, "notify_job_approved"):
            success = self.sender.notify_job_approved(
                ds_email, job_name, job_url=job_url
            )
        else:
            success = self.sender.send_notification(
                ds_email,
                f"Job Approved: {job_name}",
                "Your job has been approved",
            )

        if success:
            self.state.mark_notified(job_name, "approved")

        return success

    def on_job_executed(
        self,
        ds_email: str,
        job_name: str,
        duration: Optional[int] = None,
        results_url: Optional[str] = None,
    ) -> bool:
        if not self.notify_on_executed:
            return False

        if self.state.was_notified(job_name, "executed"):
            return False

        if hasattr(self.sender, "notify_job_executed"):
            success = self.sender.notify_job_executed(
                ds_email, job_name, duration=duration, results_url=results_url
            )
        else:
            success = self.sender.send_notification(
                ds_email,
                f"Job Completed: {job_name}",
                "Your job has finished",
            )

        if success:
            self.state.mark_notified(job_name, "executed")

        return success
