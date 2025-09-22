"""
SyftClient class - Main client object that manages platforms and transport layers
"""

from typing import Dict, List, Optional, Any
from .platforms.base import BasePlatformClient
from .platforms.detection import Platform, detect_primary_platform, get_secondary_platforms, PlatformDetector
from .environment import Environment, detect_environment


class SyftClient:
    """
    Main client object that manages multiple platforms for a single email
    
    A SyftClient represents an authenticated session for a single email account
    that can have multiple platforms (e.g., Gmail + Dropbox with same email).
    """
    
    def __init__(self, email: str):
        """
        Initialize a SyftClient for a specific email
        
        Args:
            email: The email address for this client
        """
        self.email = email
        self._platforms: Dict[str, BasePlatformClient] = {}
        self.transport_instances: Dict[str, Any] = {}  # platform:transport -> instance
        
    @property
    def platforms(self):
        """Provide attribute-style access to platforms"""
        class PlatformRegistry:
            def __init__(self, platforms_dict):
                self._platforms = platforms_dict
                self._parent_client = self  # Reference to parent SyftClient
            
            def __getattr__(self, name):
                if name in self._platforms:
                    return self._platforms[name]
                raise AttributeError(f"'platforms' object has no attribute '{name}'")
            
            def __getitem__(self, key):
                return self._platforms[key]
            
            def __contains__(self, key):
                return key in self._platforms
            
            def items(self):
                return self._platforms.items()
            
            def keys(self):
                return self._platforms.keys()
            
            def values(self):
                return self._platforms.values()
            
            def get(self, key, default=None):
                return self._platforms.get(key, default)
            
            def __dir__(self):
                """Support tab completion for platform names"""
                # Include dict methods and platform names
                return list(self._platforms.keys()) + ['items', 'keys', 'values', 'get']
            
            def __repr__(self):
                """String representation showing platforms and their transports"""
                from rich.console import Console
                from rich.table import Table
                from rich.panel import Panel
                from io import StringIO
                
                # Create a string buffer to capture the rich output
                string_buffer = StringIO()
                console = Console(file=string_buffer, force_terminal=True, width=100)
                
                # Create main table with single column for better formatting
                main_table = Table(show_header=False, show_edge=False, box=None, padding=0)
                main_table.add_column("", no_wrap=False)
                
                # Add each platform with its transports
                for platform_name, platform in self._platforms.items():
                    # Platform header with project info
                    platform_header = f"[bold yellow].{platform_name}[/bold yellow]"
                    
                    # Try to get project ID from credentials or auth data
                    project_info = ""
                    if platform_name in ['google_personal', 'google_org']:
                        # For Google Org, check if project_id is already loaded
                        if platform_name == 'google_org' and hasattr(platform, 'project_id') and platform.project_id:
                            project_info = f" [dim](project: {platform.project_id})[/dim]"
                        else:
                            # Try to get project ID from credentials file
                            try:
                                creds_path = None
                                if hasattr(platform, 'find_oauth_credentials'):
                                    creds_path = platform.find_oauth_credentials()
                                elif hasattr(platform, 'credentials_path'):
                                    creds_path = platform.credentials_path
                                
                                if creds_path and creds_path.exists():
                                    import json
                                    with open(creds_path, 'r') as f:
                                        creds_data = json.load(f)
                                        if 'installed' in creds_data:
                                            project_id = creds_data['installed'].get('project_id')
                                            if project_id:
                                                project_info = f" [dim](project: {project_id})[/dim]"
                            except:
                                pass
                    
                    main_table.add_row(platform_header + project_info)
                    
                    # Get all available transport names (including uninitialized)
                    transport_names = platform.get_transport_layers()
                    
                    for transport_name in transport_names:
                        # Initialize status indicators
                        api_status = "[red]✗[/red]"  # Default to not enabled
                        auth_status = "[dim]✗[/dim]"  # Not authenticated by default
                        transport_style = "dim"
                        message = ""
                        
                        # Check if transport is actually initialized and setup
                        transport_initialized = False
                        if hasattr(platform, 'transports') and transport_name in platform.transports:
                            transport = platform.transports[transport_name]
                            # Check if this is an initialized transport (not a stub)
                            if hasattr(transport, '_setup_called') and transport._setup_called:
                                transport_initialized = True
                                auth_status = "[green]✓[/green]"
                            elif hasattr(transport, 'is_setup') and callable(transport.is_setup):
                                # For fully initialized transports, check is_setup
                                try:
                                    if transport.is_setup():
                                        transport_initialized = True
                                        auth_status = "[green]✓[/green]"
                                except:
                                    pass
                        
                        # Use static method to check API status
                        # This works regardless of whether transport is initialized
                        transport_map = None
                        if platform_name == 'google_personal':
                            # Import the transport classes to use their static methods
                            transport_map = {
                                'gmail': 'syft_client.platforms.google_personal.gmail.GmailTransport',
                                'gdrive_files': 'syft_client.platforms.google_personal.gdrive_files.GDriveFilesTransport',
                                'gsheets': 'syft_client.platforms.google_personal.gsheets.GSheetsTransport',
                                'gforms': 'syft_client.platforms.google_personal.gforms.GFormsTransport'
                            }
                        elif platform_name == 'google_org':
                            # Import the transport classes to use their static methods
                            transport_map = {
                                'gmail': 'syft_client.platforms.google_org.gmail.GmailTransport',
                                'gdrive_files': 'syft_client.platforms.google_org.gdrive_files.GDriveFilesTransport',
                                'gsheets': 'syft_client.platforms.google_org.gsheets.GSheetsTransport',
                                'gforms': 'syft_client.platforms.google_org.gforms.GFormsTransport'
                            }
                            
                        if transport_map and transport_name in transport_map:
                                try:
                                    # Import the transport class
                                    module_path, class_name = transport_map[transport_name].rsplit('.', 1)
                                    module = __import__(module_path, fromlist=[class_name])
                                    transport_class = getattr(module, class_name)
                                    
                                    # Call static method to check API
                                    if transport_class.check_api_enabled(platform):
                                        api_status = "[green]✓[/green]"
                                        transport_style = "green"
                                    else:
                                        api_status = "[red]✗[/red]"
                                        transport_style = "dim"
                                        # If API is disabled, show enable message
                                        message = f" [dim](call .{transport_name}.enable_api())[/dim]"
                                except Exception as e:
                                    # If check fails, see if it's an API disabled error
                                    if "has not been used in project" in str(e) and "before or it is disabled" in str(e):
                                        api_status = "[red]✗[/red]"
                                        message = f" [dim](call .{transport_name}.enable_api())[/dim]"
                        
                        # Set message based on transport initialization status
                        if not transport_initialized:
                            # Transport is not initialized
                            if api_status == "[green]✓[/green]":
                                # API is enabled but transport not initialized
                                message = " [dim](call .init() to initialize)[/dim]" if message == "" else message
                            else:
                                # API is disabled and transport not initialized
                                if message == "":
                                    message = " [dim](not initialized)[/dim]"
                        
                        # Show both statuses
                        main_table.add_row(f"  {api_status} {auth_status} [{transport_style}].{transport_name}[/{transport_style}]{message}")
                
                # Create the panel
                panel = Panel(
                    main_table,
                    title="Platforms",
                    expand=False,
                    width=100,
                    padding=(1, 2)
                )
                
                console.print(panel)
                output = string_buffer.getvalue()
                string_buffer.close()
                
                return output.strip()
                
        return PlatformRegistry(self._platforms)
    
    def _initialize_all_transports(self) -> None:
        """Initialize transport instances for all possible platforms"""
        from .platforms import get_platform_client
        
        # Initialize transports for secondary platforms
        for platform in get_secondary_platforms():
            try:
                platform_client = get_platform_client(platform, self.email)
                self._add_platform_transports(platform.value, platform_client)
            except:
                pass  # Skip if platform client can't be created
    
    def _add_platform_transports(self, platform_name: str, platform_client: BasePlatformClient) -> None:
        """Add transport instances from a platform client to our registry"""
        platform_transports = platform_client.get_transport_instances()
        
        for transport_name, transport_instance in platform_transports.items():
            key = f"{platform_name}:{transport_name}"
            self.transport_instances[key] = transport_instance
    
    def add_platform(self, platform_client: BasePlatformClient, auth_data: Dict[str, Any]) -> None:
        """
        Add an authenticated platform to this client
        
        Args:
            platform_client: The authenticated platform client
            auth_data: Authentication data from the platform
        """
        platform_name = platform_client.platform
        self._platforms[platform_name] = platform_client
        
        # Store auth data in the platform client for now
        platform_client._auth_data = auth_data
        
        # Add transports from this platform
        self._add_platform_transports(platform_name, platform_client)
    
    @property
    def platform_names(self) -> List[str]:
        """Get list of authenticated platform names"""
        return list(self._platforms.keys())
    
    def get_platform(self, platform_name: str) -> Optional[BasePlatformClient]:
        """Get a specific platform client by name"""
        return self._platforms.get(platform_name)
    
    def __getattr__(self, name: str):
        """Allow attribute-style access to platforms"""
        # First check if it's a platform
        if name in self._platforms:
            return self._platforms[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
    def get_transports(self, platform_name: str) -> List[str]:
        """Get transport layers for a specific platform"""
        platform = self.get_platform(platform_name)
        return platform.get_transport_layers() if platform else []
    
    @property
    def all_transports(self) -> Dict[str, List[str]]:
        """Get all transport layers grouped by platform"""
        return {
            platform_name: platform.get_transport_layers()
            for platform_name, platform in self._platforms.items()
        }
    
    @property
    def one_step_transports(self) -> List[str]:
        """Get list of transport layers that are one step from being logged in (login_complexity == 1)"""
        one_step = []
        
        # Simply iterate through all instantiated transports
        for key, transport_instance in self.transport_instances.items():
            if hasattr(transport_instance, 'login_complexity') and transport_instance.login_complexity == 1:
                one_step.append(key)
        
        return one_step
    
    def __repr__(self) -> str:
        """String representation using rich for proper formatting"""
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from io import StringIO
        
        # Create a string buffer to capture the rich output
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=100)
        
        # Create main table with single column for better formatting
        main_table = Table(show_header=False, show_edge=False, box=None, padding=0)
        main_table.add_column("", no_wrap=False)
        
        # Add folder path
        from pathlib import Path
        syft_folder = Path.home() / "SyftBox" / self.email.replace('@', '_at_').replace('.', '_')
        main_table.add_row(f"[dim].folder[/dim] = {syft_folder}")
        
        # Add platforms section
        main_table.add_row("")  # Empty row for spacing
        main_table.add_row("[dim].platforms[/dim]")
        
        # Add each platform with its transports
        for platform_name, platform in self._platforms.items():
            # Platform header with project info
            platform_header = f"  [bold yellow].{platform_name}[/bold yellow]"
            
            # Try to get project ID from credentials or auth data
            project_info = ""
            if platform_name in ['google_personal', 'google_org']:
                # For Google Org, check if project_id is already loaded
                if platform_name == 'google_org' and hasattr(platform, 'project_id') and platform.project_id:
                    project_info = f" [dim](project: {platform.project_id})[/dim]"
                else:
                    # Try to get project ID from credentials file
                    try:
                        creds_path = None
                        if hasattr(platform, 'find_oauth_credentials'):
                            creds_path = platform.find_oauth_credentials()
                        elif hasattr(platform, 'credentials_path'):
                            creds_path = platform.credentials_path
                        
                        if creds_path and Path(creds_path).exists():
                            import json
                            with open(creds_path, 'r') as f:
                                creds_data = json.load(f)
                                if 'installed' in creds_data:
                                    project_id = creds_data['installed'].get('project_id')
                                    if project_id:
                                        project_info = f" [dim](project: {project_id})[/dim]"
                    except:
                        pass
            
            main_table.add_row(platform_header + project_info)
            
            # Get all available transport names (including uninitialized)
            transport_names = platform.get_transport_layers()
            
            for transport_name in transport_names:
                # Initialize status indicators
                api_status = "[red]✗[/red]"  # Default to not enabled
                auth_status = "[dim]✗[/dim]"  # Not authenticated by default
                transport_style = "dim"
                message = ""
                
                # Check if transport is actually initialized and setup
                transport_initialized = False
                if hasattr(platform, 'transports') and transport_name in platform.transports:
                    transport = platform.transports[transport_name]
                    # Check if this is an initialized transport (not a stub)
                    if hasattr(transport, '_setup_called') and transport._setup_called:
                        transport_initialized = True
                        auth_status = "[green]✓[/green]"
                    elif hasattr(transport, 'is_setup') and callable(transport.is_setup):
                        # For fully initialized transports, check is_setup
                        try:
                            if transport.is_setup():
                                transport_initialized = True
                                auth_status = "[green]✓[/green]"
                        except:
                            pass
                
                # Use static method to check API status
                # This works regardless of whether transport is initialized
                transport_map = None
                if platform_name == 'google_personal':
                    # Import the transport classes to use their static methods
                    transport_map = {
                        'gmail': 'syft_client.platforms.google_personal.gmail.GmailTransport',
                        'gdrive_files': 'syft_client.platforms.google_personal.gdrive_files.GDriveFilesTransport',
                        'gsheets': 'syft_client.platforms.google_personal.gsheets.GSheetsTransport',
                        'gforms': 'syft_client.platforms.google_personal.gforms.GFormsTransport'
                    }
                elif platform_name == 'google_org':
                    # Import the transport classes to use their static methods
                    transport_map = {
                        'gmail': 'syft_client.platforms.google_org.gmail.GmailTransport',
                        'gdrive_files': 'syft_client.platforms.google_org.gdrive_files.GDriveFilesTransport',
                        'gsheets': 'syft_client.platforms.google_org.gsheets.GSheetsTransport',
                        'gforms': 'syft_client.platforms.google_org.gforms.GFormsTransport'
                    }
                    
                if transport_map and transport_name in transport_map:
                        try:
                            # Import the transport class
                            module_path, class_name = transport_map[transport_name].rsplit('.', 1)
                            module = __import__(module_path, fromlist=[class_name])
                            transport_class = getattr(module, class_name)
                            
                            # Call static method to check API
                            if transport_class.check_api_enabled(platform):
                                api_status = "[green]✓[/green]"
                                transport_style = "green"
                            else:
                                api_status = "[red]✗[/red]"
                                transport_style = "dim"
                                # If API is disabled, show enable message
                                message = f" [dim](call .{transport_name}.enable_api())[/dim]"
                        except Exception as e:
                            # If check fails, see if it's an API disabled error
                            if "has not been used in project" in str(e) and "before or it is disabled" in str(e):
                                api_status = "[red]✗[/red]"
                                message = f" [dim](call .{transport_name}.enable_api())[/dim]"
                
                # Set message based on transport initialization status
                if not transport_initialized:
                    # Transport is not initialized
                    if api_status == "[green]✓[/green]":
                        # API is enabled but transport not initialized
                        message = " [dim](call .init() to initialize)[/dim]" if message == "" else message
                    else:
                        # API is disabled and transport not initialized
                        if message == "":
                            message = " [dim](not initialized)[/dim]"
                
                # Show both statuses
                main_table.add_row(f"    {api_status} {auth_status} [{transport_style}].{transport_name}[/{transport_style}]{message}")
        
        # Create the panel
        panel = Panel(
            main_table,
            title=f"SyftClient.email = '{self.email}'",
            expand=False,
            width=100,
            padding=(1, 2)
        )
        
        console.print(panel)
        output = string_buffer.getvalue()
        string_buffer.close()
        
        return output.strip()
    
    
    def __str__(self) -> str:
        """User-friendly string representation"""
        lines = [f"SyftClient - {self.email}"]
        for platform_name, platform in self._platforms.items():
            transports = platform.get_transport_layers()
            lines.append(f"  • {platform_name}: {', '.join(transports)}")
        return "\n".join(lines)
    
    def reset_wallet(self, confirm: bool = True) -> bool:
        """
        Reset the wallet by deleting all stored credentials and tokens.
        
        Args:
            confirm: If True, ask for confirmation before deleting (default: True)
            
        Returns:
            bool: True if wallet was reset, False if cancelled
        """
        from pathlib import Path
        import shutil
        
        # Get wallet directory path
        wallet_dir = Path.home() / ".syft"
        
        if not wallet_dir.exists():
            print("No wallet directory found at ~/.syft")
            return True
        
        if confirm:
            # Show what will be deleted
            print(f"\n⚠️  WARNING: This will delete all stored credentials!")
            print(f"\nWallet directory: {wallet_dir}")
            
            # Count files that will be deleted
            file_count = sum(1 for _ in wallet_dir.rglob('*') if _.is_file())
            if file_count > 0:
                print(f"Files to be deleted: {file_count}")
                
                # Show some example files
                example_files = list(wallet_dir.rglob('*'))[:5]
                for f in example_files:
                    if f.is_file():
                        print(f"  - {f.relative_to(wallet_dir)}")
                if file_count > 5:
                    print(f"  ... and {file_count - 5} more files")
            
            response = input("\nAre you sure you want to delete all wallet data? (yes/no): ")
            if response.lower() != 'yes':
                print("Wallet reset cancelled.")
                return False
        
        try:
            # Delete the entire wallet directory
            shutil.rmtree(wallet_dir)
            print(f"\n✓ Wallet directory deleted: {wallet_dir}")
            print("All stored credentials have been removed.")
            print("\nYou will need to authenticate again on your next login.")
            return True
        except Exception as e:
            print(f"\n✗ Error deleting wallet: {e}")
            return False
    
    def _login(self, provider: Optional[str] = None, verbose: bool = False, init_transport: bool = True, wizard: Optional[bool] = None) -> None:
        """
        Instance method that handles the actual login process
        
        Args:
            provider: Optional provider override
            verbose: Whether to print progress
            init_transport: Whether to initialize transport layers
            wizard: Whether to run interactive setup wizard
            
        Raises:
            Exception: If authentication fails
        """
        # Step 1: login(email) is called
        if verbose:
            print(f"Logging in as {self.email}...")
        
        # Step 2: Platform detection (includes unknown platform handling and support validation)
        platform = detect_primary_platform(self.email, provider)
        if verbose:
            print(f"{'Using specified' if provider else 'Detected'} platform: {platform.value}")
        
        # Step 3: Environment detection
        environment = detect_environment()
        if verbose:
            print(f"Detected environment: {environment.value}")
        
        # Steps 4-5: Create platform client and authenticate
        from .platforms import get_platform_client
        
        try:
            # Create platform client with init_transport parameter
            client = get_platform_client(platform, self.email, init_transport=init_transport, wizard=wizard)
            
            if verbose:
                print(f"\nAuthenticating with {platform.value}...")
            
            # Step 5: Attempt authentication (looks for 1-step auth)
            auth_result = client.authenticate()
            
            if verbose:
                print(f"Authentication successful!")
            
            # Add the authenticated platform to this client
            self.add_platform(client, auth_result)
            
            # Initialize transports for all secondary platforms if requested
            if init_transport:
                self._initialize_all_transports()
            
            # Check for secondary platforms
            secondary_platforms = get_secondary_platforms()
            if secondary_platforms and verbose:
                print(f"\nSecondary platforms available: {', '.join([p.value for p in secondary_platforms])}")
                print("(These can work with any email address)")
            
            if verbose:
                print(f"\n{self}")
                
        except NotImplementedError as e:
            raise e
        except Exception as e:
            if verbose:
                print(f"Authentication failed: {e}")
            raise
    
    @staticmethod
    def reset_wallet_static(confirm: bool = True) -> bool:
        """
        Static method to reset the wallet without needing a client instance.
        
        Args:
            confirm: If True, ask for confirmation before deleting (default: True)
            
        Returns:
            bool: True if wallet was reset, False if cancelled
        """
        # Create a dummy client just to use the instance method
        dummy = SyftClient("dummy@example.com")
        return dummy.reset_wallet(confirm)
    
    @staticmethod
    def login(email: Optional[str] = None, provider: Optional[str] = None, 
              quickstart: bool = True, verbose: bool = False, init_transport: bool = True, 
              wizard: Optional[bool] = None, **kwargs) -> 'SyftClient':
        """
        Simple login function for syft_client
        
        Args:
            email: Email address to authenticate as
            provider: Email provider name (e.g., 'google', 'microsoft'). Required if auto-detection fails.
            quickstart: If True and in supported environment, use fastest available login
            verbose: If True, print detailed progress information
            init_transport: If True (default), initialize transport layers during login. If False, skip transport initialization.
            wizard: If True, run interactive setup wizard for credentials. If None, auto-detect based on missing credentials.
            **kwargs: Additional arguments for authentication
            
        Returns:
            SyftClient: Authenticated client object with platform and transport layers
        """
        # Step 0: Validate email input
        if email is None:
            environment = detect_environment()
            if environment == Environment.COLAB:
                # In Colab, try to get email from auth
                try:
                    from google.colab import auth as colab_auth
                    import google.auth
                    # Authenticate and get credentials
                    colab_auth.authenticate_user()
                    credentials, project = google.auth.default()
                    
                    # Debug: check what we got
                    if project == 'default':
                        # This means we got the project ID, not the email
                        # Let's try a different approach
                        pass
                    
                    # Try to get email from credentials
                    if hasattr(credentials, '_service_account_email'):
                        email = credentials._service_account_email
                    elif hasattr(credentials, 'service_account_email'):
                        email = credentials.service_account_email
                    else:
                        # Try to get from token info
                        import requests
                        from google.auth.transport.requests import Request
                        
                        # Ensure credentials are valid
                        if credentials.expired and credentials.refresh_token:
                            credentials.refresh(Request())
                        elif not hasattr(credentials, 'token') or credentials.token is None:
                            # Force a refresh to get a token
                            credentials.refresh(Request())
                            
                        token = credentials.token
                        
                        # Get user info from Google
                        headers = {'Authorization': f'Bearer {token}'}
                        resp = requests.get('https://www.googleapis.com/oauth2/v1/userinfo', headers=headers)
                        if resp.status_code == 200:
                            user_info = resp.json()
                            email = user_info.get('email')
                            
                            if email and email != 'default' and '@' in email:
                                print(f"Auto-detected email from Colab auth: {email}")
                            else:
                                if email == 'default':
                                    print("Debug: Got 'default' as email from userinfo")
                                raise ValueError("Could not detect email from Colab auth. Please specify: login(email='your@gmail.com')")
                        else:
                            raise ValueError("Could not detect email from Colab auth. Please specify: login(email='your@gmail.com')")
                except Exception as e:
                    # If anything fails, show the actual error for debugging
                    import traceback
                    print(f"Debug: Colab auth error: {e}")
                    traceback.print_exc()
                    raise ValueError("Please specify an email: login(email='your@gmail.com')")
            else:
                # Look for existing emails in ~/.syft
                from pathlib import Path
                syft_dir = Path.home() / ".syft"
                
                if syft_dir.exists():
                    # Find email-like directory names
                    email_dirs = []
                    for item in syft_dir.iterdir():
                        if item.is_dir() and '_at_' in item.name:
                            # Convert back from safe format to email
                            # Format is: email_at_domain_com -> email@domain.com
                            parts = item.name.split('_at_')
                            if len(parts) == 2:
                                local_part = parts[0]
                                domain_parts = parts[1].split('_')
                                if len(domain_parts) >= 2:
                                    # Reconstruct domain with dots
                                    domain = '.'.join(domain_parts)
                                    email_candidate = f"{local_part}@{domain}"
                                    # Basic email validation
                                    if '.' in domain:
                                        email_dirs.append((item, email_candidate))
                    
                    if len(email_dirs) == 1:
                        # Only one email found, use it
                        _, email = email_dirs[0]
                        print(f"📧 Using email from ~/.syft: {email}")
                    elif len(email_dirs) > 1:
                        # Multiple emails found, ask user to choose
                        print("\n📧 Multiple email accounts found in ~/.syft:")
                        for i, (_, email_addr) in enumerate(email_dirs):
                            print(f"  {i+1}. {email_addr}")
                        print(f"  {len(email_dirs)+1}. Enter a different email")
                        
                        choice = input(f"\nSelect an option (1-{len(email_dirs)+1}): ").strip()
                        
                        try:
                            choice_idx = int(choice) - 1
                            if 0 <= choice_idx < len(email_dirs):
                                _, email = email_dirs[choice_idx]
                            elif choice_idx == len(email_dirs):
                                email = input("Enter your email: ").strip()
                                if not email:
                                    raise ValueError("Email cannot be empty")
                            else:
                                raise ValueError("Invalid choice")
                        except (ValueError, IndexError):
                            raise ValueError("Invalid selection. Please run login() again.")
                    else:
                        raise ValueError("Please specify an email: login(email='your@email.com')")
                else:
                    raise ValueError("Please specify an email: login(email='your@email.com')")
        
        # Create SyftClient and login
        client = SyftClient(email)
        client._login(provider=provider, verbose=verbose, init_transport=init_transport, wizard=wizard)
        return client