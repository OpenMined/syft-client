"""Gmail transport layer using Gmail API"""

import base64
import json
import logging
import pickle
import time
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from googleapiclient.discovery import build

from ...transports.base import BaseTransport
from ..transport_base import BaseTransportLayer


class GmailTransportBase(BaseTransportLayer, BaseTransport):
    """Gmail transport layer using Gmail API via OAuth2"""

    # STATIC Attributes
    is_keystore = True
    is_notification_layer = True
    is_html_compatible = True
    is_reply_compatible = True
    guest_submit = False
    guest_read_file = False
    guest_read_folder = False

    # Email categorization
    BACKEND_PREFIX = "[SYFT-DATA]"
    NOTIFICATION_PREFIX = "[SYFT]"
    BACKEND_LABEL = "SyftBackend"

    def __init__(self, email: str):
        """Initialize Gmail transport"""
        super().__init__(email)
        self.gmail_service = None
        self.credentials = None
        self._labels = {}
        self._setup_verified = False

    @property
    def api_is_active_by_default(self) -> bool:
        """Gmail API requires manual activation"""
        return False

    @property
    def login_complexity(self) -> int:
        """No additional complexity after OAuth2"""
        if self.is_setup():
            return 0
        return 0

    @staticmethod
    def check_api_enabled(platform_client: Any) -> bool:
        """
        Check if Gmail API is enabled.

        Args:
            platform_client: The platform client with credentials

        Returns:
            bool: True if API is enabled, False otherwise
        """
        # Suppress googleapiclient warnings during API check
        googleapi_logger = logging.getLogger("googleapiclient.http")
        original_level = googleapi_logger.level
        googleapi_logger.setLevel(logging.ERROR)

        try:
            # Check if we're in Colab environment
            if hasattr(platform_client, "current_environment"):
                from ...environment import Environment

                if platform_client.current_environment == Environment.COLAB:
                    # Gmail doesn't work in Colab for Google Personal accounts
                    # Colab's auth doesn't provide the necessary Gmail scopes
                    return False

            # Regular OAuth credential check
            if (
                not hasattr(platform_client, "credentials")
                or not platform_client.credentials
            ):
                return False

            # Try to build service and make a simple API call
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            # Refresh credentials if needed
            if (
                platform_client.credentials.expired
                and platform_client.credentials.refresh_token
            ):
                platform_client.credentials.refresh(Request())

            service = build("gmail", "v1", credentials=platform_client.credentials)
            service.users().messages().list(userId="me", maxResults=1).execute()
            return True
        except Exception:
            return False
        finally:
            googleapi_logger.setLevel(original_level)

    @staticmethod
    def enable_api_static(transport_name: str, email: str) -> None:
        """Show instructions for enabling Gmail API"""
        print(f"\n🔧 To enable the Gmail API:")
        print(f"\n1. Open this URL in your browser:")
        print(
            f"   https://console.cloud.google.com/marketplace/product/google/gmail.googleapis.com?authuser={email}"
        )
        print(f"\n2. Click the 'Enable' button")
        print(f"\n3. Wait for the API to be enabled (may take 5-10 seconds)")
        print(
            f"\n📝 Note: API tends to flicker for 5-10 seconds before enabling/disabling"
        )

    @staticmethod
    def disable_api_static(transport_name: str, email: str) -> None:
        """Show instructions for disabling Gmail API"""
        print(f"\n🔧 To disable the Gmail API:")
        print(f"\n1. Open this URL in your browser:")
        print(
            f"   https://console.cloud.google.com/apis/api/gmail.googleapis.com/overview?authuser={email}"
        )
        print(f"\n2. Click 'Manage' or 'Disable API'")
        print(f"\n3. Confirm by clicking 'Disable'")
        print(
            f"\n📝 Note: API tends to flicker for 5-10 seconds before enabling/disabling"
        )

    def setup(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """Setup Gmail transport with OAuth2 credentials"""
        if not credentials or "credentials" not in credentials:
            return False

        try:
            self.credentials = credentials["credentials"]

            # Build Gmail service
            self.gmail_service = build("gmail", "v1", credentials=self.credentials)

            # Setup Gmail labels and filters
            self._setup_gmail()

            self._setup_verified = False
            return True
        except Exception:
            return False

    def is_setup(self) -> bool:
        """Check if Gmail transport is ready - NO CACHING, makes real API call"""
        if not self.gmail_service:
            return False

        try:
            # Simple API call - just list 1 message
            self.gmail_service.users().messages().list(
                userId="me", maxResults=1
            ).execute()
            return True
        except Exception:
            return False

    def _setup_gmail(self) -> None:
        """Setup Gmail labels and filters for backend emails"""
        try:
            self._ensure_backend_label()
            self._ensure_backend_filter()
        except Exception:
            pass

    def _ensure_backend_label(self) -> None:
        """Create backend label if it doesn't exist"""
        try:
            results = self.gmail_service.users().labels().list(userId="me").execute()
            labels = results.get("labels", [])

            for label in labels:
                if label["name"] == self.BACKEND_LABEL:
                    self._labels[self.BACKEND_LABEL] = label["id"]
                    return

            label_object = {
                "name": self.BACKEND_LABEL,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            }

            created_label = (
                self.gmail_service.users()
                .labels()
                .create(userId="me", body=label_object)
                .execute()
            )

            self._labels[self.BACKEND_LABEL] = created_label["id"]
        except:
            pass

    def _ensure_backend_filter(self) -> None:
        """Create filter to route backend emails to label"""
        try:
            results = (
                self.gmail_service.users()
                .settings()
                .filters()
                .list(userId="me")
                .execute()
            )
            filters = results.get("filter", [])

            for f in filters:
                criteria = f.get("criteria", {})
                if criteria.get("subject") == self.BACKEND_PREFIX:
                    return

            filter_object = {
                "criteria": {"subject": self.BACKEND_PREFIX},
                "action": {
                    "addLabelIds": [self._labels.get(self.BACKEND_LABEL)],
                    "removeLabelIds": ["INBOX"],
                },
            }

            self.gmail_service.users().settings().filters().create(
                userId="me", body=filter_object
            ).execute()
        except:
            pass

    def _test_email_to_self(self) -> bool:
        """Test Gmail functionality by sending and receiving an email to self"""
        try:
            test_id = f"syft-test-{datetime.now().strftime('%Y%m%d%H%M%S')}-{id(self)}"
            test_subject = f"Syft Client Test [{test_id}]"
            test_message = (
                "This is an automated test email from Syft Client.\\n\\n"
                "✓ Your Gmail transport is working correctly!\\n\\n"
                "This email confirms that Syft Client can successfully send messages "
                "through your Gmail account using OAuth2 authentication.\\n\\n"
                f"Test ID: {test_id}\\n\\n"
                "This email will be automatically marked as read."
            )

            if not self.send(self.email, test_message, subject=test_subject):
                return False

            time.sleep(2)

            return self._find_and_mark_test_email(test_id)
        except Exception:
            return False

    def _find_and_mark_test_email(self, test_id: str) -> bool:
        """Find test email by ID and mark it as read"""
        try:
            query = f'subject:"Syft Client Test [{test_id}]"'
            results = (
                self.gmail_service.users()
                .messages()
                .list(userId="me", q=query)
                .execute()
            )

            messages = results.get("messages", [])
            if not messages:
                return False

            for msg in messages:
                self.gmail_service.users().messages().modify(
                    userId="me", id=msg["id"], body={"removeLabelIds": ["UNREAD"]}
                ).execute()

            return True
        except Exception:
            return False

    def send(
        self,
        recipient: str,
        data: Any,
        subject: str = "Syft Client Message",
        is_notification: bool = True,
    ) -> bool:
        """Send email via Gmail API"""
        if not self.gmail_service:
            return False

        try:
            # Add appropriate prefix to subject
            if is_notification:
                if not subject.startswith(self.NOTIFICATION_PREFIX):
                    subject = f"{self.NOTIFICATION_PREFIX} {subject}"
            else:
                if not subject.startswith(self.BACKEND_PREFIX):
                    subject = f"{self.BACKEND_PREFIX} {subject}"

            # Create message
            message = MIMEMultipart()
            message["to"] = recipient
            message["from"] = self.email
            message["subject"] = subject
            message["X-Syft-Client"] = "true"
            message["X-Syft-Type"] = "notification" if is_notification else "backend"

            # Handle different data types
            if isinstance(data, str):
                message.attach(MIMEText(data, "plain"))
            elif isinstance(data, dict):
                message.attach(MIMEText(json.dumps(data, indent=2), "plain"))
            else:
                # Binary data - pickle and attach
                part = MIMEBase("application", "octet-stream")
                part.set_payload(pickle.dumps(data))
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f'attachment; filename="syft_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pkl"',
                )
                message.attach(part)
                message.attach(
                    MIMEText("Syft Client data attached as pickle file.", "plain")
                )

            # Convert to Gmail API format
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            body = {"raw": raw_message}

            # Send
            self.gmail_service.users().messages().send(userId="me", body=body).execute()
            return True

        except Exception as e:
            # Only print error if not in a repr/display context
            import sys
            import traceback

            # Check if we're being called from __repr__ by looking at the call stack
            stack = traceback.extract_stack()
            in_repr = any("__repr__" in frame.name for frame in stack)

            # Check if it's an API not enabled error
            if "has not been used in project" in str(
                e
            ) and "before or it is disabled" in str(e):
                if not in_repr:
                    print(f"\n⚠️  Gmail API is not enabled for your project!")
                    print("To fix this:")
                    # Extract the URL from the error message
                    import re

                    url_match = re.search(r"https://[^\s]+", str(e))
                    if url_match:
                        print(f"1. Open: {url_match.group(0)}")
                    print("2. Click 'ENABLE'")
                    print("3. Wait a few minutes for the change to propagate")
                    print("4. Try again\n")
            elif not in_repr:
                print(f"Error sending email: {e}")
            return False

    def receive(
        self, folder: Optional[str] = None, limit: int = 10, backend_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Receive emails from Gmail via API"""
        if not self.gmail_service:
            return []

        messages = []

        try:
            # Build query
            query_parts = []
            if backend_only:
                query_parts.append(f'subject:"{self.BACKEND_PREFIX}"')
            elif folder:
                query_parts.append(f"label:{folder}")

            query = " ".join(query_parts) if query_parts else None

            # List messages
            results = (
                self.gmail_service.users()
                .messages()
                .list(userId="me", q=query, maxResults=limit)
                .execute()
            )

            message_ids = results.get("messages", [])

            # Get full message details
            for msg_ref in message_ids:
                try:
                    msg = (
                        self.gmail_service.users()
                        .messages()
                        .get(userId="me", id=msg_ref["id"])
                        .execute()
                    )

                    # Parse message
                    headers = {
                        h["name"]: h["value"] for h in msg["payload"].get("headers", [])
                    }

                    subject = headers.get("Subject", "")
                    is_backend = subject.startswith(self.BACKEND_PREFIX)
                    is_syft = (
                        headers.get("X-Syft-Client", "").lower() == "true"
                        or subject.startswith(self.NOTIFICATION_PREFIX)
                        or is_backend
                    )

                    message_data = {
                        "id": msg["id"],
                        "from": headers.get("From", ""),
                        "to": headers.get("To", ""),
                        "subject": subject,
                        "date": headers.get("Date", ""),
                        "is_syft": is_syft,
                        "is_backend": is_backend,
                        "body": self._get_message_body(msg),
                        "attachments": self._get_message_attachments(msg),
                    }

                    messages.append(message_data)
                except:
                    continue

        except Exception as e:
            print(f"Error receiving emails: {e}")

        return messages

    def _get_message_body(self, message: Dict[str, Any]) -> str:
        """Extract message body from Gmail API message"""

        def get_body_from_parts(parts):
            for part in parts:
                if part["mimeType"] == "text/plain":
                    data = part["body"]["data"]
                    return base64.urlsafe_b64decode(data).decode(
                        "utf-8", errors="ignore"
                    )
                elif "parts" in part:
                    body = get_body_from_parts(part["parts"])
                    if body:
                        return body
            return ""

        payload = message["payload"]
        if "parts" in payload:
            return get_body_from_parts(payload["parts"])
        elif payload.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode(
                "utf-8", errors="ignore"
            )
        return ""

    def _get_message_attachments(self, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract attachments from Gmail API message"""
        attachments = []

        def process_parts(parts):
            for part in parts:
                filename = part.get("filename")
                if filename and part["body"].get("attachmentId"):
                    att_id = part["body"]["attachmentId"]

                    try:
                        att = (
                            self.gmail_service.users()
                            .messages()
                            .attachments()
                            .get(userId="me", messageId=message["id"], id=att_id)
                            .execute()
                        )

                        data = base64.urlsafe_b64decode(att["data"])

                        unpickled_data = None
                        if filename.endswith(".pkl"):
                            try:
                                unpickled_data = pickle.loads(data)
                            except:
                                pass

                        attachments.append(
                            {
                                "filename": filename,
                                "size": len(data),
                                "data": data,
                                "unpickled_data": unpickled_data,
                            }
                        )
                    except:
                        pass
                elif "parts" in part:
                    process_parts(part["parts"])

        if "parts" in message["payload"]:
            process_parts(message["payload"]["parts"])

        return attachments

    def send_backend(
        self, recipient: str, data: Any, subject: str = "Data Transfer"
    ) -> bool:
        """Send backend data email"""
        return self.send(recipient, data, subject, is_notification=False)

    def receive_backend(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Receive backend emails only"""
        return self.receive(limit=limit, backend_only=True)

    def send_notification(
        self, recipient: str, message: str, subject: str = "Notification"
    ) -> bool:
        """Send human-readable notification email"""
        return self.send(recipient, message, subject, is_notification=True)

    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
        """Test Gmail transport by sending an email to self with test data

        Args:
            test_data: Data to include in the test email
            cleanup: If True, delete the test email after creation (default: True)

        Returns:
            Dictionary with 'success' (bool) and 'url' (str) if successful
        """
        if not self.gmail_service:
            print(
                "Gmail service not initialized. Please authenticate first using client.auth()"
            )
            return {"success": False, "error": "Gmail service not initialized"}

        try:
            # Send test email to self
            success = self.send(
                recipient=self.email,
                data={"test_data": test_data, "timestamp": datetime.now().isoformat()},
                subject=f"Test Email - {test_data}",
            )

            if success:
                # Wait a moment for the email to be delivered
                import time

                time.sleep(2)

                # Mark the test email as read
                try:
                    # Search for the email we just sent
                    query = f'from:{self.email} to:{self.email} subject:"Test Email - {test_data}" is:unread'
                    results = (
                        self.gmail_service.users()
                        .messages()
                        .list(userId="me", q=query)
                        .execute()
                    )

                    messages = results.get("messages", [])
                    if messages:
                        message_id = messages[0]["id"]

                        # Mark the first matching message as read
                        self.gmail_service.users().messages().modify(
                            userId="me",
                            id=message_id,
                            body={"removeLabelIds": ["UNREAD"]},
                        ).execute()

                        # Delete the email if cleanup is requested
                        if cleanup:
                            try:
                                self.gmail_service.users().messages().trash(
                                    userId="me", id=message_id
                                ).execute()
                            except Exception:
                                # If deletion fails, try to permanently delete
                                try:
                                    self.gmail_service.users().messages().delete(
                                        userId="me", id=message_id
                                    ).execute()
                                except Exception:
                                    pass
                except Exception:
                    # If marking as read fails, continue anyway
                    pass

                # Return Gmail search URL for the test email
                import urllib.parse

                search_query = f'from:{self.email} subject:"Test Email - {test_data}"'
                encoded_query = urllib.parse.quote(search_query)
                # Use authuser parameter instead of /u/0/ to handle multiple accounts
                url = f"https://mail.google.com/mail/?authuser={urllib.parse.quote(self.email)}#search/{encoded_query}"

                print(f"✅ Gmail test successful! Email sent to {self.email}")
                if cleanup:
                    print(
                        "   Email has been deleted as requested (re-run test(cleanup=False) to see the email yourself.)"
                    )

                return {"success": True, "url": url}
            else:
                print("❌ Gmail test failed: Unable to send email")
                return {"success": False, "error": "Failed to send test email"}

        except Exception as e:
            print(f"❌ Gmail test failed: {e}")
            return {"success": False, "error": str(e)}

    # BaseTransport interface implementation
    def add_peer(self, email: str, verbose: bool = True) -> bool:
        """
        Add a peer for Gmail transport

        For Gmail, this is always successful since we can send emails to any valid address.
        We just validate the email format.
        """
        # Validate email format
        if not email or "@" not in email or "." not in email.split("@")[1]:
            if verbose:
                print(f"❌ Invalid email address: {email}")
            return False

        # Gmail doesn't require any setup to send to a contact
        if verbose:
            print(f"✅ Peer {email} added for Gmail transport (no setup required)")
        return True

    def remove_peer(self, email: str, verbose: bool = True) -> bool:
        """
        Remove a peer from Gmail transport

        For Gmail, this always succeeds since there's no persistent connection.
        """
        if verbose:
            print(f"✅ Peer {email} removed from Gmail transport")
        return True

    def list_peers(self) -> List[str]:
        """
        List contacts for Gmail transport

        Gmail doesn't maintain a separate peer list for transport purposes.
        Returns empty list.
        """
        return []

    def _send_archive_via_transport(
        self,
        archive_data: bytes,
        filename: str,
        recipient: str,
        message_id: Optional[str] = None,
    ) -> bool:
        """
        Send archive data via Gmail as an email attachment
        """
        try:
            # Create email message
            msg = MIMEMultipart()
            msg["To"] = recipient
            msg["From"] = self.email
            msg["Subject"] = f"{self.BACKEND_PREFIX} Syft Message" + (
                f" [{message_id}]" if message_id else ""
            )

            # Add body
            body = f"This is a Syft message containing encrypted data.\nMessage ID: {message_id or 'N/A'}"
            msg.attach(MIMEText(body, "plain"))

            # Attach the archive data
            part = MIMEBase("application", "octet-stream")
            part.set_payload(archive_data)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={filename}")
            msg.attach(part)

            # Send the email
            raw_msg = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            message_body = {"raw": raw_msg}

            if self._labels and self.BACKEND_LABEL in self._labels:
                message_body["labelIds"] = [self._labels[self.BACKEND_LABEL]]

            result = (
                self.gmail_service.users()
                .messages()
                .send(userId="me", body=message_body)
                .execute()
            )

            return bool(result.get("id"))

        except Exception as e:
            print(f"❌ Failed to send via Gmail: {e}")
            return False

    @property
    def transport_name(self) -> str:
        """Get the name of this transport"""
        return "gmail"

    def is_available(self) -> bool:
        """Check if Gmail transport is available"""
        return self.is_setup()

    def get_peer_resource(self, email: str) -> Optional[Any]:
        """
        Get the resource associated with a peer for Gmail

        Gmail doesn't have persistent folders/resources like Drive,
        so we return basic availability info

        Args:
            email: Email address of the contact

        Returns:
            PeerResource with email info
        """
        from ...sync.peer_resource import PeerResource

        return PeerResource(
            peer_email=email,
            transport_name=self.transport_name,
            platform_name=self._get_platform_name(),
            resource_type="email",
            available=self.is_setup(),
        )

    def _get_platform_name(self) -> str:
        raise NotImplementedError()
        # """Get the platform name for this transport"""
        # return (
        #     getattr(self._platform_client, "platform", "google_org")
        #     if hasattr(self, "_platform_client")
        #     else "google_org"
        # )
