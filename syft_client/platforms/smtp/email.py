"""Generic SMTP email transport layer implementation"""

import email
import imaplib
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from ...environment import Environment
from ..transport_base import BaseTransportLayer


class SMTPEmailTransport(BaseTransportLayer):
    """Generic SMTP/IMAP email transport layer"""

    # STATIC Attributes
    is_keystore = False  # Generic SMTP less trusted than major providers
    is_notification_layer = True  # Users check email regularly
    is_html_compatible = True  # Email supports HTML
    is_reply_compatible = True  # Email has native reply support
    guest_submit = False  # Requires email account
    guest_read_file = False  # Requires authentication
    guest_read_folder = False  # Requires authentication

    def __init__(self, email: str, credentials: Optional[Dict[str, Any]] = None):
        super().__init__(email)
        if credentials:
            self._cached_credentials = credentials
            self.smtp_server = credentials.get("smtp_server")
            self.smtp_port = credentials.get("smtp_port", 587)
            self.imap_server = credentials.get("imap_server")
            self.imap_port = credentials.get("imap_port", 993)

    @property
    def api_is_active_by_default(self) -> bool:
        """SMTP is a standard protocol"""
        return True  # No API activation needed

    @property
    def login_complexity(self) -> int:
        """SMTP requires server details + credentials"""
        if self._cached_credentials:
            return 0  # Already set up

        # User needs to provide SMTP server details
        # (host, port, security settings, username, password)
        return 2  # Need server config + credentials

    def authenticate(self) -> Dict[str, Any]:
        """Set up SMTP/IMAP connection"""
        if self._cached_credentials:
            return {"authenticated": True, "cached": True}

        # This would typically delegate to the platform client
        raise NotImplementedError(
            "Direct transport auth not implemented - use platform client"
        )

    def send(self, recipient: str, data: Any) -> bool:
        """Send email via SMTP"""
        if not self._cached_credentials:
            raise Exception("Not authenticated")

        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = self.email
            msg["To"] = recipient
            msg["Subject"] = data.get("subject", "Syft Client Message")

            # Add body
            body = data.get("body", "")
            msg.attach(MIMEText(body, "plain"))

            # Connect and send
            context = ssl.create_default_context()

            if self.smtp_port == 465:  # SSL
                server = smtplib.SMTP_SSL(
                    self.smtp_server, self.smtp_port, context=context
                )
            else:  # TLS
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()

            server.login(
                self._cached_credentials["email"], self._cached_credentials["password"]
            )

            server.send_message(msg)
            server.quit()

            return True

        except Exception as e:
            print(f"Failed to send email: {str(e)}")
            return False

    def receive(self) -> List[Dict[str, Any]]:
        """Receive emails via IMAP"""
        if not self._cached_credentials or not self.imap_server:
            raise Exception("Not authenticated or no IMAP server configured")

        messages = []

        try:
            # Connect to IMAP
            if self.imap_port == 993:  # SSL
                server = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            else:
                server = imaplib.IMAP4(self.imap_server, self.imap_port)

            server.login(
                self._cached_credentials["email"], self._cached_credentials["password"]
            )

            # Select inbox
            server.select("INBOX")

            # Search for all messages (limit to recent for demo)
            status, data = server.search(None, "ALL")

            if status == "OK":
                mail_ids = data[0].split()
                # Get last 5 messages
                for mail_id in mail_ids[-5:]:
                    status, msg_data = server.fetch(mail_id, "(RFC822)")

                    if status == "OK":
                        for response_part in msg_data:
                            if isinstance(response_part, tuple):
                                msg = email.message_from_bytes(response_part[1])

                                messages.append(
                                    {
                                        "id": mail_id.decode(),
                                        "from": msg["From"],
                                        "to": msg["To"],
                                        "subject": msg["Subject"],
                                        "date": msg["Date"],
                                        "body": self._get_email_body(msg),
                                    }
                                )

            server.close()
            server.logout()

            return messages

        except Exception as e:
            print(f"Failed to receive emails: {str(e)}")
            return []

    def _get_email_body(self, msg) -> str:
        """Extract body from email message"""
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode(
                        "utf-8", errors="ignore"
                    )
                    break
        else:
            body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

        return body
