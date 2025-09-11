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
        
        # Initialize all transport layers for this platform
        self._initialize_transport_layers()
    
    def _initialize_transport_layers(self) -> None:
        """Initialize all transport layers for Google Personal"""
        from .gmail import GmailTransport
        from .gdrive_files import GDriveFilesTransport
        from .gsheets import GSheetsTransport
        from .gforms import GFormsTransport
        
        # Create transport instances
        self.transports = {
            'gmail': GmailTransport(self.email),
            'gdrive_files': GDriveFilesTransport(self.email),
            'gsheets': GSheetsTransport(self.email),
            'gforms': GFormsTransport(self.email)
        }
    
    def authenticate(self) -> Dict[str, Any]:
        """Authenticate with personal Gmail using app password"""
        # Get app password from user
        password = self._get_app_password()
        
        # Setup credentials
        credentials = {
            'email': self.email,
            'password': password
        }
        
        # Try to setup all transport layers with low complexity
        successful_transports = []
        failed_transports = []
        
        for transport_name, transport in self.transports.items():
            if transport.login_complexity <= 1:  # Only try simple transports
                try:
                    if transport.setup(credentials):
                        successful_transports.append(transport_name)
                        if self.verbose:
                            print(f"✓ {transport_name} setup successful")
                    else:
                        failed_transports.append(transport_name)
                        if self.verbose:
                            print(f"✗ {transport_name} setup failed")
                except Exception as e:
                    failed_transports.append(transport_name)
                    if self.verbose:
                        print(f"✗ {transport_name} setup error: {e}")
        
        # Check if at least one transport succeeded
        if not successful_transports:
            raise ValueError("Failed to setup any transport layers")
        
        if self.verbose:
            print(f"\n✅ Authentication successful!")
            print(f"Active transports: {', '.join(successful_transports)}")
            if failed_transports:
                print(f"Failed transports: {', '.join(failed_transports)}")
        
        # Return auth data
        return {
            'email': self.email,
            'auth_method': 'app_password',
            'credentials': credentials,
            'active_transports': successful_transports,
            'failed_transports': failed_transports
        }
        
    def get_transport_layers(self) -> List[str]:
        """Get list of available transport layers for personal Gmail"""
        return list(self.transports.keys())
    
    def get_transport_instances(self) -> Dict[str, Any]:
        """Get all instantiated transport layers for this platform"""
        # Return our pre-initialized transports instead of using base class logic
        return self.transports
    
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
    
    def _get_app_password(self) -> str:
        """Get Gmail app password from user"""
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
            raise RuntimeError("Cannot prompt for password in non-interactive mode")
        
        try:
            prompt = " Enter Password: " if not self.verbose else "\nEnter your Google app password (16 characters): "
            password = getpass.getpass(prompt)
        except (EOFError, KeyboardInterrupt):
            raise RuntimeError("Password input cancelled by user")
        
        # Remove spaces from password
        password = password.replace(" ", "")
        
        # Validate password format
        if len(password) != 16:
            raise ValueError(f"Invalid app password length: expected 16 characters, got {len(password)}")
        
        return password
    
    
