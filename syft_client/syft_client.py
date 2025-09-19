"""
SyftClient class - Main client object that manages platforms and transport layers
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
from .platforms.base import BasePlatformClient
from .platforms.detection import Platform, detect_primary_platform, get_secondary_platforms, PlatformDetector
from .environment import Environment, detect_environment


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
        self.platforms: Dict[str, BasePlatformClient] = {}
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
        self.platforms[platform_name] = platform_client
        
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
        return self.platforms.get(platform_name)
    
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
        """String representation"""
        platform_info = []
        for name, platform in self.platforms.items():
            transports = platform.get_transport_layers()
            platform_info.append(f"{name}:{len(transports)}")
        return f"SyftClient(email='{self.email}', platforms=[{', '.join(platform_info)}])"
    
    def __str__(self) -> str:
        """User-friendly string representation"""
        lines = [f"SyftClient - {self.email}"]
        for platform_name, platform in self.platforms.items():
            transports = platform.get_transport_layers()
            lines.append(f"  • {platform_name}: {', '.join(transports)}")
        return "\n".join(lines)
    
    def _login(self, provider: Optional[str] = None, verbose: bool = False) -> None:
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
            client = get_platform_client(platform, self.email, verbose=verbose)
            
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
              quickstart: bool = True, verbose: bool = False, **kwargs) -> 'SyftClient':
        """
        Simple login function for syft_client
        
        Args:
            email: Email address to authenticate as. Optional in Colab (auto-detected).
            provider: Email provider name (e.g., 'google', 'microsoft'). Required if auto-detection fails.
            quickstart: If True and in supported environment, use fastest available login
            verbose: If True, print detailed progress information
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
        client._login(provider=provider, verbose=verbose)
        return client