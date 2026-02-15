"""Gmail email sender."""

import base64
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from syft_bg.notify.email_templates import TemplateRenderer


class GmailSender:
    """Sends emails via Gmail API."""

    def __init__(self, credentials: Credentials, use_html: bool = True):
        self.service = build("gmail", "v1", credentials=credentials)
        self.use_html = use_html
        self._renderer: Optional[TemplateRenderer] = None

    @property
    def renderer(self) -> Optional[TemplateRenderer]:
        if self._renderer is None:
            self._renderer = TemplateRenderer()
        return self._renderer

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> bool:
        """Send an email."""
        try:
            if body_html and self.use_html:
                message = MIMEMultipart("alternative")
                message["to"] = to_email
                message["subject"] = subject
                part_text = MIMEText(body_text, "plain")
                message.attach(part_text)
                part_html = MIMEText(body_html, "html")
                message.attach(part_html)
            else:
                message = MIMEText(body_text)
                message["to"] = to_email
                message["subject"] = subject

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            self.service.users().messages().send(
                userId="me", body={"raw": raw_message}
            ).execute()
            return True
        except Exception:
            return False

    def notify_new_job(
        self,
        do_email: str,
        job_name: str,
        submitter: str,
        timestamp: Optional[datetime] = None,
        job_url: Optional[str] = None,
    ) -> bool:
        """Notify DO about a new job."""
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
                pass

        return self.send_email(do_email, subject, body_text, body_html)

    def notify_job_approved(
        self,
        ds_email: str,
        job_name: str,
        job_url: Optional[str] = None,
    ) -> bool:
        """Notify DS that their job was approved."""
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
        """Notify DS that their job finished."""
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

    def notify_new_peer_request_to_do(
        self,
        do_email: str,
        ds_email: str,
        peer_url: Optional[str] = None,
    ) -> bool:
        """Notify DO about a new peer request."""
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
        """Notify DS that their peer request was sent."""
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
        """Notify DS that they added a peer."""
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
        """Notify DS that their peer request was accepted."""
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
