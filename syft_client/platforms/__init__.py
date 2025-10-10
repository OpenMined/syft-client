"""Platform implementations for syft_client"""

from .apple import AppleClient
from .base import BasePlatformClient
from .detection import (
    Platform,
    PlatformDetector,
    detect_platform_full,
    detect_primary_platform,
    get_secondary_platforms,
)
from .dropbox import DropboxClient
from .fastmail import FastmailClient
from .gmx import GMXClient
from .google_org import GoogleOrgClient

# Import all platform clients
from .google_personal import GooglePersonalClient
from .mailcom import MailcomClient
from .microsoft import MicrosoftClient
from .proton import ProtonClient
from .smtp import SMTPClient
from .transport_base import BaseTransportLayer
from .yahoo import YahooClient
from .zoho import ZohoClient

# Platform client registry
PLATFORM_CLIENTS = {
    Platform.GOOGLE_PERSONAL: GooglePersonalClient,
    Platform.GOOGLE_ORG: GoogleOrgClient,
    Platform.MICROSOFT: MicrosoftClient,
    Platform.YAHOO: YahooClient,
    Platform.APPLE: AppleClient,
    Platform.ZOHO: ZohoClient,
    Platform.PROTON: ProtonClient,
    Platform.GMX: GMXClient,
    Platform.FASTMAIL: FastmailClient,
    Platform.MAILCOM: MailcomClient,
    Platform.DROPBOX: DropboxClient,
    Platform.SMTP: SMTPClient,
}


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
    "BasePlatformClient",
    "BaseTransportLayer",
    "Platform",
    "detect_primary_platform",
    "get_secondary_platforms",
    "detect_platform_full",
    "PlatformDetector",
    "get_platform_client",
    "GooglePersonalClient",
    "GoogleOrgClient",
    "MicrosoftClient",
    "YahooClient",
    "AppleClient",
    "ZohoClient",
    "ProtonClient",
    "GMXClient",
    "FastmailClient",
    "MailcomClient",
    "DropboxClient",
    "SMTPClient",
]
