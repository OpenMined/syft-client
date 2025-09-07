"""Base class for platform clients"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List


class BasePlatformClient(ABC):
    """Abstract base class for all platform clients"""
    
    def __init__(self, email: str):
        self.email = email
        self.platform = self.__class__.__name__.replace('Client', '').lower()
        
    @abstractmethod
    def authenticate(self) -> Dict[str, Any]:
        """
        Authenticate the user with the platform.
        
        Returns:
            Dict containing authentication tokens/credentials
        """
        pass
        
    @abstractmethod
    def get_transport_layers(self) -> List[str]:
        """
        Get list of available transport layers for this platform.
        
        Returns:
            List of transport layer class names
        """
        pass
        
    def __repr__(self):
        return f"{self.__class__.__name__}(email='{self.email}')"