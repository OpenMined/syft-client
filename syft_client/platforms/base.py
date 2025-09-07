"""Base class for platform clients"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List


class BasePlatformClient(ABC):
    """Abstract base class for all platform clients"""
    
    def __init__(self, email: str):
        self.email = email
        self.platform = self.__class__.__name__.replace('Client', '').lower()
        
    def authenticate(self) -> Dict[str, Any]:
        """
        Authenticate the user with the platform.
        
        Returns:
            Dict containing authentication tokens/credentials
            
        Raises:
            NotImplementedError: If platform login not yet supported
        """
        # Check if this platform has implemented authentication
        if self.login_complexity == -1:
            platform_name = self.platform.replace('client', '')
            raise NotImplementedError(
                f"\nLogin for {platform_name} is not yet supported.\n\n"
                f"This platform requires additional development to enable authentication.\n"
                f"Currently supported platforms with working authentication:\n"
                f"  • smtp - Generic SMTP/IMAP email (implemented)\n\n"
                f"Platforms coming soon:\n"
                f"  • google - Gmail, Google Workspace\n"
                f"  • microsoft - Outlook, Office 365\n"
                f"  • dropbox - Dropbox file storage\n\n"
                f"To use a generic SMTP email server, try:\n"
                f"  login(email='{self.email}', provider='smtp')\n"
            )
        
        # Subclasses should override this entire method
        raise NotImplementedError(
            f"Platform {self.platform} must implement authenticate() method"
        )
        
    @abstractmethod
    def get_transport_layers(self) -> List[str]:
        """
        Get list of available transport layers for this platform.
        
        Returns:
            List of transport layer class names
        """
        pass
        
    @property
    def login_complexity(self) -> int:
        """
        Returns the number of steps required for platform authentication.
        
        This is the base authentication complexity (e.g., OAuth2 flow).
        Transport layers add their own complexity on top of this.
        
        Returns:
            -1: Not implemented
            0: Already authenticated (cached credentials)
            1: Single-step login (e.g., Colab with Google)
            2+: Multi-step login (e.g., OAuth2 flow)
        """
        return -1  # Default: not implemented
        
    def __repr__(self):
        return f"{self.__class__.__name__}(email='{self.email}')"