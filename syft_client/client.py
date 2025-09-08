"""Main client module for syft_client"""
from typing import Optional

from .environment import Environment, detect_environment
from .platforms.detection import Platform, detect_platform, PlatformDetector
from .syft_client import SyftClient


def login(email: Optional[str] = None, provider: Optional[str] = None, quickstart: bool = True, verbose: bool = False, **kwargs):
    """
    Simple login function for syft_client
    
    Args:
        email: Email address to authenticate as
        provider: Email provider name (e.g., 'google', 'microsoft'). Required if auto-detection fails.
        quickstart: If True and in supported environment, use fastest available login
        verbose: If True, print detailed progress information
        **kwargs: Additional arguments for authentication
        
    Returns:
        SyftClient: Authenticated client object with platform and transport layers
    """
    # Step 0: Handle no email case
    if email is None:
        # Need environment info for appropriate error message
        environment = detect_environment()
        
        # For now, always require email until caching is implemented
        if environment == Environment.COLAB:
            raise ValueError(
                "Please specify an email: login(email='your@gmail.com')"
            )
        else:
            raise ValueError(
                "Please specify an email: login(email='your@email.com')"
            )
    
    # Step 1: login(email) is called
    if verbose:
        print(f"Logging in as {email}...")
    
    # Step 2: Platform detection - which platform does this email belong to?
    if provider:
        # User specified provider manually
        try:
            platform = Platform(provider.lower())
            if verbose:
                print(f"Using specified platform: {platform.value}")
        except ValueError:
            # Create list of supported provider strings only
            supported_providers = sorted([p.value for p in PlatformDetector.SUPPORTED_PLATFORMS])
            raise ValueError(
                f"Invalid provider '{provider}'. Valid options are:\n"
                f"{', '.join(supported_providers)}"
            )
    else:
        # Auto-detect platform
        platform = detect_platform(email)
        if verbose:
            print(f"Detected platform: {platform.value}")
    
    # Check if platform is unknown or unsupported
    if platform == Platform.UNKNOWN:
        # Create helpful error message with supported providers only
        provider_examples = {
            'google_personal': 'Personal Gmail accounts',
            'google_org': 'Google Workspace (organizational)',
            'microsoft': 'Outlook, Hotmail, Live, Office 365',
            'yahoo': 'Yahoo Mail',
            'apple': 'iCloud Mail',
            'zoho': 'Zoho Mail',
            'proton': 'ProtonMail',
            'gmx': 'GMX Mail',
            'fastmail': 'Fastmail',
            'mailcom': 'Mail.com',
            'dropbox': 'Dropbox (file storage only)',
            'smtp': 'Generic SMTP/IMAP email'
        }
        
        # Format provider list with examples
        provider_list = []
        for prov, desc in provider_examples.items():
            provider_list.append(f"  • '{prov}' - {desc}")
        
        raise ValueError(
            f"\nCould not automatically detect the email provider for: {email}\n\n"
            f"Please re-run login() and specify your email provider manually:\n\n"
            f"  login(email='{email}', provider='provider_name')\n\n"
            f"Supported providers:\n" + "\n".join(provider_list) + "\n\n"
            f"Example:\n"
            f"  login(email='{email}', provider='microsoft')      # for Office 365\n"
            f"  login(email='{email}', provider='google_personal') # for personal Gmail\n"
            f"  login(email='{email}', provider='google_org')      # for Google Workspace\n"
        )
    
    # Check if detected/specified platform is supported
    if not PlatformDetector.is_supported(platform):
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
    
    # Step 3: Environment detection - which Python environment are we in?
    environment = detect_environment()
    if verbose:
        print(f"Detected environment: {environment.value}")
    
    # Step 4: Get platform client and attempt authentication
    from .platforms import get_platform_client
    
    try:
        # Create platform client
        client = get_platform_client(platform, email)
        
        if verbose:
            print(f"\nAuthenticating with {platform.value}...")
        
        # Attempt authentication
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
        # Re-raise with cleaner error message
        raise e
    except Exception as e:
        if verbose:
            print(f"Authentication failed: {e}")
        raise