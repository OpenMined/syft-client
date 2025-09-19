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
        main_table.add_column("Attribute", style="bold cyan")
        main_table.add_column("Value")
        
        # Get the transport name (e.g., 'gmail', 'gdrive_files')
        transport_name = self.__class__.__name__.replace('Transport', '').lower()
        if 'gmail' in transport_name:
            transport_name = 'gmail'
        elif 'gdrive' in transport_name.lower():
            transport_name = 'gdrive_files'
        elif 'gsheets' in transport_name.lower():
            transport_name = 'gsheets'
        elif 'gforms' in transport_name.lower():
            transport_name = 'gforms'
        
        # Status
        status = "[green]✓ Ready[/green]" if self.is_setup() else "[red]✗ Not configured[/red]"
        main_table.add_row(".is_setup()", status)
        
        # Environment
        env_name = self.environment.value if self.environment else "Unknown"
        main_table.add_row(".environment", env_name)
        
        # Capabilities
        main_table.add_row("", "")  # spacer
        main_table.add_row("[bold]Capabilities[/bold]", "")
        
        # Add capability rows with actual attribute names
        capabilities = [
            (".is_keystore", self.is_keystore),
            (".is_notification_layer", self.is_notification_layer),
            (".is_html_compatible", self.is_html_compatible),
            (".is_reply_compatible", self.is_reply_compatible),
            (".guest_submit", self.guest_submit),
            (".guest_read_file", self.guest_read_file),
            (".guest_read_folder", self.guest_read_folder),
        ]
        
        for attr_name, value in capabilities:
            icon = "[green]✓[/green]" if value else "[dim]✗[/dim]"
            main_table.add_row(f"  {attr_name}", icon)
        
        # Complexity
        main_table.add_row("", "")  # spacer
        main_table.add_row(".login_complexity", f"{self.login_complexity} steps")
        
        # Key methods
        main_table.add_row("", "")  # spacer
        main_table.add_row("[bold]Methods[/bold]", "")
        main_table.add_row("  .send(recipient, data)", "Send data")
        main_table.add_row("  .receive()", "Get messages") 
        main_table.add_row("  .setup(credentials)", "Configure transport")
        
        # Create the panel showing how to access this transport
        # Try to infer the platform from the email
        platform = "unknown"
        if hasattr(self, '_platform_client'):
            # If we have a reference to the platform client
            platform = getattr(self._platform_client, 'platform', 'unknown')
        elif '@' in self.email:
            # Guess from email domain
            domain = self.email.split('@')[1].lower()
            if 'gmail.com' in domain:
                platform = 'google_personal'
            elif 'google' in domain or 'workspace' in domain:
                platform = 'google_org'
        
        panel_title = f"client.platforms.{platform}.{transport_name}"
        
        panel = Panel(
            main_table,
            title=panel_title,
            expand=False,
            width=70,
            padding=(1, 2)
        )
        
        console.print(panel)
        output = string_buffer.getvalue()
        string_buffer.close()
        
        return output.strip()