"""Gmail transport layer implementation"""

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
from datetime import datetime
from ..transport_base import BaseTransportLayer
from ...environment import Environment


class GmailTransport(BaseTransportLayer):
    """Gmail transport layer using SMTP/IMAP with app passwords"""
    
    # STATIC Attributes
    is_keystore = True  # Gmail is trusted for storing keys
    is_notification_layer = True  # Users check email regularly
    is_html_compatible = True  # Email supports HTML
    is_reply_compatible = True  # Email has native reply support
    guest_submit = False  # Requires Gmail account
    guest_read_file = False  # Requires authentication
    guest_read_folder = False  # Requires authentication
    
    def __init__(self, email: str, credentials: Optional[Dict[str, Any]] = None):
        """Initialize Gmail transport with credentials"""
        super().__init__(email)
        self.credentials = credentials
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.imap_server = "imap.gmail.com"
        self.imap_port = 993
    
    @property
    def api_is_active_by_default(self) -> bool:
        """App password authentication doesn't require API activation"""
        return True  # Using SMTP/IMAP instead of Gmail API
        
    @property
    def login_complexity(self) -> int:
        """No additional setup needed after app password auth"""
        return 0  # Gmail client already handles authentication
    
    def test_connection(self, email: str, password: str, verbose: bool = False) -> bool:
        """Test Gmail connection with provided credentials"""
        smtp_success = self._test_smtp_connection(email, password, verbose)
        imap_success = self._test_imap_connection(email, password, verbose)
        return smtp_success and imap_success
    
    def _test_smtp_connection(self, email: str, password: str, verbose: bool = False) -> bool:
        """Test SMTP connection with Gmail"""
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as smtp:
                smtp.starttls()
                smtp.login(email, password)
            
            if verbose:
                print("✓ SMTP connection successful")
            return True
        except Exception as e:
            if verbose:
                print(f"✗ SMTP connection failed: {e}")
            return False
    
    def _test_imap_connection(self, email: str, password: str, verbose: bool = False) -> bool:
        """Test IMAP connection with Gmail"""
        try:
            with imaplib.IMAP4_SSL(self.imap_server, self.imap_port) as imap:
                imap.login(email, password)
                imap.logout()
            
            if verbose:
                print("✓ IMAP connection successful")
            return True
        except Exception as e:
            if verbose:
                print(f"✗ IMAP connection failed: {e}")
            return False
    
    def set_credentials(self, email: str, password: str) -> None:
        """Set credentials for the transport"""
        self.credentials = {
            'email': email,
            'password': password
        }
        
    def send(self, recipient: str, data: Any, subject: str = "Syft Client Message") -> bool:
        """Send email via Gmail SMTP"""
        if not self.credentials:
            raise ValueError("No credentials available. Please authenticate first.")
            
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.credentials['email']
            msg['To'] = recipient
            msg['Subject'] = subject
            
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
        
    def receive(self, folder: str = 'INBOX', limit: int = 10) -> List[Dict[str, Any]]:
        """Receive emails from Gmail via IMAP"""
        if not self.credentials:
            raise ValueError("No credentials available. Please authenticate first.")
            
        messages = []
        
        try:
            # Connect to IMAP
            with imaplib.IMAP4_SSL(self.imap_server, self.imap_port) as imap:
                imap.login(self.credentials['email'], self.credentials['password'])
                
                # Select folder
                imap.select(folder)
                
                # Search for messages (most recent first)
                _, data = imap.search(None, 'ALL')
                message_ids = data[0].split()
                
                # Get most recent messages
                for msg_id in reversed(message_ids[-limit:]):
                    _, msg_data = imap.fetch(msg_id, '(RFC822)')
                    
                    # Parse email
                    raw_email = msg_data[0][1]
                    email_message = email_lib.message_from_bytes(raw_email)
                    
                    # Extract message details
                    message = {
                        'id': msg_id.decode(),
                        'from': email_message['From'],
                        'to': email_message['To'],
                        'subject': email_message['Subject'],
                        'date': email_message['Date'],
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
                                message['attachments'].append({
                                    'filename': filename,
                                    'size': len(attachment_data),
                                    'data': attachment_data  # In production, might want to handle this differently
                                })
                    
                    messages.append(message)
                    
        except Exception as e:
            print(f"Error receiving emails: {e}")
            
        return messages