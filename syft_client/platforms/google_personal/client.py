"""Google Personal (Gmail) platform client implementation"""

from typing import Any, Dict, List, Optional
import getpass
import json
from ..base import BasePlatformClient


class GooglePersonalClient(BasePlatformClient):
    """Client for personal Gmail accounts"""
    
    def __init__(self, email: str, verbose: bool = False):
        super().__init__(email, verbose=verbose)
        self.platform = "google_personal"
        self._gmail_servers = {
            'smtp': {
                'server': 'smtp.gmail.com',
                'port': 587,
                'ssl': False,
                'starttls': True
            },
            'imap': {
                'server': 'imap.gmail.com',
                'port': 993,
                'ssl': True,
                'starttls': False
            }
        }
    
    def authenticate(self) -> Dict[str, Any]:
        """Authenticate with personal Gmail using app password"""
        return self._authenticate_with_app_password()
        
    def get_transport_layers(self) -> List[str]:
        """Get list of available transport layers for personal Gmail"""
        return [
            'GmailTransport',
            'GDriveFilesTransport', 
            'GSheetsTransport',
            'GFormsTransport'
        ]
    
    @property
    def login_complexity(self) -> int:
        """
        Personal Gmail authentication complexity.
        
        App Password: 3 steps (enable 2FA, generate password, enter it)
        OAuth2: 2 steps (device flow)
        Colab: 1 step (built-in auth)
        """
        from ...environment import Environment
        
        if self.current_environment == Environment.COLAB:
            return 1  # Single step - Colab built-in
        else:
            # App password is simpler than OAuth2 for now
            return 3  # App password steps
    
    def _create_transport_instance(self, transport_name: str) -> Optional[Any]:
        """Create a transport instance with proper credentials if available"""
        transport_instance = super()._create_transport_instance(transport_name)
        
        # If we have auth data and this is Gmail transport, set credentials
        if transport_instance and transport_name == 'GmailTransport' and hasattr(self, '_auth_data'):
            credentials = self._auth_data.get('credentials', {})
            if credentials:
                transport_instance.set_credentials(
                    credentials.get('email', self.email),
                    credentials.get('password')
                )
        
        return transport_instance
    
    
    
    def _authenticate_with_app_password(self) -> Dict[str, Any]:
        """Authenticate using Gmail app password"""
        # Add authuser parameter to ensure correct account
        import urllib.parse
        encoded_email = urllib.parse.quote(self.email)
        app_password_url = f"https://myaccount.google.com/apppasswords?authuser={encoded_email}"
        
        if self.verbose:
            print(f"\n📱 Google App Password required for {self.email}")
            print(f"Generate one at: {app_password_url}")
        else:
            # Minimal output - just the essential URL
            print(f"If you don't have a Google App Password: {app_password_url}")
        
        if not self.is_interactive:
            print("\n❌ Error: Non-interactive mode detected")
            print("App password authentication requires user input.")
            print("Please run in interactive mode or use OAuth2 authentication.")
            raise RuntimeError("Cannot prompt for password in non-interactive mode")
        
        try:
            prompt = " Enter Password: " if not self.verbose else "\nEnter your Google app password (16 characters): "
            password = getpass.getpass(prompt)
        except (EOFError, KeyboardInterrupt):
            if self.verbose:
                print("\n❌ Password input cancelled")
            raise RuntimeError("Password input cancelled by user")
        
        # Remove spaces from password
        password = password.replace(" ", "")
        
        # Validate password format
        if len(password) != 16:
            if self.verbose:
                print(f"\n❌ Error: App passwords should be 16 characters (got {len(password)})")
                print("Please generate a new app password from Google account settings.")
            raise ValueError("Invalid app password length")
        
        if self.verbose:
            print("\n🔍 Testing Gmail connection...")
        
        # Create Gmail transport and test connection
        from .gmail import GmailTransport
        gmail_transport = GmailTransport(self.email)
        
        if gmail_transport.test_connection(self.email, password, verbose=self.verbose):
            if self.verbose:
                print("\n✅ Authentication successful!")
                print("\n💡 Tip: Save your app password in your password manager")
                print("   to avoid re-entering it next time.")
            
            # Return auth data
            auth_data = {
                'email': self.email,
                'auth_method': 'app_password',
                'servers': self._gmail_servers,
                'credentials': {
                    'email': self.email,
                    'password': password
                }
            }
            
            return auth_data
        else:
            if self.verbose:
                print("\n❌ Authentication failed!")
                print("\nPossible issues:")
                print("1. The app password may be incorrect")
                print("2. 2FA might not be enabled on your account")
                print("3. The password might have been revoked")
                print("\nPlease generate a new app password and try again.")
            raise ValueError("Gmail authentication failed")
    
    
