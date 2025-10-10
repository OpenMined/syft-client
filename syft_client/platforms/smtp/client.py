"""SMTP platform client implementation"""

import getpass
import imaplib
import smtplib
import ssl
from typing import Any, Dict, List, Optional

from ..base import BasePlatformClient


class SMTPClient(BasePlatformClient):
    """Generic SMTP client for email servers"""

    def __init__(self, email: str):
        super().__init__(email)
        self.platform = "smtp"
        self.smtp_server: Optional[str] = None
        self.smtp_port: int = 587  # Default TLS port
        self.imap_server: Optional[str] = None
        self.imap_port: int = 993  # Default SSL port
        self._credentials: Optional[Dict[str, str]] = None

    @property
    def login_complexity(self) -> int:
        """
        Return the complexity of the login process.
        SMTP: 2 (requires server configuration + username/password)
        """
        return 2

    def authenticate(self) -> Dict[str, Any]:
        """Authenticate with SMTP server"""
        print(f"\nSMTP Authentication for {self.email}")
        print("=" * 50)

        # Get server details if not provided
        if not self.smtp_server:
            self._get_server_config()

        # Get password
        password = getpass.getpass(f"Password for {self.email}: ")

        # Test SMTP connection
        print("\nTesting SMTP connection...")
        smtp_success = self._test_smtp_connection(self.email, password)

        # Test IMAP connection if server provided
        imap_success = False
        if self.imap_server:
            print("\nTesting IMAP connection...")
            imap_success = self._test_imap_connection(self.email, password)

        if smtp_success:
            self._credentials = {
                "email": self.email,
                "password": password,  # In production, this should be encrypted
                "smtp_server": self.smtp_server,
                "smtp_port": self.smtp_port,
                "imap_server": self.imap_server,
                "imap_port": self.imap_port,
            }

            print("\n✓ Authentication successful!")
            return {
                "authenticated": True,
                "smtp_verified": smtp_success,
                "imap_verified": imap_success,
                "platform": "smtp",
                "email": self.email,
            }
        else:
            raise Exception("SMTP authentication failed")

    def get_transport_layers(self) -> List[str]:
        """Get the transport layers for SMTP (email-based)"""
        return ["SMTPEmailTransport"]

    def _get_server_config(self) -> None:
        """Get SMTP/IMAP server configuration from user"""
        print("\nPlease provide SMTP server details:")
        print(
            "(Common examples: smtp.gmail.com, smtp.mail.yahoo.com, smtp.office365.com)"
        )

        self.smtp_server = input("SMTP server hostname: ").strip()

        # Ask for port with default
        port_input = input(f"SMTP port (default {self.smtp_port}): ").strip()
        if port_input:
            self.smtp_port = int(port_input)

        # Optionally get IMAP config
        if input("\nConfigure IMAP for receiving emails? (y/n): ").lower() == "y":
            self.imap_server = input("IMAP server hostname: ").strip()
            imap_port_input = input(f"IMAP port (default {self.imap_port}): ").strip()
            if imap_port_input:
                self.imap_port = int(imap_port_input)

    def _test_smtp_connection(self, email: str, password: str) -> bool:
        """Test SMTP connection and authentication"""
        try:
            # Create SSL context
            context = ssl.create_default_context()

            # Try connection
            if self.smtp_port == 465:  # SSL
                server = smtplib.SMTP_SSL(
                    self.smtp_server, self.smtp_port, context=context
                )
            else:  # TLS
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()

            # Authenticate
            server.login(email, password)
            print(
                f"✓ SMTP connection successful to {self.smtp_server}:{self.smtp_port}"
            )

            # Clean disconnect
            server.quit()
            return True

        except smtplib.SMTPAuthenticationError:
            print("✗ Authentication failed - check email/password")
            return False
        except Exception as e:
            print(f"✗ SMTP connection failed: {str(e)}")
            return False

    def _test_imap_connection(self, email: str, password: str) -> bool:
        """Test IMAP connection and authentication"""
        try:
            # Connect to IMAP server
            if self.imap_port == 993:  # SSL
                server = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            else:  # Plain
                server = imaplib.IMAP4(self.imap_server, self.imap_port)

            # Authenticate
            server.login(email, password)

            # Test by selecting inbox
            status, data = server.select("INBOX")
            if status == "OK":
                print(
                    f"✓ IMAP connection successful to {self.imap_server}:{self.imap_port}"
                )
                server.close()
                server.logout()
                return True
            else:
                print("✗ Could not select INBOX")
                return False

        except imaplib.IMAP4.error as e:
            print(f"✗ IMAP authentication failed: {str(e)}")
            return False
        except Exception as e:
            print(f"✗ IMAP connection failed: {str(e)}")
            return False
