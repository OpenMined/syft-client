"""
Gmail email sender for notifications.
"""

import base64
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

try:
    from .base import NotificationSender
except ImportError:
    from notifications_base import NotificationSender


class GmailSender(NotificationSender):
    def __init__(self, credentials: Credentials):
        self.service = build("gmail", "v1", credentials=credentials)

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """
        Send email via Gmail API.

        Returns:
            True if sent successfully, False on error
        """
        # TODO: Add logging for debugging
        # logger.info(f"Sending email to {to_email}: {subject}")
        try:
            message = MIMEText(body)
            message["to"] = to_email
            message["subject"] = subject

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

            self.service.users().messages().send(
                userId="me", body={"raw": raw_message}
            ).execute()

            return True

        except Exception:
            # TODO: Add logging for error tracking
            # except Exception as e:
            #     logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    def notify_new_job(self, do_email: str, job_name: str, submitter: str) -> bool:
        """
        Send job notification to Data Owner.

        Args:
            do_email: Data Owner email address
            job_name: Name of the new job
            submitter: Email of job submitter

        Returns:
            True if notification sent successfully
        """
        subject = f"New Job: {job_name}"

        body = f"""You have a new job request in SyftBox!

Job: {job_name}
From: {submitter}

Log in to SyftBox to review and approve this job.
"""

        return self.send_email(do_email, subject, body)

    def notify_job_approved(self, ds_email: str, job_name: str) -> bool:
        """
        Send job approved notification to Data Scientist.

        Args:
            ds_email: Data Scientist email address
            job_name: Name of the approved job

        Returns:
            True if notification sent successfully
        """
        subject = f"Job Approved: {job_name}"

        body = f"""Your job has been approved!

Job: {job_name}

The data owner has reviewed and approved your job request.
Your job will be executed soon.
"""

        return self.send_email(ds_email, subject, body)

    def notify_job_executed(self, ds_email: str, job_name: str) -> bool:
        """
        Send job completed notification to Data Scientist.

        Args:
            ds_email: Data Scientist email address
            job_name: Name of the completed job

        Returns:
            True if notification sent successfully
        """
        subject = f"Job Completed: {job_name}"

        body = f"""Your job has finished execution!

Job: {job_name}

Your job has completed successfully. Results are available.
"""

        return self.send_email(ds_email, subject, body)

    def send_notification(self, to: str, subject: str, body: str) -> bool:
        """
        Implement abstract method from NotificationSender.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body

        Returns:
            True if sent successfully
        """
        return self.send_email(to, subject, body)
