"""
SyftClient class - Main client object that manages platforms and transport layers
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
from .platforms.base import BasePlatformClient
from .platforms.detection import Platform, detect_primary_platform, get_secondary_platforms, PlatformDetector
from .environment import Environment, detect_environment


class PlatformRegistry:
    """Container for platform clients that allows attribute access"""
    
    def __init__(self):
        self._platforms: Dict[str, BasePlatformClient] = {}
    
    def add(self, name: str, client: BasePlatformClient):
        """Add a platform client"""
        self._platforms[name] = client
        # Also set as attribute for dot access
        setattr(self, name, client)
    
    def __getitem__(self, key: str) -> Optional[BasePlatformClient]:
        """Allow dict-style access for backwards compatibility"""
        return self._platforms.get(key)
    
    def __contains__(self, key: str) -> bool:
        """Check if platform exists"""
        return key in self._platforms
    
    def items(self):
        """Iterate over platforms"""
        return self._platforms.items()
    
    def keys(self):
        """Get platform names"""
        return self._platforms.keys()
    
    def values(self):
        """Get platform clients"""
        return self._platforms.values()
    
    def __bool__(self):
        """Check if any platforms are registered"""
        return bool(self._platforms)
    
    def __len__(self):
        """Number of platforms"""
        return len(self._platforms)
    
    def __dir__(self):
        """Show available platforms for tab completion"""
        return list(self._platforms.keys())
    
    def __repr__(self):
        """String representation using rich for proper formatting"""
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from io import StringIO
        from .platforms.detection import get_all_platforms
        
        # Create a string buffer to capture the rich output
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=70)
        
        # Create main table
        main_table = Table(show_header=False, show_edge=False, box=None, padding=0)
        main_table.add_column(style="dim")
        
        # Get all available platforms
        all_platforms = get_all_platforms()
        
        for platform_enum in all_platforms:
            platform_name = platform_enum.value
            
            # Check if this platform is logged in
            if platform_name in self._platforms:
                # Logged in - show with transports
                platform = self._platforms[platform_name]
                
                # Get transports and their status
                transports = []
                transport_layers = platform.get_transport_layers()
                for transport in transport_layers:
                    transport_obj = platform.transports.get(transport) if hasattr(platform, 'transports') else None
                    if transport_obj and hasattr(transport_obj, 'is_setup') and transport_obj.is_setup():
                        status = "[green]✓[/green]"
                    else:
                        status = "[dim]○[/dim]"
                    transports.append(f"{status} .{transport}")
                
                # Add platform
                main_table.add_row(f"[bold yellow].{platform_name}[/bold yellow]")
                
                # Add transports in 2 columns
                if transports:
                    transport_table = Table(show_header=False, show_edge=False, box=None, padding=(0, 2))
                    transport_table.add_column(width=30)
                    transport_table.add_column(width=30)
                    
                    for i in range(0, len(transports), 2):
                        col1 = transports[i] if i < len(transports) else ""
                        col2 = transports[i+1] if i+1 < len(transports) else ""
                        transport_table.add_row(f"  {col1}", f"  {col2}")
                    
                    main_table.add_row(transport_table)
                    main_table.add_row("")  # spacer between platforms
            else:
                # Not logged in - show grayed out
                main_table.add_row(f"[dim].{platform_name}[/dim]  [dim italic](not authenticated)[/dim italic]")
        
        if len(all_platforms) == 0:
            main_table.add_row("No platforms available")
        
        # Create the panel
        panel = Panel(
            main_table,
            title="PlatformRegistry",
            expand=False,
            width=70,
            padding=(1, 2)
        )
        
        console.print(panel)
        output = string_buffer.getvalue()
        string_buffer.close()
        
        return output.strip()


class SyftClient:
    """
    Main client object that manages multiple platforms for a single email
    
    A SyftClient represents an authenticated session for a single email account
    that can have multiple platforms (e.g., Gmail + Dropbox with same email).
    """
    
    def __dir__(self):
        """Limit tab completion to only show essential attributes"""
        return ['email', 'platforms', 'folder']
    
    def __init__(self, email: str):
        """
        Initialize a SyftClient for a specific email
        
        Args:
            email: The email address for this client
        """
        self.email = email
        self.platforms = PlatformRegistry()
        self.transport_instances: Dict[str, Any] = {}  # platform:transport -> instance
        
        # Create SyftBox directory structure
        self._syftbox_dir = self._create_syftbox_directory()
        self.folder = self._syftbox_dir  # Expose as client.folder
    
    def _create_syftbox_directory(self) -> Path:
        """
        Create the local SyftBox directory structure
        
        Creates:
            ~/SyftBox_{email}/
            ├── datasites/
            ├── apps/
            ├── approved/
            ├── inbox/
            └── merged_archive/
        
        Returns:
            Path to the SyftBox directory
        """
        # Create ~/SyftBox_{email} directory
        home_dir = Path.home()
        syftbox_dir = home_dir / f"SyftBox_{self.email}"
        
        try:
            # Create main directory
            syftbox_dir.mkdir(exist_ok=True)
            
            # Create subdirectories (matching existing structure)
            subdirs = ["datasites", "apps", "approved", "inbox", "merged_archive"]
            for subdir in subdirs:
                (syftbox_dir / subdir).mkdir(exist_ok=True)
                
        except Exception as e:
            print(f"Warning: Could not create SyftBox directory: {e}")
            
        return syftbox_dir
    
    @property
    def datasites_folder(self) -> Path:
        """Get the datasites folder path"""
        return self.folder / "datasites"
    
    @property
    def apps_folder(self) -> Path:
        """Get the apps folder path"""
        return self.folder / "apps"
    
    def resolve_syft_path(self, path: str) -> Path:
        """
        Resolve a syft:// URL to a full file path
        
        Supports:
        - syft://filename.txt -> ~/SyftBox_{email}/datasites/filename.txt
        - syft://folder/filename.txt -> ~/SyftBox_{email}/datasites/folder/filename.txt
        
        Args:
            path: A path that may start with syft://
            
        Returns:
            Resolved Path object
        """
        if not path.startswith("syft://"):
            return Path(path)
        
        # Extract the relative path after syft://
        relative_path = path[7:]  # Remove "syft://"
        
        # Build the full path (always in datasites)
        return self.datasites_folder / relative_path
    
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
        self.platforms.add(platform_name, platform_client)
        
        # Store auth data in the platform client for now
        platform_client._auth_data = auth_data
        
        # Add transports from this platform
        self._add_platform_transports(platform_name, platform_client)
    
    @property
    def platform_names(self) -> List[str]:
        """Get list of authenticated platform names"""
        return list(self.platforms.keys())
    
    def get_platform(self, platform_name: str) -> Optional[BasePlatformClient]:
        """Get a specific platform client by name"""
        return self.platforms[platform_name]
    
    def get_transports(self, platform_name: str) -> List[str]:
        """Get transport layers for a specific platform"""
        platform = self.get_platform(platform_name)
        return platform.get_transport_layers() if platform else []
    
    @property
    def all_transports(self) -> Dict[str, List[str]]:
        """Get all transport layers grouped by platform"""
        return {
            platform_name: platform.get_transport_layers()
            for platform_name, platform in self.platforms.items()
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
        from rich.columns import Columns
        from io import StringIO
        
        # Create a string buffer to capture the rich output
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=70)
        
        # Create main table
        main_table = Table(show_header=False, show_edge=False, box=None, padding=0)
        main_table.add_column(style="dim")
        
        # Add folder info
        main_table.add_row(f"[bold cyan].folder[/bold cyan] = {self.folder}")
        main_table.add_row("")  # spacer
        
        if self.platforms:
            # Add platforms header
            main_table.add_row("[bold cyan].platforms[/bold cyan]")
            
            for platform_name, platform in self.platforms.items():
                # Get transports and their status
                transports = []
                transport_layers = platform.get_transport_layers()
                for transport in transport_layers:
                    # Try to get transport as attribute first
                    transport_obj = getattr(platform, transport, None)
                    if transport_obj is None and hasattr(platform, 'transports'):
                        # Fallback to transports dict
                        transport_obj = platform.transports.get(transport)
                    
                    if transport_obj and hasattr(transport_obj, 'is_setup') and transport_obj.is_setup():
                        transports.append(f"[green]✓[/green] .{transport}")
                    else:
                        transports.append(f"[dim]○[/dim] .{transport}")
                
                # Add platform with attribute-style syntax
                main_table.add_row(f"  [bold yellow].{platform_name}[/bold yellow]")
                
                # Create a table for transports in 2 columns
                if transports:
                    transport_table = Table(show_header=False, show_edge=False, box=None, padding=(0, 2))
                    transport_table.add_column(width=30)
                    transport_table.add_column(width=30)
                    
                    for i in range(0, len(transports), 2):
                        col1 = transports[i] if i < len(transports) else ""
                        col2 = transports[i+1] if i+1 < len(transports) else ""
                        transport_table.add_row(f"    {col1}", f"    {col2}")
                    
                    main_table.add_row(transport_table)
        else:
            main_table.add_row("")
            main_table.add_row("No authenticated platforms")
        
        # Create the panel with the table
        panel = Panel(
            main_table,
            title=f"SyftClient.email = '{self.email}'",
            expand=False,
            width=70,
            padding=(1, 2)
        )
        
        console.print(panel)
        output = string_buffer.getvalue()
        string_buffer.close()
        
        return output.strip()
    
    def __str__(self) -> str:
        """User-friendly string representation"""
        lines = []
        lines.append(f"SyftClient ({self.email})")
        for platform_name, platform in self.platforms.items():
            transports = []
            transport_layers = platform.get_transport_layers()
            for transport in transport_layers:
                # Check if transport is active/configured
                transport_obj = platform.transports.get(transport)
                if transport_obj and hasattr(transport_obj, 'is_setup') and transport_obj.is_setup():
                    transports.append(f"✓{transport}")
                else:
                    transports.append(f"○{transport}")
            lines.append(f"  └─ {platform_name}: {', '.join(transports)}")
        return "\n".join(lines)
    
    def _login(self, provider: Optional[str] = None, verbose: bool = False, wizard: Optional[bool] = None) -> None:
        """
        Instance method that handles the actual login process
        
        Args:
            provider: Optional provider override
            verbose: Whether to print progress
            
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
            # Create platform client
            client = get_platform_client(platform, self.email, verbose=verbose, wizard=wizard)
            
            if verbose:
                print(f"\nAuthenticating with {platform.value}...")
            
            # Step 5: Attempt authentication (looks for 1-step auth)
            auth_result = client.authenticate()
            
            if verbose:
                print(f"Authentication successful!")
            
            # Add the authenticated platform to this client
            self.add_platform(client, auth_result)
            
            # Initialize transports for all secondary platforms
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
    def login(email: Optional[str] = None, provider: Optional[str] = None, 
              quickstart: bool = True, verbose: bool = False, wizard: Optional[bool] = None, **kwargs) -> 'SyftClient':
        """
        Simple login function for syft_client
        
        Args:
            email: Email address to authenticate as. Optional in Colab (auto-detected).
            provider: Email provider name (e.g., 'google', 'microsoft'). Required if auto-detection fails.
            quickstart: If True and in supported environment, use fastest available login
            verbose: If True, print detailed progress information
            wizard: If True, show interactive setup wizard (Colab defaults to False, others default to True)
            **kwargs: Additional arguments for authentication
            
        Returns:
            SyftClient: Authenticated client object with platform and transport layers
        """
        # Step 0: Handle email input
        environment = detect_environment()
        if email is None:
            if environment == Environment.COLAB:
                # In Colab, we can try to auto-detect the email
                try:
                    from google.colab import auth as colab_auth
                    from googleapiclient.discovery import build
                    
                    # Authenticate and get email
                    colab_auth.authenticate_user()
                    service = build('drive', 'v3')
                    about = service.about().get(fields="user(emailAddress)").execute()
                    email = about['user']['emailAddress']
                    
                    if verbose:
                        print(f"🔐 Auto-detected Colab user: {email}")
                except Exception as e:
                    if verbose:
                        print(f"⚠️  Could not auto-detect email in Colab: {e}")
                    raise ValueError("Could not auto-detect email. Please specify: login(email='your@gmail.com')")
            else:
                raise ValueError("Please specify an email: login(email='your@email.com')")
        
        # Create SyftClient and login
        client = SyftClient(email)
        client._login(provider=provider, verbose=verbose, wizard=wizard)
        return client