"""Google Organizational (Workspace) platform client implementation using OAuth2"""

from typing import Any, Dict, List, Optional
import os
import json
from pathlib import Path
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from ..base import BasePlatformClient
from ...auth.wallets import get_wallet_class, LocalFileWallet
from ...environment import Environment

# Try importing Colab auth
try:
    from google.colab import auth as colab_auth
    COLAB_AVAILABLE = True
except ImportError:
    colab_auth = None
    COLAB_AVAILABLE = False


class GoogleOrgClient(BasePlatformClient):
    """Client for Google Workspace (organizational) accounts using OAuth2"""
    
    # OAuth2 scopes for all Google services (same as personal)
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/forms.body'
    ]
    
    def __init__(self, email: str, verbose: bool = False):
        super().__init__(email, verbose=verbose)
        self.platform = "google_org"
        
        # OAuth2 state
        self.credentials: Optional[Credentials] = None
        self.wallet = None
        self.config_path = self.get_config_path()
        
        # Initialize transport layers
        self._initialize_transport_layers()
    
    def _sanitize_email(self) -> str:
        """Sanitize email for use in file paths"""
        return self.email.replace('@', '_at_').replace('.', '_')
    
    def _initialize_transport_layers(self) -> None:
        """Initialize all transport layers for Google Workspace"""
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
    
    # ===== Core Authentication Methods (Main Flow) =====
    
    def authenticate(self) -> Dict[str, Any]:
        """
        Main authentication entry point - orchestrates entire flow.
        
        Flow:
        1. Load wallet configuration
        2. Get or create wallet
        3. Check for cached token
        4. If no token, run OAuth2 flow
        5. If first time, configure wallet
        6. Store token in wallet
        7. If first time, setup transports
        """
        try:
            # Check if we're in Colab and can use automatic auth
            if self.current_environment == Environment.COLAB and COLAB_AVAILABLE:
                # Try Colab authentication first
                if self.authenticate_colab():
                    # For Colab, we still need to setup transports but skip wallet/OAuth2
                    config = self.load_platform_config()
                    is_first_time = not config.get('setup_completed', False)
                    
                    if is_first_time:
                        # Setup transport layers (but only non-Gmail ones will work)
                        if self.verbose:
                            print("\n⚠️  Note: Gmail requires OAuth2 setup and won't work with Colab auth")
                            print("   Other services (Drive, Sheets, Forms) will work automatically")
                        
                        transport_result = self.setup_transport_layers()
                        
                        # Mark setup as completed
                        config['setup_completed'] = datetime.now().isoformat()
                        config['colab_auth'] = True
                        self.save_platform_config(config)
                        
                        successful_transports = transport_result.get('configured', [])
                        failed_transports = transport_result.get('failed', [])
                    else:
                        successful_transports = []
                        failed_transports = []
                    
                    return {
                        'email': self.email,
                        'auth_method': 'colab',
                        'platform': self.platform,
                        'wallet': 'colab_builtin',
                        'active_transports': successful_transports,
                        'failed_transports': failed_transports
                    }
            
            # Regular OAuth2 flow
            # Step 1 & 2: Initialize wallet
            self.wallet = self.get_or_create_wallet()
            
            # Step 3: Check for cached token
            cached_credentials = self.check_cached_token()
            
            if not cached_credentials:
                # Step 4: Run OAuth2 flow
                self.credentials = self.authenticate_oauth2()
                if not self.credentials:
                    raise RuntimeError("OAuth2 authentication failed")
                
                # Note: Token is already stored in wallet by authenticate_oauth2
            
            # Check if this is first time setup
            config = self.load_platform_config()
            is_first_time = not config.get('setup_completed', False)
            
            if is_first_time:
                # Step 5: Configure wallet preference for first-time users
                if not config.get('wallet_config'):
                    self.configure_wallet_preference()
                
                # Step 7: Setup transport layers for first-time users
                transport_result = self.setup_transport_layers()
                
                # Mark setup as completed
                config['setup_completed'] = datetime.now().isoformat()
                self.save_platform_config(config)
                
                successful_transports = transport_result.get('configured', [])
                failed_transports = transport_result.get('failed', [])
            else:
                # For returning users, just verify transports are still working
                successful_transports = []
                failed_transports = []
                
                for transport_name, transport in self.transports.items():
                    if hasattr(transport, 'is_setup') and transport.is_setup():
                        successful_transports.append(transport_name)
                    else:
                        # Try to set it up
                        try:
                            setup_data = {'credentials': self.credentials}
                            if transport.setup(setup_data):
                                successful_transports.append(transport_name)
                            else:
                                failed_transports.append(transport_name)
                        except Exception:
                            failed_transports.append(transport_name)
            
            if not successful_transports:
                raise ValueError("Failed to setup any transport layers")
            
            if self.verbose:
                print(f"\n✅ Authentication complete!")
                print(f"Active transports: {', '.join(successful_transports)}")
            
            return {
                'email': self.email,
                'auth_method': 'oauth2',
                'wallet': self.wallet.name,
                'active_transports': successful_transports,
                'failed_transports': failed_transports
            }
            
        except Exception as e:
            raise RuntimeError(f"Authentication failed: {e}")
    
    def authenticate_oauth2(self) -> Optional[Credentials]:
        """
        Run OAuth2-specific authentication flow.
        
        Returns raw Google credentials object.
        """
        # Step 1: Look for credentials.json
        credentials_file = self.find_oauth_credentials()
        
        # Step 2: Run wizard if needed
        if not credentials_file:
            credentials_file = self.run_oauth_wizard()
            if not credentials_file:
                return None
        
        # Step 3: Execute OAuth2 flow
        try:
            self.credentials = self.execute_oauth_flow(credentials_file)
            
            # Step 4: Convert to token data for storage
            token_data = {
                'token': self.credentials.token,
                'refresh_token': self.credentials.refresh_token,
                'token_uri': self.credentials.token_uri,
                'client_id': self.credentials.client_id,
                'client_secret': self.credentials.client_secret,
                'scopes': self.credentials.scopes,
                'expiry': self.credentials.expiry.isoformat() if self.credentials.expiry else None
            }
            
            # Step 5: Store in wallet
            self.store_token_in_wallet(token_data)
            
            return self.credentials
            
        except Exception as e:
            if self.verbose:
                print(f"✗ OAuth2 flow failed: {e}")
            raise
    
    def authenticate_colab(self) -> bool:
        """
        Authenticate using Google Colab's built-in authentication.
        
        This only works for Google Drive, Sheets, and Forms - NOT Gmail.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not COLAB_AVAILABLE or self.current_environment != Environment.COLAB:
            return False
        
        try:
            if self.verbose:
                print("🔐 Authenticating with Google Colab...")
            
            # Authenticate the Colab user
            colab_auth.authenticate_user()
            
            # Get the email address from Drive API
            from googleapiclient.discovery import build
            service = build('drive', 'v3')
            about = service.about().get(fields="user(emailAddress)").execute()
            authenticated_email = about['user']['emailAddress']
            
            # Verify it matches our expected email
            if authenticated_email != self.email:
                if self.verbose:
                    print(f"⚠️  Colab authenticated as {authenticated_email}, but expected {self.email}")
                return False
            
            if self.verbose:
                print(f"✅ Authenticated via Google Colab as {self.email}")
            
            # Mark as authenticated for non-Gmail transports
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Colab authentication failed: {e}")
            return False
    
    # ===== Wallet Integration Methods =====
    
    def load_wallet_config(self) -> Optional[Dict[str, Any]]:
        """Load wallet configuration from ~/.syft/[email]/config.json"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    return config.get('wallet_config', None)
            return None
        except Exception as e:
            if self.verbose:
                print(f"Failed to load wallet config: {e}")
            return None
    
    def get_or_create_wallet(self) -> Any:  # Returns wallet instance
        """Get configured wallet or create default LocalFileWallet"""
        # Load saved configuration
        config = self.load_wallet_config()
        
        if config:
            # Try to use configured wallet
            try:
                wallet_type = config.get('preferred_wallet', 'local_file')
                wallet_config = config.get('wallet_config', {})
                
                wallet_class = get_wallet_class(wallet_type)
                wallet = wallet_class(wallet_config)
                
                # Test if wallet is accessible
                if wallet.test_connection():
                    if self.verbose:
                        print(f"✓ Using {wallet.name} wallet")
                    return wallet
                else:
                    if self.verbose:
                        print(f"⚠️  {wallet.name} wallet not accessible, falling back to local storage")
            except Exception as e:
                if self.verbose:
                    print(f"⚠️  Failed to initialize configured wallet: {e}")
        
        # Fall back to default LocalFileWallet
        if self.verbose:
            print("Using default local file wallet")
        
        return LocalFileWallet({})
    
    def configure_wallet_preference(self) -> Dict[str, Any]:
        """Interactive wallet selection for first-time users"""
        from ...auth.wallets import AVAILABLE_WALLETS
        
        print("\n🔐 Choose your token storage preference")
        print("=" * 50)
        print("\nTokens allow Syft to access Google services on your behalf.")
        print("Where would you like to store them?\n")
        
        # For now, we only have LocalFileWallet, but show the structure for future wallets
        options = [
            ("1", "local_file", "Local File Storage", "Simple, works everywhere"),
            # Future options:
            # ("2", "1password", "1Password", "Secure, syncs across devices"),
            # ("3", "keychain", "macOS Keychain", "Native Mac integration"),
        ]
        
        for num, key, name, desc in options:
            if key in AVAILABLE_WALLETS:
                print(f"{num}. {name} - {desc}")
        
        # Get user choice
        while True:
            try:
                choice = input("\nYour choice [1]: ").strip() or "1"
                
                # Find the selected wallet
                for num, key, name, desc in options:
                    if choice == num and key in AVAILABLE_WALLETS:
                        wallet_type = key
                        wallet_name = name
                        break
                else:
                    print("Invalid choice. Please try again.")
                    continue
                
                # For now, we only have local_file, so no additional config needed
                wallet_config = {
                    "preferred_wallet": wallet_type,
                    "wallet_config": {},
                    "fallback_wallet": "local_file"
                }
                
                # Save the preference
                self.save_platform_config({"wallet_config": wallet_config})
                
                print(f"\n✓ {wallet_name} configured successfully!")
                print("Future logins will use this storage method.")
                
                return wallet_config
                
            except KeyboardInterrupt:
                print("\n\nWallet configuration cancelled.")
                # Default to local file
                return {
                    "preferred_wallet": "local_file",
                    "wallet_config": {},
                    "fallback_wallet": "local_file"
                }
    
    def store_token_in_wallet(self, token_data: Dict[str, Any]) -> bool:
        """Store OAuth2 token using configured wallet"""
        if not self.wallet:
            self.wallet = self.get_or_create_wallet()
        
        try:
            success = self.wallet.store_token(
                service=self.platform,
                account=self.email,
                token_data=token_data
            )
            
            if success and self.verbose:
                print(f"✓ Token stored in {self.wallet.name}")
            
            return success
        except Exception as e:
            if self.verbose:
                print(f"✗ Failed to store token: {e}")
            return False
    
    def load_token_from_wallet(self) -> Optional[Dict[str, Any]]:
        """Retrieve OAuth2 token from configured wallet"""
        if not self.wallet:
            self.wallet = self.get_or_create_wallet()
        
        try:
            token_data = self.wallet.retrieve_token(
                service=self.platform,
                account=self.email
            )
            
            if token_data and self.verbose:
                print(f"✓ Token loaded from {self.wallet.name}")
            
            return token_data
        except Exception as e:
            if self.verbose:
                print(f"✗ Failed to load token: {e}")
            return None
    
    # ===== Token Management Methods =====
    
    def check_cached_token(self) -> Optional[Credentials]:
        """Check for existing valid token in wallet"""
        # Try to load token from wallet
        token_data = self.load_token_from_wallet()
        
        if not token_data:
            return None
        
        try:
            # Convert to Google Credentials object
            self.credentials = Credentials.from_authorized_user_info(token_data, self.SCOPES)
            
            # Check if token is valid
            if self.validate_token():
                return self.credentials
            
            # Try to refresh if expired
            if self.refresh_token_if_needed():
                return self.credentials
            
            return None
        except Exception as e:
            if self.verbose:
                print(f"Failed to load cached token: {e}")
            return None
    
    def refresh_token_if_needed(self) -> bool:
        """Refresh token if expired, update in wallet"""
        if not self.credentials:
            return False
        
        try:
            # Check if token needs refresh
            if self.credentials.expired:
                if self.verbose:
                    print("Token expired, refreshing...")
                
                # Refresh the token
                self.credentials.refresh(Request())
                
                # Save refreshed token back to wallet
                token_data = {
                    'token': self.credentials.token,
                    'refresh_token': self.credentials.refresh_token,
                    'token_uri': self.credentials.token_uri,
                    'client_id': self.credentials.client_id,
                    'client_secret': self.credentials.client_secret,
                    'scopes': self.credentials.scopes,
                    'expiry': self.credentials.expiry.isoformat() if self.credentials.expiry else None
                }
                
                if self.store_token_in_wallet(token_data):
                    if self.verbose:
                        print("✓ Token refreshed and saved")
                    return True
                else:
                    if self.verbose:
                        print("✗ Failed to save refreshed token")
                    return False
            
            return True  # Token is still valid
            
        except Exception as e:
            if self.verbose:
                print(f"Failed to refresh token: {e}")
            return False
    
    def validate_token(self) -> bool:
        """Test if current token works with simple API call"""
        if not self.credentials:
            return False
        
        try:
            # Try a simple API call to validate the token
            # We'll use the Gmail API to get user profile
            from googleapiclient.discovery import build
            
            service = build('gmail', 'v1', credentials=self.credentials)
            result = service.users().getProfile(userId='me').execute()
            
            if self.verbose:
                print(f"✓ Token validated for: {result.get('emailAddress', self.email)}")
            
            return True
        except Exception as e:
            if self.verbose:
                print(f"✗ Token validation failed: {e}")
            return False
    
    # ===== Credentials & Wizard Methods =====
    
    def find_oauth_credentials(self) -> Optional[Path]:
        """Locate OAuth2 app credentials (credentials.json)"""
        # Check email-specific directory first
        email_dir = Path.home() / ".syft" / self._sanitize_email()
        
        possible_paths = [
            email_dir / "credentials.json",  # Email-specific location (preferred)
            Path.home() / ".syft" / "credentials.json",  # Legacy location
            Path.home() / ".syft" / "google_oauth" / "credentials.json",  # Old location
            Path("credentials.json"),  # Current directory fallback
        ]
        
        for path in possible_paths:
            if path.exists():
                if self.verbose:
                    print(f"✓ Found credentials at: {path}")
                return path
        
        if self.verbose:
            print("✗ No credentials.json found")
            print(f"   Expected location: {email_dir / 'credentials.json'}")
        return None
    
    def run_oauth_wizard(self) -> Optional[Path]:
        """Run interactive wizard to create OAuth2 app credentials"""
        from .wizard import check_or_create_credentials
        
        if self.verbose:
            print("\n🔧 OAuth2 credentials not found. Starting setup wizard...")
        
        # Run the wizard
        creds_file = check_or_create_credentials(self.email, self.verbose, is_workspace=True)
        
        if not creds_file:
            if self.verbose:
                print("✗ OAuth2 setup cancelled or failed")
            return None
        
        return creds_file
    
    def wizard(self) -> None:
        """Public entry point for manual wizard launch"""
        from .wizard import create_oauth2_wizard
        create_oauth2_wizard(self.email, verbose=True, is_workspace=True)
    
    # ===== OAuth2 Flow Methods =====
    
    def execute_oauth_flow(self, credentials_file: Path) -> Credentials:
        """Execute OAuth2 browser flow and return credentials"""
        if self.verbose:
            print(f"\n🔐 Starting OAuth2 authentication for {self.email}")
            print("A browser window will open for Google sign-in...")
            print("\n⚠️  Google Workspace accounts may require admin consent")
        
        # Create the flow
        flow = self.create_oauth_client(credentials_file)
        
        # Run the local server to handle the OAuth2 callback
        self.credentials = flow.run_local_server(port=0)
        
        if self.verbose:
            print("✓ OAuth2 authentication successful")
        
        return self.credentials
    
    def create_oauth_client(self, credentials_file: Path) -> InstalledAppFlow:
        """Create OAuth2 flow object for testing/mocking"""
        return InstalledAppFlow.from_client_secrets_file(
            str(credentials_file), 
            self.SCOPES
        )
    
    # ===== Transport Setup Methods =====
    
    def setup_transport_layers(self) -> Dict[str, Any]:
        """Interactive transport setup for first-time users"""
        print("\n🚀 Let's set up your Google Workspace services!")
        print("=" * 50)
        
        # Get available transports
        available = self.show_available_transports()
        
        # Show what's available
        print("\nAvailable services:")
        for i, transport in enumerate(available, 1):
            status = "✓ Configured" if transport['configured'] else "○ Not configured"
            required = " (Required)" if transport['required'] else ""
            print(f"\n{i}. {transport['name']}{required} - {status}")
            print(f"   {transport['description']}")
            print(f"   Features: {', '.join(transport['features'])}")
        
        # Quick setup options
        print("\n\nQuick setup options:")
        print("1. Basic - Gmail only (recommended for testing)")
        print("2. Standard - Gmail + Google Drive")
        print("3. Full - All services")
        print("4. Custom - Choose individually")
        print("5. Skip for now")
        
        choice = input("\nYour choice [2]: ").strip() or "2"
        
        transports_to_setup = []
        if choice == "1":
            transports_to_setup = ['gmail']
        elif choice == "2":
            transports_to_setup = ['gmail', 'gdrive_files']
        elif choice == "3":
            transports_to_setup = ['gmail', 'gdrive_files', 'gsheets', 'gforms']
        elif choice == "4":
            # Custom selection
            print("\nSelect services to set up (comma-separated numbers):")
            for i, transport in enumerate(available, 1):
                print(f"{i}. {transport['name']}")
            
            selections = input("\nYour selections: ").strip()
            if selections:
                try:
                    indices = [int(x.strip()) - 1 for x in selections.split(',')]
                    transports_to_setup = [available[i]['id'] for i in indices if 0 <= i < len(available)]
                except:
                    print("Invalid selection, using default (Gmail only)")
                    transports_to_setup = ['gmail']
        else:
            print("\nSkipping transport setup. You can configure them later.")
            return {'configured': [], 'skipped': [t['id'] for t in available]}
        
        # Set up selected transports
        configured = []
        failed = []
        
        for transport_id in transports_to_setup:
            if self.setup_transport(transport_id):
                configured.append(transport_id)
            else:
                failed.append(transport_id)
        
        # Summary
        print(f"\n✅ Setup complete!")
        if configured:
            print(f"Configured: {', '.join(configured)}")
        if failed:
            print(f"Failed: {', '.join(failed)}")
        
        return {
            'configured': configured,
            'failed': failed,
            'skipped': [t['id'] for t in available if t['id'] not in configured + failed]
        }
    
    def check_transport_status(self) -> Dict[str, Dict[str, Any]]:
        """Check configuration status of all transports"""
        status = {}
        
        # Load saved config
        config = self.load_platform_config()
        transport_config = config.get('transports', {})
        
        for transport_name, transport in self.transports.items():
            status[transport_name] = {
                'name': transport.__class__.__name__,
                'configured': False,
                'active': False,
                'features': []
            }
            
            # Check if transport has been set up
            if hasattr(transport, '_setup_verified'):
                status[transport_name]['configured'] = transport._setup_verified
                status[transport_name]['active'] = transport._setup_verified
            
            # Add saved config info
            if transport_name in transport_config:
                status[transport_name].update(transport_config[transport_name])
            
            # Get transport features
            if hasattr(transport, 'is_notification_layer'):
                if transport.is_notification_layer:
                    status[transport_name]['features'].append('notifications')
            if hasattr(transport, 'is_keystore'):
                if transport.is_keystore:
                    status[transport_name]['features'].append('keystore')
            if hasattr(transport, 'is_html_compatible'):
                if transport.is_html_compatible:
                    status[transport_name]['features'].append('html')
                    
        return status
    
    def show_available_transports(self) -> List[Dict[str, Any]]:
        """List available transports with descriptions and status"""
        transport_info = {
            'gmail': {
                'name': 'Gmail',
                'description': 'Send and receive emails with attachments',
                'features': ['Email notifications', 'Backend data transfer', 'HTML support'],
                'setup_complexity': 1,  # Needs label/filter creation
                'required': True
            },
            'gdrive_files': {
                'name': 'Google Drive',
                'description': 'Store and share files in the cloud',
                'features': ['File upload/download', 'Folder organization', 'Sharing'],
                'setup_complexity': 0,  # Just folder creation
                'required': False
            },
            'gsheets': {
                'name': 'Google Sheets',
                'description': 'Create and manage spreadsheets',
                'features': ['Data tables', 'CSV export', 'Public sharing'],
                'setup_complexity': 0,  # No setup needed
                'required': False
            },
            'gforms': {
                'name': 'Google Forms',
                'description': 'Create forms for data collection',
                'features': ['Dynamic forms', 'Response collection'],
                'setup_complexity': 0,  # No setup needed
                'required': False
            }
        }
        
        # Get current status
        status = self.check_transport_status()
        
        # Build transport list
        transports = []
        for transport_id, info in transport_info.items():
            transport_data = {
                'id': transport_id,
                'name': info['name'],
                'description': info['description'],
                'features': info['features'],
                'setup_complexity': info['setup_complexity'],
                'required': info.get('required', False),
                'configured': status.get(transport_id, {}).get('configured', False),
                'active': status.get(transport_id, {}).get('active', False)
            }
            transports.append(transport_data)
            
        return transports
    
    def setup_transport(self, name: str) -> bool:
        """Configure a specific transport"""
        if name not in self.transports:
            if self.verbose:
                print(f"✗ Unknown transport: {name}")
            return False
        
        transport = self.transports[name]
        
        # Check if already configured
        if hasattr(transport, 'is_setup') and transport.is_setup():
            if self.verbose:
                print(f"✓ {name} is already configured!")
            return True
        
        if self.verbose:
            print(f"\nSetting up {name}...")
        
        # Ensure we have credentials
        if not self.credentials:
            if self.verbose:
                print("✗ No credentials available. Please authenticate first.")
            return False
        
        # Call the transport's setup method
        try:
            setup_data = {'credentials': self.credentials}
            success = transport.setup(setup_data)
            
            if success:
                if self.verbose:
                    print(f"✓ {name} setup successful")
                
                # Update config
                config = self.load_platform_config()
                if 'transports' not in config:
                    config['transports'] = {}
                
                config['transports'][name] = {
                    'configured': True,
                    'configured_at': datetime.now().isoformat(),
                    'active': True
                }
                self.save_platform_config(config)
                
            else:
                if self.verbose:
                    print(f"✗ {name} setup failed")
            
            return success
            
        except Exception as e:
            if self.verbose:
                print(f"✗ {name} setup error: {e}")
            return False
    
    def configure_transports(self) -> Dict[str, Any]:
        """Interactive wizard for adding transports later"""
        print("\n🔧 Transport Configuration")
        print("=" * 50)
        
        # Check current status
        status = self.check_transport_status()
        available = self.show_available_transports()
        
        configured = [t for t in available if t['configured']]
        not_configured = [t for t in available if not t['configured']]
        
        if configured:
            print("\n✅ Currently configured:")
            for t in configured:
                print(f"   • {t['name']}")
        
        if not not_configured:
            print("\n✓ All transports are already configured!")
            reconfigure = input("\nWould you like to reconfigure any? (y/n): ").lower()
            if reconfigure != 'y':
                return {'message': 'All transports already configured'}
            # Show all for reconfiguration
            not_configured = available
        else:
            print("\n○ Not yet configured:")
            for t in not_configured:
                print(f"   • {t['name']} - {t['description']}")
        
        print("\nWhich would you like to set up?")
        for i, transport in enumerate(not_configured, 1):
            print(f"{i}. {transport['name']}")
        print("0. Cancel")
        
        choice = input("\nSelect (0-{}): ".format(len(not_configured))).strip()
        
        if choice == "0" or not choice:
            print("Configuration cancelled.")
            return {'cancelled': True}
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(not_configured):
                transport = not_configured[idx]
                if self.setup_transport(transport['id']):
                    print(f"\n✓ {transport['name']} configured successfully!")
                    
                    # Ask if they want to configure more
                    more = input("\nConfigure another transport? (y/n): ").lower()
                    if more == 'y':
                        return self.configure_transports()  # Recursive call
                    
                    return {'configured': [transport['id']]}
                else:
                    return {'failed': [transport['id']]}
            else:
                print("Invalid selection.")
                return {'error': 'Invalid selection'}
                
        except ValueError:
            print("Invalid input.")
            return {'error': 'Invalid input'}
    
    # ===== Configuration Methods =====
    
    def load_platform_config(self) -> Dict[str, Any]:
        """Load all platform settings from config file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            if self.verbose:
                print(f"Failed to load platform config: {e}")
            return {}
    
    def save_platform_config(self, config: Dict[str, Any]) -> None:
        """Save wallet and transport preferences"""
        try:
            # Load existing config
            existing_config = self.load_platform_config()
            
            # Merge with new config
            existing_config.update(config)
            
            # Add metadata
            existing_config['last_updated'] = datetime.now().isoformat()
            existing_config['platform'] = self.platform
            existing_config['email'] = self.email
            
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save config
            with open(self.config_path, 'w') as f:
                json.dump(existing_config, f, indent=2)
            
            # Set secure permissions
            self.config_path.chmod(0o600)
            
            if self.verbose:
                print(f"✓ Configuration saved to {self.config_path}")
                
        except Exception as e:
            if self.verbose:
                print(f"Failed to save platform config: {e}")
            raise
    
    def get_config_path(self) -> Path:
        """Get path to platform config file"""
        return Path.home() / ".syft" / self._sanitize_email() / "config.json"
    
    # ===== Legacy/Existing Methods (To be refactored) =====
    
    def get_transport_layers(self) -> List[str]:
        """Get list of available transport layers"""
        return list(self.transports.keys())
    
    def get_transport_instances(self) -> Dict[str, Any]:
        """Get all instantiated transport layers for this platform"""
        return self.transports
    
    @property
    def login_complexity(self) -> int:
        """OAuth2 authentication complexity for Google Workspace"""
        from ...environment import Environment
        
        # Check for cached credentials
        if self._has_cached_credentials():
            return 0
            
        if self.current_environment == Environment.COLAB:
            return 1  # Single step - Colab built-in OAuth
        else:
            # OAuth2 flow required with possible admin consent
            return 3  # OAuth2 redirect + admin consent
    
    def _has_cached_credentials(self) -> bool:
        """Check if we have cached OAuth2 tokens"""
        try:
            # Quick check without full wallet initialization
            wallet = LocalFileWallet({})
            token_data = wallet.retrieve_token(
                service=self.platform,
                account=self.email
            )
            return token_data is not None
        except:
            return False