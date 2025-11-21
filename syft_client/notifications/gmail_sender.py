"""
Gmail email sender for notifications.
"""

import base64
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


class GmailSender:
    def __init__(self, credentials: Credentials):
        self.service = build("gmail", "v1", credentials=credentials)

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """
        Send email via Gmail API.

        Returns:
            True if sent successfully, False on error
        """
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
