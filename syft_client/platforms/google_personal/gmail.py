"""Gmail transport layer using Gmail API"""

from typing import Any, Dict, List, Optional
import base64
import pickle
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import json

from googleapiclient.discovery import build
from ..transport_base import BaseTransportLayer


class GmailTransport(BaseTransportLayer):
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
    
    def setup(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """Setup Gmail transport with OAuth2 credentials"""
        if not credentials or 'credentials' not in credentials:
            return False
            
        try:
            self.credentials = credentials['credentials']
            
            # Build Gmail service
            self.gmail_service = build('gmail', 'v1', credentials=self.credentials)
            
            # Setup Gmail labels and filters
            self._setup_gmail()
            
            self._setup_verified = False
            return True
        except Exception:
            return False
    
    def is_setup(self) -> bool:
        """Check if Gmail transport is ready"""
        # First check if we're cached as setup
        if self.is_cached_as_setup():
            return True
            
        # Otherwise check normal setup
        if not self.gmail_service:
            return False
        
        if self._setup_verified:
            return True
        
        # Test by sending email to self
        if self._test_email_to_self():
            self._setup_verified = True
            return True
            
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
            results = self.gmail_service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])
            
            for label in labels:
                if label['name'] == self.BACKEND_LABEL:
                    self._labels[self.BACKEND_LABEL] = label['id']
                    return
            
            label_object = {
                'name': self.BACKEND_LABEL,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show'
            }
            
            created_label = self.gmail_service.users().labels().create(
                userId='me', body=label_object
            ).execute()
            
            self._labels[self.BACKEND_LABEL] = created_label['id']
        except:
            pass
    
    def _ensure_backend_filter(self) -> None:
        """Create filter to route backend emails to label"""
        try:
            results = self.gmail_service.users().settings().filters().list(userId='me').execute()
            filters = results.get('filter', [])
            
            for f in filters:
                criteria = f.get('criteria', {})
                if criteria.get('subject') == self.BACKEND_PREFIX:
                    return
            
            filter_object = {
                'criteria': {'subject': self.BACKEND_PREFIX},
                'action': {
                    'addLabelIds': [self._labels.get(self.BACKEND_LABEL)],
                    'removeLabelIds': ['INBOX']
                }
            }
            
            self.gmail_service.users().settings().filters().create(
                userId='me', body=filter_object
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
            results = self.gmail_service.users().messages().list(
                userId='me', q=query
            ).execute()
            
            messages = results.get('messages', [])
            if not messages:
                return False
            
            for msg in messages:
                self.gmail_service.users().messages().modify(
                    userId='me',
                    id=msg['id'],
                    body={'removeLabelIds': ['UNREAD']}
                ).execute()
            
            return True
        except Exception:
            return False
    
    def send(self, recipient: str, data: Any, subject: str = "Syft Client Message", 
             is_notification: bool = True) -> bool:
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
            message['to'] = recipient
            message['from'] = self.email
            message['subject'] = subject
            message['X-Syft-Client'] = 'true'
            message['X-Syft-Type'] = 'notification' if is_notification else 'backend'
            
            # Handle different data types
            if isinstance(data, str):
                message.attach(MIMEText(data, 'plain'))
            elif isinstance(data, dict):
                message.attach(MIMEText(json.dumps(data, indent=2), 'plain'))
            else:
                # Binary data - pickle and attach
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(pickle.dumps(data))
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="syft_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pkl"'
                )
                message.attach(part)
                message.attach(MIMEText("Syft Client data attached as pickle file.", 'plain'))
            
            # Convert to Gmail API format
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            body = {'raw': raw_message}
            
            # Send
            self.gmail_service.users().messages().send(userId='me', body=body).execute()
            return True
            
        except Exception as e:
            print(f"Error sending email: {e}")
            return False
    
    def receive(self, folder: Optional[str] = None, limit: int = 10, 
                backend_only: bool = False) -> List[Dict[str, Any]]:
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
                query_parts.append(f'label:{folder}')
            
            query = ' '.join(query_parts) if query_parts else None
            
            # List messages
            results = self.gmail_service.users().messages().list(
                userId='me', q=query, maxResults=limit
            ).execute()
            
            message_ids = results.get('messages', [])
            
            # Get full message details
            for msg_ref in message_ids:
                try:
                    msg = self.gmail_service.users().messages().get(
                        userId='me', id=msg_ref['id']
                    ).execute()
                    
                    # Parse message
                    headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}
                    
                    subject = headers.get('Subject', '')
                    is_backend = subject.startswith(self.BACKEND_PREFIX)
                    is_syft = (
                        headers.get('X-Syft-Client', '').lower() == 'true' or
                        subject.startswith(self.NOTIFICATION_PREFIX) or
                        is_backend
                    )
                    
                    message_data = {
                        'id': msg['id'],
                        'from': headers.get('From', ''),
                        'to': headers.get('To', ''),
                        'subject': subject,
                        'date': headers.get('Date', ''),
                        'is_syft': is_syft,
                        'is_backend': is_backend,
                        'body': self._get_message_body(msg),
                        'attachments': self._get_message_attachments(msg)
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
                if part['mimeType'] == 'text/plain':
                    data = part['body']['data']
                    return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                elif 'parts' in part:
                    body = get_body_from_parts(part['parts'])
                    if body:
                        return body
            return ''
        
        payload = message['payload']
        if 'parts' in payload:
            return get_body_from_parts(payload['parts'])
        elif payload.get('body', {}).get('data'):
            return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
        return ''
    
    def _get_message_attachments(self, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract attachments from Gmail API message"""
        attachments = []
        
        def process_parts(parts):
            for part in parts:
                filename = part.get('filename')
                if filename and part['body'].get('attachmentId'):
                    att_id = part['body']['attachmentId']
                    
                    try:
                        att = self.gmail_service.users().messages().attachments().get(
                            userId='me', messageId=message['id'], id=att_id
                        ).execute()
                        
                        data = base64.urlsafe_b64decode(att['data'])
                        
                        unpickled_data = None
                        if filename.endswith('.pkl'):
                            try:
                                unpickled_data = pickle.loads(data)
                            except:
                                pass
                        
                        attachments.append({
                            'filename': filename,
                            'size': len(data),
                            'data': data,
                            'unpickled_data': unpickled_data
                        })
                    except:
                        pass
                elif 'parts' in part:
                    process_parts(part['parts'])
        
        if 'parts' in message['payload']:
            process_parts(message['payload']['parts'])
            
        return attachments
    
    def send_backend(self, recipient: str, data: Any, subject: str = "Data Transfer") -> bool:
        """Send backend data email"""
        return self.send(recipient, data, subject, is_notification=False)
    
    def receive_backend(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Receive backend emails only"""
        return self.receive(limit=limit, backend_only=True)
    
    def send_notification(self, recipient: str, message: str, subject: str = "Notification") -> bool:
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
            print("Gmail service not initialized. Please authenticate first using client.auth()")
            return {"success": False, "error": "Gmail service not initialized"}
            
        try:
            # Send test email to self
            success = self.send(
                recipient=self.email,
                data={"test_data": test_data, "timestamp": datetime.now().isoformat()},
                subject=f"Test Email - {test_data}"
            )
            
            if success:
                # Wait a moment for the email to be delivered
                import time
                time.sleep(2)
                
                # Mark the test email as read
                try:
                    # Search for the email we just sent
                    query = f"from:{self.email} to:{self.email} subject:\"Test Email - {test_data}\" is:unread"
                    results = self.gmail_service.users().messages().list(
                        userId='me', q=query
                    ).execute()
                    
                    messages = results.get('messages', [])
                    if messages:
                        message_id = messages[0]['id']
                        
                        # Mark the first matching message as read
                        self.gmail_service.users().messages().modify(
                            userId='me',
                            id=message_id,
                            body={'removeLabelIds': ['UNREAD']}
                        ).execute()
                        
                        # Delete the email if cleanup is requested
                        if cleanup:
                            try:
                                self.gmail_service.users().messages().trash(
                                    userId='me',
                                    id=message_id
                                ).execute()
                            except Exception:
                                # If deletion fails, try to permanently delete
                                try:
                                    self.gmail_service.users().messages().delete(
                                        userId='me',
                                        id=message_id
                                    ).execute()
                                except Exception:
                                    pass
                except Exception:
                    # If marking as read fails, continue anyway
                    pass
                
                # Return Gmail search URL for the test email
                import urllib.parse
                search_query = f"from:{self.email} subject:\"Test Email - {test_data}\""
                encoded_query = urllib.parse.quote(search_query)
                # Use authuser parameter instead of /u/0/ to handle multiple accounts
                url = f"https://mail.google.com/mail/?authuser={urllib.parse.quote(self.email)}#search/{encoded_query}"
                
                print(f"✅ Gmail test successful! Email sent to {self.email}")
                if cleanup:
                    print("   Email has been deleted as requested")
                
                return {"success": True, "url": url}
            else:
                print("❌ Gmail test failed: Unable to send email")
                return {"success": False, "error": "Failed to send test email"}
                
        except Exception as e:
            print(f"❌ Gmail test failed: {e}")
            return {"success": False, "error": str(e)}