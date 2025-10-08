"""Platform implementations for syft_client"""

from .base import BasePlatformClient
from .transport_base import BaseTransportLayer
from .detection import Platform, detect_primary_platform, get_secondary_platforms, detect_platform_full, PlatformDetector

# Lazy import function to avoid loading all platform clients at module import time
def _get_platform_client_class(platform: Platform):
    """Lazy load platform client classes to avoid import errors in subprocesses"""
    # Import only when needed
    if platform == Platform.GOOGLE_PERSONAL:
        from .google_personal import GooglePersonalClient
        return GooglePersonalClient
    elif platform == Platform.GOOGLE_ORG:
        from .google_org import GoogleOrgClient
        return GoogleOrgClient
    elif platform == Platform.MICROSOFT:
        from .microsoft import MicrosoftClient
        return MicrosoftClient
    elif platform == Platform.YAHOO:
        from .yahoo import YahooClient
        return YahooClient
    elif platform == Platform.APPLE:
        from .apple import AppleClient
        return AppleClient
    elif platform == Platform.ZOHO:
        from .zoho import ZohoClient
        return ZohoClient
    elif platform == Platform.PROTON:
        from .proton import ProtonClient
        return ProtonClient
    elif platform == Platform.GMX:
        from .gmx import GMXClient
        return GMXClient
    elif platform == Platform.FASTMAIL:
        from .fastmail import FastmailClient
        return FastmailClient
    elif platform == Platform.MAILCOM:
        from .mailcom import MailcomClient
        return MailcomClient
    elif platform == Platform.DROPBOX:
        from .dropbox import DropboxClient
        return DropboxClient
    elif platform == Platform.SMTP:
        from .smtp import SMTPClient
        return SMTPClient
    else:
        raise ValueError(f"Unknown platform: {platform}")

# Platform client registry - uses lazy loading
class _PlatformClientRegistry(dict):
    """Registry that lazily loads platform client classes"""

    # List of all supported platforms
    _SUPPORTED_PLATFORMS = [
        Platform.GOOGLE_PERSONAL,
        Platform.GOOGLE_ORG,
        Platform.MICROSOFT,
        Platform.YAHOO,
        Platform.APPLE,
        Platform.ZOHO,
        Platform.PROTON,
        Platform.GMX,
        Platform.FASTMAIL,
        Platform.MAILCOM,
        Platform.DROPBOX,
        Platform.SMTP,
    ]

    def __getitem__(self, platform):
        return _get_platform_client_class(platform)

    def __contains__(self, platform):
        """Check if platform is supported"""
        return platform in self._SUPPORTED_PLATFORMS

    def get(self, platform, default=None):
        try:
            return _get_platform_client_class(platform)
        except ValueError:
            return default

    def keys(self):
        """Return all supported platform keys"""
        return self._SUPPORTED_PLATFORMS

    def values(self):
        """Return all platform client classes (lazy loaded)"""
        return [_get_platform_client_class(p) for p in self._SUPPORTED_PLATFORMS]

    def items(self):
        """Return all (platform, client_class) pairs (lazy loaded)"""
        return [(p, _get_platform_client_class(p)) for p in self._SUPPORTED_PLATFORMS]

PLATFORM_CLIENTS = _PlatformClientRegistry()

# Re-export classes for backwards compatibility using lazy loading
def __getattr__(name):
    """Lazy load platform client classes when accessed"""
    if name == 'GooglePersonalClient':
        from .google_personal import GooglePersonalClient
        return GooglePersonalClient
    elif name == 'GoogleOrgClient':
        from .google_org import GoogleOrgClient
        return GoogleOrgClient
    elif name == 'MicrosoftClient':
        from .microsoft import MicrosoftClient
        return MicrosoftClient
    elif name == 'YahooClient':
        from .yahoo import YahooClient
        return YahooClient
    elif name == 'AppleClient':
        from .apple import AppleClient
        return AppleClient
    elif name == 'ZohoClient':
        from .zoho import ZohoClient
        return ZohoClient
    elif name == 'ProtonClient':
        from .proton import ProtonClient
        return ProtonClient
    elif name == 'GMXClient':
        from .gmx import GMXClient
        return GMXClient
    elif name == 'FastmailClient':
        from .fastmail import FastmailClient
        return FastmailClient
    elif name == 'MailcomClient':
        from .mailcom import MailcomClient
        return MailcomClient
    elif name == 'DropboxClient':
        from .dropbox import DropboxClient
        return DropboxClient
    elif name == 'SMTPClient':
        from .smtp import SMTPClient
        return SMTPClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def get_platform_client(platform: Platform, email: str, **kwargs) -> BasePlatformClient:
    """
    Get the appropriate platform client for the given platform.
    
    Args:
        platform: The platform enum
        email: User's email address
        **kwargs: Additional arguments to pass to the platform client
        
    Returns:
        Platform client instance
        
    Raises:
        ValueError: If platform is not supported
    """
    if platform not in PLATFORM_CLIENTS:
        raise ValueError(f"Platform {platform.value} is not supported")
    
    client_class = PLATFORM_CLIENTS[platform]
    return client_class(email, **kwargs)

__all__ = [
    'BasePlatformClient',
    'BaseTransportLayer',
    'Platform',
    'detect_primary_platform',
    'get_secondary_platforms',
    'detect_platform_full',
    'PlatformDetector',
    'get_platform_client',
    'GooglePersonalClient',
    'GoogleOrgClient',
    'MicrosoftClient',
    'YahooClient',
    'AppleClient',
    'ZohoClient',
    'ProtonClient',
    'GMXClient',
    'FastmailClient',
    'MailcomClient',
    'DropboxClient',
    'SMTPClient',
]