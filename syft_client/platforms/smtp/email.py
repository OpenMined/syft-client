"""Generic SMTP email transport layer implementation"""

from typing import Any, Dict, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import pickle
import base64
import smtplib
import imaplib
import email as email_lib
import time
from datetime import datetime
from ..transport_base import BaseTransportLayer
from ...environment import Environment


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
    
    # Email type prefixes
    BACKEND_PREFIX = "[SYFT-DATA]"  # For backend/data emails
    NOTIFICATION_PREFIX = "[SYFT]"  # For human-readable notifications
    BACKEND_FOLDER = "SyftBackend"  # Folder for backend emails
    
    def __init__(self, email: str, credentials: Optional[Dict[str, Any]] = None):
        """Initialize SMTP transport with credentials"""
        super().__init__(email)
        self.credentials = credentials
        if credentials:
            self.smtp_server = credentials.get('smtp_server')
            self.smtp_port = credentials.get('smtp_port', 587)
            self.imap_server = credentials.get('imap_server')
            self.imap_port = credentials.get('imap_port', 993)
        self._is_setup_verified = False  # Cache setup verification
    
    @property
    def api_is_active_by_default(self) -> bool:
        """SMTP/IMAP doesn't require API activation"""
        return True  # Using standard email protocols
        
    @property
    def login_complexity(self) -> int:
        """No additional setup needed after authentication"""
        return 0  # SMTP client already handles authentication
    
    
    def setup(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """Setup SMTP transport with credentials and create backend folder"""
        if not credentials or 'password' not in credentials:
            return False
            
        # Store credentials
        self.credentials = credentials
        self._cached_credentials = credentials
        self.smtp_server = credentials.get('smtp_server')
        self.smtp_port = credentials.get('smtp_port', 587)
        self.imap_server = credentials.get('imap_server')
        self.imap_port = credentials.get('imap_port', 993)
        self._is_setup_verified = False  # Reset verification flag
        
        # Create backend folder if it doesn't exist (only if IMAP is configured)
        if self.imap_server and not self._create_backend_folder():
            # Non-fatal if folder creation fails
            pass
            
        return True
    
    def is_setup(self) -> bool:
        """Check if SMTP transport is ready"""
        if not self.credentials or 'password' not in self.credentials:
            return False
        
        # Use cached result if available
        if self._is_setup_verified:
            return True
        
        # Test by sending email to self
        if self.test_email_to_self():
            self._is_setup_verified = True
            return True
            
        return False
    
    def test_email_to_self(self) -> bool:
        """Test SMTP functionality by sending and receiving an email to self"""
        if not self.credentials or 'password' not in self.credentials:
            return False
            
        try:
            # Generate unique test ID to identify our email
            test_id = f"syft-test-{datetime.now().strftime('%Y%m%d%H%M%S')}-{id(self)}"
            test_subject = f"Syft Client Test [{test_id}]"
            test_message = (
                "This is an automated test email from Syft Client.\n\n"
                "✓ Your SMTP transport is working correctly!\n\n"
                "This email confirms that Syft Client can successfully send messages "
                "through your email account.\n\n"
                f"Test ID: {test_id}\n\n"
                "This email will be automatically marked as read if IMAP is configured."
            )
            
            # Send email to self
            email = self.credentials.get('email', self.email)
            if not self.send(email, test_message, subject=test_subject):
                return False
            
            # If IMAP is configured, try to find and mark the test email
            if self.imap_server:
                # Wait a moment for email to arrive
                time.sleep(2)
                # Try to find and read the test email
                return self._find_and_mark_test_email(test_id)
            else:
                # If no IMAP, just confirm send worked
                return True
            
        except Exception:
            return False
    
    def _create_backend_folder(self) -> bool:
        """Create SyftBackend folder if it doesn't exist"""
        if not self.credentials or not self.imap_server:
            return False
            
        try:
            with imaplib.IMAP4_SSL(self.imap_server, self.imap_port) as imap:
                imap.login(self.credentials['email'], self.credentials['password'])
                
                # Check if folder exists
                status, folders = imap.list()
                folder_exists = False
                
                if status == 'OK':
                    for folder in folders:
                        if isinstance(folder, bytes):
                            folder_str = folder.decode('utf-8')
                            if self.BACKEND_FOLDER in folder_str:
                                folder_exists = True
                                break
                
                # Create folder if it doesn't exist
                if not folder_exists:
                    status, _ = imap.create(self.BACKEND_FOLDER)
                    if status != 'OK':
                        return False
                        
                    # Subscribe to the folder so it shows up in clients
                    imap.subscribe(self.BACKEND_FOLDER)
                
                # Note: Email filters need to be created via the email client interface
                if not folder_exists:
                    print(f"\nℹ️  To automatically route backend emails to the {self.BACKEND_FOLDER} folder:")
                    print(f"   1. Go to your email settings → Filters/Rules")
                    print(f"   2. Create a filter for: subject:\"{self.BACKEND_PREFIX}\"")
                    print(f"   3. Move to folder: {self.BACKEND_FOLDER}")
                    print(f"   4. Skip the inbox (optional)")
                
                return True
                
        except Exception as e:
            print(f"Error creating backend folder: {e}")
            return False
    
    def _find_and_mark_test_email(self, test_id: str) -> bool:
        """Find test email by ID and mark it as read"""
        if not self.credentials or not self.imap_server:
            return False
            
        try:
            # Connect to IMAP
            with imaplib.IMAP4_SSL(self.imap_server, self.imap_port) as imap:
                imap.login(self.credentials['email'], self.credentials['password'])
                
                # Select inbox
                imap.select('INBOX')
                
                # Search for emails with our test ID in subject
                # Using subject search since it's more reliable than body search
                search_criteria = f'(SUBJECT "Syft Client Test [{test_id}]")'
                _, data = imap.search(None, search_criteria)
                
                message_ids = data[0].split()
                if not message_ids:
                    return False
                
                # Mark the email as read (add \Seen flag)
                for msg_id in message_ids:
                    imap.store(msg_id, '+FLAGS', '\\Seen')
                
                return True
                
        except Exception:
            return False
        
    def send(self, recipient: str, data: Any, subject: str = "Syft Client Message", 
             is_notification: bool = True) -> bool:
        """
        Send email via SMTP
        
        Args:
            recipient: Email address to send to
            data: Data to send (str, dict, or any picklable object)
            subject: Email subject
            is_notification: If True, sends as notification email. If False, as backend email.
        """
        if not self.credentials:
            raise ValueError("No credentials available. Please authenticate first.")
            
        try:
            # Add appropriate prefix to subject based on email type
            if is_notification:
                # For human-readable notifications
                if not subject.startswith(self.NOTIFICATION_PREFIX):
                    subject = f"{self.NOTIFICATION_PREFIX} {subject}"
            else:
                # For backend data emails
                if not subject.startswith(self.BACKEND_PREFIX):
                    subject = f"{self.BACKEND_PREFIX} {subject}"
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.credentials['email']
            msg['To'] = recipient
            msg['Subject'] = subject
            
            # Add header to identify Syft emails
            msg['X-Syft-Client'] = 'true'
            msg['X-Syft-Type'] = 'notification' if is_notification else 'backend'
            
            # Handle different data types
            if isinstance(data, str):
                # Plain text
                msg.attach(MIMEText(data, 'plain'))
            elif isinstance(data, dict):
                # JSON data
                import json
                msg.attach(MIMEText(json.dumps(data, indent=2), 'plain'))
            else:
                # Binary data - pickle and attach
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(pickle.dumps(data))
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="syft_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pkl"'
                )
                msg.attach(part)
                
                # Add text explanation
                msg.attach(MIMEText("Syft Client data attached as pickle file.", 'plain'))
            
            # Connect and send
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.credentials['email'], self.credentials['password'])
                server.send_message(msg)
                
            return True
            
        except Exception as e:
            print(f"Error sending email: {e}")
            return False
        
    def receive(self, folder: Optional[str] = None, limit: int = 10, 
                backend_only: bool = False) -> List[Dict[str, Any]]:
        """
        Receive emails via IMAP
        
        Args:
            folder: Optional folder name. If None, uses INBOX or BACKEND_FOLDER based on backend_only
            limit: Maximum number of messages to retrieve
            backend_only: If True, retrieves only from backend folder. If False, from inbox.
        """
        if not self.credentials or not self.imap_server:
            raise ValueError("No credentials available or IMAP not configured.")
            
        messages = []
        
        try:
            # Connect to IMAP
            with imaplib.IMAP4_SSL(self.imap_server, self.imap_port) as imap:
                imap.login(self.credentials['email'], self.credentials['password'])
                
                # Determine folder to use
                if folder is None:
                    folder = self.BACKEND_FOLDER if backend_only else 'INBOX'
                
                # Select folder
                try:
                    status, _ = imap.select(folder)
                    if status != 'OK':
                        # Fall back to INBOX if folder doesn't exist
                        imap.select('INBOX')
                except:
                    # Fall back to INBOX if any error
                    imap.select('INBOX')
                
                # Build search criteria
                search_criteria = 'ALL'
                if not backend_only and folder == 'INBOX':
                    # When reading inbox, optionally filter out backend emails
                    # Note: IMAP search doesn't support NOT with subject patterns well,
                    # so we'll filter in post-processing
                    pass
                
                # Search for messages (most recent first)
                _, data = imap.search(None, search_criteria)
                message_ids = data[0].split()
                
                # Get most recent messages
                for msg_id in reversed(message_ids[-limit:]):
                    _, msg_data = imap.fetch(msg_id, '(RFC822)')
                    
                    # Parse email
                    raw_email = msg_data[0][1]
                    email_message = email_lib.message_from_bytes(raw_email)
                    
                    # Check if this is a backend email
                    subject = email_message.get('Subject', '')
                    is_backend_email = subject.startswith(self.BACKEND_PREFIX)
                    
                    # Filter based on backend_only parameter
                    if backend_only and not is_backend_email:
                        continue  # Skip non-backend emails when backend_only=True
                    elif not backend_only and folder == 'INBOX' and is_backend_email:
                        continue  # Skip backend emails when reading regular inbox
                    
                    # Check if it's a Syft email
                    is_syft_email = (
                        email_message.get('X-Syft-Client', '').lower() == 'true' or
                        subject.startswith(self.NOTIFICATION_PREFIX) or
                        subject.startswith(self.BACKEND_PREFIX)
                    )
                    
                    # Extract message details
                    message = {
                        'id': msg_id.decode(),
                        'from': email_message['From'],
                        'to': email_message['To'],
                        'subject': subject,
                        'date': email_message['Date'],
                        'is_syft': is_syft_email,
                        'is_backend': is_backend_email,
                        'body': None,
                        'attachments': []
                    }
                    
                    # Process message parts
                    for part in email_message.walk():
                        content_type = part.get_content_type()
                        
                        if content_type == 'text/plain':
                            if not message['body']:
                                message['body'] = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        elif content_type == 'text/html':
                            # Skip HTML if we already have plain text
                            if not message['body']:
                                message['body'] = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        elif part.get('Content-Disposition', '').startswith('attachment'):
                            # Handle attachments
                            filename = part.get_filename()
                            if filename:
                                attachment_data = part.get_payload(decode=True)
                                
                                # For backend emails with pickle attachments, try to unpickle
                                unpickled_data = None
                                if is_backend_email and filename.endswith('.pkl'):
                                    try:
                                        unpickled_data = pickle.loads(attachment_data)
                                    except:
                                        pass
                                
                                message['attachments'].append({
                                    'filename': filename,
                                    'size': len(attachment_data),
                                    'data': attachment_data,
                                    'unpickled_data': unpickled_data  # Will be None if not pickle or failed
                                })
                    
                    messages.append(message)
                    
        except Exception as e:
            print(f"Error receiving emails: {e}")
            
        return messages
    
    def send_backend(self, recipient: str, data: Any, subject: str = "Data Transfer") -> bool:
        """
        Send backend data email (automatically prefixed with [SYFT-DATA])
        
        Args:
            recipient: Email address to send to
            data: Data to send (any picklable object)
            subject: Email subject (will be prefixed with [SYFT-DATA])
        """
        return self.send(recipient, data, subject, is_notification=False)
    
    def receive_backend(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Receive backend emails only (from SyftBackend folder or filtered by prefix)
        
        Args:
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of backend email messages with unpickled data where available
        """
        return self.receive(folder=self.BACKEND_FOLDER, limit=limit, backend_only=True)
    
    def send_notification(self, recipient: str, message: str, subject: str = "Notification") -> bool:
        """
        Send human-readable notification email (automatically prefixed with [SYFT])
        
        Args:
            recipient: Email address to send to
            message: Text message to send
            subject: Email subject (will be prefixed with [SYFT])
        """
        return self.send(recipient, message, subject, is_notification=True)