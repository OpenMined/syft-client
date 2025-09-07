"""Main client module for syft_client"""
from typing import Optional

from .environment import Environment, detect_environment
from .platforms.detection import Platform, detect_platform


def login(email: Optional[str] = None, quickstart: bool = True, verbose: bool = False, **kwargs):
    """
    Simple login function for syft_client
    
    Args:
        email: Email address to authenticate as
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
    platform = detect_platform(email)
    if verbose:
        print(f"Detected platform: {platform.value}")
    
    # Check if platform is supported
    if platform == Platform.UNKNOWN:
        raise ValueError(
            f"Could not detect platform for email: {email}. "
            "Supported providers include: Gmail, Outlook, Yahoo, iCloud, Zoho, "
            "ProtonMail, GMX, Fastmail, Tutanota, Mail.com, QQ Mail, NetEase (163/126), "
            "Mail.ru, Yandex, and Naver"
        )
    
    # Step 3: Environment detection - which Python environment are we in?
    environment = detect_environment()
    if verbose:
        print(f"Detected environment: {environment.value}")
    
    # TODO: Step 4 onwards - configure transport layers, heat caches, etc.
    pass