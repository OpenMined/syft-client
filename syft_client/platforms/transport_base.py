"""Base class for all transport layers"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path
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
        self._platform_client = None  # Will be set by platform client
        
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
    
    def is_cached_as_setup(self) -> bool:
        """Check if this transport is cached as successfully set up"""
        # Cache has been removed, always return False
        return False
        
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
    
    @staticmethod
    def check_api_enabled(platform_client: Any) -> bool:
        """
        Check if the API for this transport is enabled.
        
        This is a static method that can be called without initializing the transport.
        
        Args:
            platform_client: The platform client with credentials
            
        Returns:
            bool: True if API is enabled, False otherwise
        """
        # Default implementation - subclasses should override
        return False
    
    @staticmethod
    def enable_api_static(transport_name: str, email: str) -> None:
        """
        Static method to show instructions for enabling the API.
        
        Args:
            transport_name: Name of the transport (e.g., 'gmail', 'gdrive_files')
            email: User's email address
        """
        # Default implementation - subclasses should override
        print(f"\n🔧 To enable the API for {transport_name}:")
        print(f"   Please check the platform-specific instructions.")
    
    @staticmethod
    def disable_api_static(transport_name: str, email: str) -> None:
        """
        Static method to show instructions for disabling the API.
        
        Args:
            transport_name: Name of the transport (e.g., 'gmail', 'gdrive_files')
            email: User's email address
        """
        # Default implementation - subclasses should override
        print(f"\n🔧 To disable the API for {transport_name}:")
        print(f"   Please check the platform-specific instructions.")
        
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
        
    def init(self, verbose: bool = True) -> bool:
        """Initialize transport - for already initialized transports, this is a no-op"""
        if verbose:
            from rich.console import Console
            from rich.panel import Panel
            
            console = Console()
            transport_name = self.__class__.__name__.replace('Transport', '').lower()
            
            # Get platform name if available
            platform_path = "client.platforms.<platform>"
            if hasattr(self, '_platform_client') and self._platform_client:
                platform_name = getattr(self._platform_client, 'platform', '<platform>')
                platform_path = f"client.platforms.{platform_name}"
            
            info_lines = [
                f"[bold green]✓ {transport_name} transport is already initialized![/bold green]",
                "",
                "No action needed - this transport is ready to use.",
                "",
                "[bold]Available methods:[/bold]"
            ]
            
            # Add transport-specific methods
            if 'gmail' in transport_name:
                info_lines.extend([
                    "  • Send emails: [cyan].send(recipient, data, subject)[/cyan]",
                    "  • Read emails: [cyan].receive(limit=10)[/cyan]",
                    "  • Test setup: [cyan].test()[/cyan]"
                ])
            elif 'gdrive' in transport_name.lower():
                info_lines.extend([
                    "  • List files: [cyan].list_files()[/cyan]",
                    "  • Upload file: [cyan].upload_file(filepath)[/cyan]",
                    "  • Download file: [cyan].download_file(file_id, save_path)[/cyan]"
                ])
            elif 'gsheets' in transport_name.lower():
                info_lines.extend([
                    "  • Read sheet: [cyan].read_sheet(spreadsheet_id, range)[/cyan]",
                    "  • Write data: [cyan].write_sheet(spreadsheet_id, range, values)[/cyan]",
                    "  • Create sheet: [cyan].create_sheet(title)[/cyan]"
                ])
            elif 'gforms' in transport_name.lower():
                info_lines.extend([
                    "  • List forms: [cyan].list_forms()[/cyan]",
                    "  • Get responses: [cyan].get_responses(form_id)[/cyan]",
                    "  • Create form: [cyan].create_form(title)[/cyan]"
                ])
            
            info_lines.extend([
                "",
                f"[dim]Access via: {platform_path}.{transport_name}[/dim]"
            ])
            
            panel = Panel("\n".join(info_lines), expand=False, border_style="green")
            console.print(panel)
        
        return True
    
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
        
        # Transport initialization status
        status = "[green]✓ Initialized[/green]" if self.is_setup() else "[red]✗ Not initialized[/red]"
        main_table.add_row(".is_initialized()", status)
        
        # API status - check if API is enabled using static method
        api_status = "[dim]Unknown[/dim]"
        if hasattr(self, '_platform_client') and self._platform_client:
            # Use the static method to check API status
            try:
                if self.__class__.check_api_enabled(self._platform_client):
                    api_status = "[green]✓ Enabled[/green]"
                else:
                    api_status = "[red]✗ Disabled[/red]"
            except:
                # If check fails, keep as Unknown
                pass
        main_table.add_row(".api_enabled", api_status)
        
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
        main_table.add_row("  .enable_api()", "Show enable instructions")
        main_table.add_row("  .disable_api()", "Show disable instructions")
        
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
    
    def check_api_error(self) -> None:
        """Check and display the last API error for debugging"""
        if hasattr(self, '_last_error'):
            print(f"Last error: {self._last_error}")
        if hasattr(self, '_last_api_error'):
            print(f"API error type: {self._last_api_error}")
        if hasattr(self, '_setup_verified'):
            print(f"Setup verified: {self._setup_verified}")
    
    def enable_api(self) -> None:
        """Guide user through enabling the API for this transport"""
        # Get transport name
        transport_name = self.__class__.__name__.replace('Transport', '').lower()
        if 'gdrive' in transport_name:
            transport_name = 'gdrive_files'
        
        # Get project_id from platform client if available
        project_id = None
        if hasattr(self, '_platform_client') and self._platform_client:
            project_id = getattr(self._platform_client, 'project_id', None)
        
        # Call the static method with project_id
        self.__class__.enable_api_static(transport_name, self.email, project_id)
    
    def disable_api(self) -> None:
        """Show instructions for disabling the API for this transport"""
        # Get transport name
        transport_name = self.__class__.__name__.replace('Transport', '').lower()
        if 'gdrive' in transport_name:
            transport_name = 'gdrive_files'
        
        # Get project_id from platform client if available
        project_id = None
        if hasattr(self, '_platform_client') and self._platform_client:
            project_id = getattr(self._platform_client, 'project_id', None)
        
        # Call the static method with project_id
        self.__class__.disable_api_static(transport_name, self.email, project_id)