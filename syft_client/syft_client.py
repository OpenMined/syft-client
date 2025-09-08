"""
SyftClient class - Main client object that manages platforms and transport layers
"""

from typing import Dict, List, Optional, Any
from .platforms.base import BasePlatformClient
from .platforms.detection import Platform, detect_platform, PlatformDetector
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
        self.platforms: Dict[str, BasePlatformClient] = {}
    
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
    
    
    
    
    @staticmethod
    def _validate_platform_support(email: str, platform: Platform) -> None:
        """
        Validate that the platform is supported
        
        Args:
            email: Email address
            platform: Platform to validate
            
        Raises:
            ValueError: If platform not supported
        """
        if PlatformDetector.is_supported(platform):
            return
            
        # Get list of supported providers
        supported = sorted([p.value for p in PlatformDetector.SUPPORTED_PLATFORMS])
        
        raise ValueError(
            f"\nThe email provider '{platform.value}' was detected but is not currently supported.\n\n"
            f"Supported providers are: {', '.join(supported)}\n\n"
            f"If you believe this is incorrect, you can try specifying a different provider:\n"
            f"  login(email='{email}', provider='microsoft')      # If using Office 365\n"
            f"  login(email='{email}', provider='google_personal') # If personal Gmail\n"
            f"  login(email='{email}', provider='google_org')      # If Google Workspace\n"
        )
    
    @staticmethod
    def _authenticate_platform(email: str, platform: Platform, verbose: bool) -> 'SyftClient':
        """
        Steps 4-5: Create platform client and authenticate
        
        Args:
            email: Email address
            platform: Platform to authenticate with
            verbose: Whether to print progress
            
        Returns:
            Authenticated SyftClient
            
        Raises:
            Exception: If authentication fails
        """
        from .platforms import get_platform_client
        
        try:
            # Create platform client
            client = get_platform_client(platform, email)
            
            if verbose:
                print(f"\nAuthenticating with {platform.value}...")
            
            # Step 5: Attempt authentication (looks for 1-step auth)
            auth_result = client.authenticate()
            
            if verbose:
                print(f"Authentication successful!")
            
            # Create SyftClient and add the authenticated platform
            syft_client = SyftClient(email)
            syft_client.add_platform(client, auth_result)
            
            if verbose:
                print(f"\n{syft_client}")
                
            return syft_client
            
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
        
        This implements Steps 0-5 of the Beach Option B RFC login flow:
        - Step 0: Validate email input
        - Step 1: Begin login process
        - Step 2: Detect platform 
        - Step 3: Detect environment
        - Step 4: Heat caches
        - Step 5: Look for 1-step authentication
        
        Args:
            email: Email address to authenticate as
            provider: Email provider name (e.g., 'google', 'microsoft'). Required if auto-detection fails.
            quickstart: If True and in supported environment, use fastest available login
            verbose: If True, print detailed progress information
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
        
        # Step 1: login(email) is called
        if verbose:
            print(f"Logging in as {email}...")
        
        # Step 2: Platform detection (includes unknown platform handling)
        platform = detect_platform(email, provider)
        if verbose:
            print(f"{'Using specified' if provider else 'Detected'} platform: {platform.value}")
        
        # Validate platform is supported
        SyftClient._validate_platform_support(email, platform)
        
        # Step 3: Environment detection
        environment = detect_environment()
        if verbose:
            print(f"Detected environment: {environment.value}")
        
        # Steps 4-5: Heat caches and attempt 1-step authentication
        return SyftClient._authenticate_platform(email, platform, verbose)