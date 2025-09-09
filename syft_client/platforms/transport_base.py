"""Base class for all transport layers"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..environment import Environment


class BaseTransportLayer(ABC):
    """Abstract base class for all transport layers"""
    
    # STATIC Attributes (to be overridden by subclasses)
    # Security
    is_keystore: bool = False  # Do we trust this layer to hold auth keys for other layers?
    
    # Notifications
    is_notification_layer: bool = False  # Does user regularly check this for messages?
    is_html_compatible: bool = False  # Can this layer render HTML?
    is_reply_compatible: bool = False  # Can this layer natively support replies?
    
    # Cross-Platform Interoperability
    guest_submit: bool = False  # Can guests submit without an account?
    guest_read_file: bool = False  # Can guests read files with a URL?
    guest_read_folder: bool = False  # Can guests access folders?
    
    def __init__(self, email: str):
        self.email = email
        self.environment: Optional[Environment] = None
        self.api_is_active: bool = False
        self._cached_credentials: Optional[Dict[str, Any]] = None
        
    @property
    def api_is_active_by_default(self) -> bool:
        """Is API active by default in current environment?"""
        # Override in subclasses based on environment
        return False
        
    def set_env_type(self, env: Environment) -> None:
        """Set the environment type"""
        self.environment = env
        
    def get_env_type(self) -> Optional[Environment]:
        """Get the current environment type"""
        return self.environment
        
    @property
    @abstractmethod
    def login_complexity(self) -> int:
        """
        Returns the ADDITIONAL steps required for transport setup.
        
        This is IN ADDITION to platform authentication complexity.
        Total complexity = platform.login_complexity + transport.login_complexity
        
        Returns:
            0: No additional setup needed (just uses platform auth)
            1: One additional step (e.g., enable API)
            2+: Multiple steps (e.g., create project, enable API, create resources)
        """
        pass
    
    @property
    def total_complexity(self) -> int:
        """
        Total login complexity including platform authentication.
        
        Returns:
            -1 if platform auth not available
            Otherwise: platform complexity + transport complexity
        """
        # This would need access to the platform client
        # For now, just return transport complexity
        return self.login_complexity
        
    @abstractmethod
    def authenticate(self) -> Dict[str, Any]:
        """Authenticate with the transport layer"""
        pass
        
    @abstractmethod
    def send(self, recipient: str, data: Any) -> bool:
        """Send data to a recipient"""
        pass
        
    @abstractmethod
    def receive(self) -> List[Dict[str, Any]]:
        """Receive messages from this transport layer"""
        pass
        
    def contacts(self) -> List[Dict[str, str]]:
        """Get list of contacts and their transport layers"""
        # TODO: Implement contact discovery
        return []
        
    def __repr__(self):
        return f"{self.__class__.__name__}(email='{self.email}')"