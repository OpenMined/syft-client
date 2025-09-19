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
        # Auto-detect environment on initialization
        from ..environment import detect_environment
        self.environment: Optional[Environment] = detect_environment()
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
        
    def setup(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """
        Setup the transport layer with necessary configuration/credentials.
        
        Args:
            credentials: Optional credentials from platform authentication
            
        Returns:
            bool: True if setup successful, False otherwise
        """
        # Default implementation - subclasses can override
        if credentials:
            self._cached_credentials = credentials
        return True
        
    def is_setup(self) -> bool:
        """
        Check if transport layer is properly configured and ready to use.
        
        Returns:
            bool: True if transport is ready, False if setup is needed
        """
        # Default implementation - subclasses should override
        return self._cached_credentials is not None
        
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
        """String representation using rich for proper formatting"""
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from io import StringIO
        
        # Create a string buffer to capture the rich output
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=70)
        
        # Create main table
        main_table = Table(show_header=False, show_edge=False, box=None, padding=0)
        main_table.add_column("Property", style="bold cyan")
        main_table.add_column("Value")
        
        # Status
        status = "[green]✓ Ready[/green]" if self.is_setup() else "[red]✗ Not configured[/red]"
        main_table.add_row("Status", status)
        
        # Environment
        env_name = self.environment.value if self.environment else "Unknown"
        main_table.add_row("Environment", env_name)
        
        # Capabilities
        main_table.add_row("", "")  # spacer
        main_table.add_row("[bold]Capabilities[/bold]", "")
        
        # Add capability rows with checkmarks/crosses
        capabilities = [
            ("Keystore", self.is_keystore),
            ("Notifications", self.is_notification_layer),
            ("HTML Support", self.is_html_compatible),
            ("Reply Support", self.is_reply_compatible),
            ("Guest Submit", self.guest_submit),
            ("Guest Read Files", self.guest_read_file),
            ("Guest Read Folders", self.guest_read_folder),
        ]
        
        for name, value in capabilities:
            icon = "[green]✓[/green]" if value else "[dim]✗[/dim]"
            main_table.add_row(f"  {name}", icon)
        
        # Complexity
        main_table.add_row("", "")  # spacer
        main_table.add_row("Setup Complexity", f"{self.login_complexity} steps")
        
        # Create the panel
        panel = Panel(
            main_table,
            title=f"{self.__class__.__name__}(email='{self.email}')",
            expand=False,
            width=70,
            padding=(1, 2)
        )
        
        console.print(panel)
        output = string_buffer.getvalue()
        string_buffer.close()
        
        return output.strip()