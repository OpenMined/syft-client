"""Main client module for syft_client"""
from typing import Optional

from .environment import Environment, detect_environment
from .platforms.detection import Platform, detect_platform, PlatformDetector


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
        Authenticated client object
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
            'google': 'Gmail, Google Workspace',
            'microsoft': 'Outlook, Hotmail, Live, Office 365',
            'yahoo': 'Yahoo Mail',
            'apple': 'iCloud Mail',
            'zoho': 'Zoho Mail',
            'proton': 'ProtonMail',
            'gmx': 'GMX Mail',
            'fastmail': 'Fastmail',
            'mailcom': 'Mail.com'
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
            f"  login(email='{email}', provider='microsoft')  # for Office 365\n"
            f"  login(email='{email}', provider='google')     # for Google Workspace\n"
        )
    
    # Check if detected/specified platform is supported
    if not PlatformDetector.is_supported(platform):
        # Get list of supported providers
        supported = sorted([p.value for p in PlatformDetector.SUPPORTED_PLATFORMS])
        
        raise ValueError(
            f"\nThe email provider '{platform.value}' was detected but is not currently supported.\n\n"
            f"Supported providers are: {', '.join(supported)}\n\n"
            f"If you believe this is incorrect, you can try specifying a different provider:\n"
            f"  login(email='{email}', provider='microsoft')  # If using Office 365\n"
            f"  login(email='{email}', provider='google')     # If using Google Workspace\n"
        )
    
    # Step 3: Environment detection - which Python environment are we in?
    environment = detect_environment()
    if verbose:
        print(f"Detected environment: {environment.value}")
    
    # TODO: Step 4 onwards - configure transport layers, heat caches, etc.
    pass