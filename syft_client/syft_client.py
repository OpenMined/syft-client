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
        console = Console(file=string_buffer, force_terminal=True, width=80)
        
        # Create main table
        main_table = Table(show_header=False, show_edge=False, box=None, padding=0)
        main_table.add_column("Property", style="dim")
        main_table.add_column("Value")
        
        # Add folder path
        from pathlib import Path
        syft_folder = Path.home() / "SyftBox" / self.email.replace('@', '_at_').replace('.', '_')
        main_table.add_row(".folder", f"= {syft_folder}")
        
        # Add platforms section
        main_table.add_row("", "")  # Empty row for spacing
        main_table.add_row(".platforms", "")
        
        # Add each platform with its transports
        for platform_name, platform in self._platforms.items():
            # Platform header
            main_table.add_row(f"  .{platform_name}", "", style="bold yellow")
            
            # Get all available transport names (including uninitialized)
            transport_names = platform.get_transport_layers()
            
            for transport_name in transport_names:
                # Check if transport is actually initialized and setup
                if hasattr(platform, 'transports') and transport_name in platform.transports:
                    transport = platform.transports[transport_name]
                    if hasattr(transport, 'is_setup') and transport.is_setup():
                        status = "✓"
                        style = "green"
                        message = ""
                    else:
                        status = "✗"
                        style = "dim"
                        # Check if this is an uninitialized stub that needs setup
                        if hasattr(transport, '_setup_called') and not transport._setup_called:
                            message = " (call .setup() to initialize)"
                        else:
                            message = ""
                else:
                    # Transport not initialized
                    status = "✗"
                    style = "dim"
                    message = ""
                main_table.add_row(f"    {status} .{transport_name}{message}", "", style=style)
        
        # Create the panel
        panel = Panel(
            main_table,
            title=f"SyftClient.email = '{self.email}'",
            expand=False,
            width=80,
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
    
    def _login(self, provider: Optional[str] = None, verbose: bool = False, init_transport: bool = True) -> None:
        """
        Instance method that handles the actual login process
        
        Args:
            provider: Optional provider override
            verbose: Whether to print progress
            init_transport: Whether to initialize transport layers
            
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
            client = get_platform_client(platform, self.email, init_transport=init_transport)
            
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
    def login(email: Optional[str] = None, provider: Optional[str] = None, 
              quickstart: bool = True, verbose: bool = False, init_transport: bool = True, **kwargs) -> 'SyftClient':
        """
        Simple login function for syft_client
        
        Args:
            email: Email address to authenticate as
            provider: Email provider name (e.g., 'google', 'microsoft'). Required if auto-detection fails.
            quickstart: If True and in supported environment, use fastest available login
            verbose: If True, print detailed progress information
            init_transport: If True (default), initialize transport layers during login. If False, skip transport initialization.
            **kwargs: Additional arguments for authentication
            
        Returns:
            SyftClient: Authenticated client object with platform and transport layers
        """
        # Step 0: Validate email input
        if email is None:
            environment = detect_environment()
            if environment == Environment.COLAB:
                raise ValueError("Please specify an email: login(email='your@gmail.com')")
            else:
                raise ValueError("Please specify an email: login(email='your@email.com')")
        
        # Create SyftClient and login
        client = SyftClient(email)
        client._login(provider=provider, verbose=verbose, init_transport=init_transport)
        return client