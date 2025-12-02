"""
Gmail email sender for notifications.
"""

import base64
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

try:
    from .base import NotificationSender
    from .template_renderer import TemplateRenderer
except ImportError:
    from notifications_base import NotificationSender

    try:
        from template_renderer import TemplateRenderer
    except ImportError:
        # Fallback for standalone testing - templates won't work
        TemplateRenderer = None  # type: ignore


class GmailSender(NotificationSender):
    """Send email notifications via Gmail API with optional HTML templates."""

    def __init__(self, credentials: Credentials, use_html: bool = True):
        """
        Initialize Gmail sender.

        Args:
            credentials: Google OAuth credentials
            use_html: Whether to send HTML emails (default True)
        """
        self.service = build("gmail", "v1", credentials=credentials)
        self.use_html = use_html
        self._renderer: Optional[TemplateRenderer] = None

    @property
    def renderer(self) -> Optional[TemplateRenderer]:
        """Lazy-load template renderer."""
        if self._renderer is None and TemplateRenderer is not None:
            self._renderer = TemplateRenderer()
        return self._renderer

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> bool:
        """
        Send email via Gmail API.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body_text: Plain text body (always required as fallback)
            body_html: Optional HTML body

        Returns:
            True if sent successfully, False on error
        """
        try:
            if body_html and self.use_html:
                # Create multipart message with both HTML and text
                message = MIMEMultipart("alternative")
                message["to"] = to_email
                message["subject"] = subject

                # Attach plain text first (fallback)
                part_text = MIMEText(body_text, "plain")
                message.attach(part_text)

                # Attach HTML (preferred)
                part_html = MIMEText(body_html, "html")
                message.attach(part_html)
            else:
                # Plain text only
                message = MIMEText(body_text)
                message["to"] = to_email
                message["subject"] = subject

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

            self.service.users().messages().send(
                userId="me", body={"raw": raw_message}
            ).execute()

            return True

        except Exception:
            # TODO: Add logging for error tracking
            return False

    def notify_new_job(
        self,
        do_email: str,
        job_name: str,
        submitter: str,
        timestamp: Optional[datetime] = None,
        job_url: Optional[str] = None,
    ) -> bool:
        """
        Send job notification to Data Owner.

        Args:
            do_email: Data Owner email address
            job_name: Name of the new job
            submitter: Email of job submitter
            timestamp: When the job was submitted
            job_url: Optional URL to view the job

        Returns:
            True if notification sent successfully
        """
        subject = f"New Job: {job_name}"

        body_text = f"""You have a new job request in SyftBox!

Job: {job_name}
From: {submitter}

Log in to SyftBox to review and approve this job.
"""

        body_html = None
        if self.use_html and self.renderer:
            try:
                body_html = self.renderer.render(
                    "emails/new_job.html",
                    {
                        "job_name": job_name,
                        "submitter": submitter,
                        "timestamp": timestamp or datetime.now(),
                        "job_url": job_url,
                    },
                )
            except Exception:
                pass  # Fall back to plain text

        return self.send_email(do_email, subject, body_text, body_html)

    def notify_job_approved(
        self,
        ds_email: str,
        job_name: str,
        job_url: Optional[str] = None,
    ) -> bool:
        """
        Send job approved notification to Data Scientist.

        Args:
            ds_email: Data Scientist email address
            job_name: Name of the approved job
            job_url: Optional URL to view the job

        Returns:
            True if notification sent successfully
        """
        subject = f"Job Approved: {job_name}"

        body_text = f"""Your job has been approved!

Job: {job_name}

The data owner has reviewed and approved your job request.
Your job will be executed soon.
"""

        body_html = None
        if self.use_html and self.renderer:
            try:
                body_html = self.renderer.render(
                    "emails/job_approved.html",
                    {
                        "job_name": job_name,
                        "job_url": job_url,
                    },
                )
            except Exception:
                pass

        return self.send_email(ds_email, subject, body_text, body_html)

    def notify_job_executed(
        self,
        ds_email: str,
        job_name: str,
        duration: Optional[int] = None,
        results_url: Optional[str] = None,
    ) -> bool:
        """
        Send job completed notification to Data Scientist.

        Args:
            ds_email: Data Scientist email address
            job_name: Name of the completed job
            duration: Job execution time in seconds
            results_url: Optional URL to download results

        Returns:
            True if notification sent successfully
        """
        subject = f"Job Completed: {job_name}"

        body_text = f"""Your job has finished execution!

Job: {job_name}

Your job has completed successfully. Results are available.
"""

        body_html = None
        if self.use_html and self.renderer:
            try:
                body_html = self.renderer.render(
                    "emails/job_executed.html",
                    {
                        "job_name": job_name,
                        "duration": duration,
                        "results_url": results_url,
                    },
                )
            except Exception:
                pass

        return self.send_email(ds_email, subject, body_text, body_html)

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

    def notify_new_peer_request_to_do(
        self,
        do_email: str,
        ds_email: str,
        peer_url: Optional[str] = None,
    ) -> bool:
        """
        Notify DO about new peer request from DS.

        Args:
            do_email: Data Owner email address
            ds_email: Data Scientist email address
            peer_url: Optional URL to review the peer request

        Returns:
            True if notification sent successfully
        """
        subject = f"New Peer Request from {ds_email}"

        body_text = f"""You have a new peer request in SyftBox!

From: {ds_email}

A data scientist wants to connect with you to collaborate on data projects.

Log in to SyftBox to review this peer request.
"""

        body_html = None
        if self.use_html and self.renderer:
            try:
                body_html = self.renderer.render(
                    "emails/new_peer_request.html",
                    {
                        "ds_email": ds_email,
                        "peer_url": peer_url,
                    },
                )
            except Exception:
                pass

        return self.send_email(do_email, subject, body_text, body_html)

    def notify_peer_request_sent(
        self,
        ds_email: str,
        do_email: str,
    ) -> bool:
        """
        Notify DS that their peer request was sent to DO.

        Args:
            ds_email: Data Scientist email address
            do_email: Data Owner email address

        Returns:
            True if notification sent successfully
        """
        subject = f"Peer Request Sent to {do_email}"

        body_text = f"""Your peer request has been sent!

To: {do_email}

Your request to connect with this data owner has been sent.
You will be notified when they accept your request.
"""

        body_html = None
        if self.use_html and self.renderer:
            try:
                body_html = self.renderer.render(
                    "emails/peer_request_sent.html",
                    {
                        "do_email": do_email,
                    },
                )
            except Exception:
                pass

        return self.send_email(ds_email, subject, body_text, body_html)

    def notify_peer_added_to_ds(
        self,
        ds_email: str,
        do_email: str,
    ) -> bool:
        """
        Notify DS that they successfully added DO as peer.

        Args:
            ds_email: Data Scientist email address
            do_email: Data Owner email address

        Returns:
            True if notification sent successfully
        """
        subject = f"Peer Added: {do_email}"

        body_text = f"""You successfully added a peer in SyftBox!

Peer: {do_email}

You can now submit jobs and collaborate with this data owner.
"""

        body_html = None
        if self.use_html and self.renderer:
            try:
                body_html = self.renderer.render(
                    "emails/peer_added.html",
                    {
                        "do_email": do_email,
                    },
                )
            except Exception:
                pass

        return self.send_email(ds_email, subject, body_text, body_html)

    def notify_peer_request_granted(
        self,
        ds_email: str,
        do_email: str,
    ) -> bool:
        """
        Notify DS that DO accepted their peer request.

        Args:
            ds_email: Data Scientist email address
            do_email: Data Owner email address

        Returns:
            True if notification sent successfully
        """
        subject = f"Peer Request Accepted: {do_email}"

        body_text = f"""Your peer request has been accepted!

Peer: {do_email}

The data owner has accepted your request. You can now collaborate with them.
"""

        body_html = None
        if self.use_html and self.renderer:
            try:
                body_html = self.renderer.render(
                    "emails/peer_granted.html",
                    {
                        "do_email": do_email,
                    },
                )
            except Exception:
                pass

        return self.send_email(ds_email, subject, body_text, body_html)
