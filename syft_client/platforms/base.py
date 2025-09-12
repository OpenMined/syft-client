"""Base class for platform clients"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List


class BasePlatformClient(ABC):
    """Abstract base class for all platform clients"""
    
    def __dir__(self):
        """Limit tab completion to only show essential attributes"""
        return ['email', 'transports']
    
    def __init__(self, email: str, **kwargs):
        self.email = email
        self.platform = self.__class__.__name__.replace('Client', '').lower()
        self._transport_instances = {}  # transport_name -> instance
        # Store any additional kwargs for subclasses that need them
        self.verbose = kwargs.get('verbose', False)
        self._current_environment = None  # Cached environment
        
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
                f"  • smtp - Generic SMTP/IMAP email (implemented)\n"
                f"  • google_personal - Personal Gmail accounts (implemented)\n\n"
                f"Platforms coming soon:\n"
                f"  • google_org - Google Workspace accounts\n"
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
    def current_environment(self):
        """Get the current environment (Colab, Jupyter, Terminal, etc.) - cached"""
        if self._current_environment is None:
            from ..environment import detect_environment
            self._current_environment = detect_environment()
        return self._current_environment
    
    @property
    def is_interactive(self) -> bool:
        """Check if we're in an interactive environment where we can prompt for input"""
        import sys
        
        # Check for Jupyter/IPython
        try:
            get_ipython()  # This is defined in Jupyter/IPython
            return True
        except NameError:
            pass
        
        # Check if standard input is a terminal (interactive)
        return sys.stdin.isatty()
    
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
    
    def get_transport_instances(self) -> Dict[str, Any]:
        """
        Get all instantiated transport layers for this platform.
        
        Returns:
            Dict mapping transport names to transport instances
        """
        # Initialize transports if not already done
        if not self._transport_instances:
            self._initialize_transports()
        return self._transport_instances
    
    def _initialize_transports(self) -> None:
        """Initialize all transport instances for this platform"""
        transport_names = self.get_transport_layers()
        
        for transport_name in transport_names:
            try:
                transport_instance = self._create_transport_instance(transport_name)
                if transport_instance:
                    self._transport_instances[transport_name] = transport_instance
            except:
                pass  # Skip if transport can't be created
    
    def _create_transport_instance(self, transport_name: str) -> Optional[Any]:
        """
        Create a transport instance by name.
        
        Subclasses can override this to customize transport creation.
        
        Args:
            transport_name: Name of the transport class
            
        Returns:
            Transport instance or None if creation fails
        """
        try:
            # Import transport module dynamically
            # Convert transport name to module name (e.g., GmailTransport -> gmail)
            module_name = transport_name.replace('Transport', '').lower()
            
            # Special cases for module names
            module_map = {
                'smtpemail': 'email',
                'gdrive_files': 'gdrive_files',
                'onedrive_files': 'onedrive_files',
                'icloud_files': 'icloud_files',
            }
            
            if module_name in module_map:
                module_name = module_map[module_name]
            
            # Import the module
            platform_module = self.platform
            transport_module = __import__(
                f'syft_client.platforms.{platform_module}.{module_name}',
                fromlist=[transport_name]
            )
            
            # Get the transport class and instantiate it
            transport_class = getattr(transport_module, transport_name)
            return transport_class(self.email)
        except Exception:
            return None
        
    def __repr__(self):
        return f"{self.__class__.__name__}(email='{self.email}')"