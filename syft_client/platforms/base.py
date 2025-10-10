"""Base class for platform clients"""

import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class TransportRegistry(dict):
    """Custom dict for transports with a nice __repr__"""

    def __repr__(self):
        """String representation using rich for proper formatting"""
        from io import StringIO

        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        # Create a string buffer to capture the rich output
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=70)

        # Create main table
        main_table = Table(show_header=False, show_edge=False, box=None, padding=0)
        main_table.add_column(style="dim")

        if self:
            for transport_name, transport_obj in self.items():
                # Check if transport is set up
                if hasattr(transport_obj, "is_setup") and transport_obj.is_setup():
                    status = "[green]✓[/green]"
                else:
                    status = "[dim]○[/dim]"

                # Show the transport
                main_table.add_row(
                    f"{status} [bold yellow]['{transport_name}'][/bold yellow] = {transport_obj.__class__.__name__}(...)"
                )
        else:
            main_table.add_row("No transports registered")

        # Create the panel
        panel = Panel(
            main_table,
            title="TransportRegistry",
            expand=False,
            width=70,
            padding=(1, 2),
        )

        console.print(panel)
        output = string_buffer.getvalue()
        string_buffer.close()

        return output.strip()


class BasePlatformClient(ABC):
    """Abstract base class for all platform clients"""

    def __dir__(self):
        """Show available attributes for tab completion"""
        # Start with basic attributes
        attrs = ["email", "transports"]

        # Add transport methods if they exist as attributes
        for transport_name in self.get_transport_layers():
            if hasattr(self, transport_name):
                attrs.append(transport_name)

        return attrs

    def __init__(self, email: str, **kwargs):
        self.email = email
        self.platform = self.__class__.__name__.replace("Client", "").lower()
        self._transport_instances = {}  # transport_name -> instance
        # Store any additional kwargs for subclasses that need them
        self.verbose = kwargs.get("verbose", False)
        self._current_environment = None  # Cached environment

    def _sanitize_email(self) -> str:
        """Sanitize email for use in file paths"""
        return self.email.replace("@", "_at_").replace(".", "_")

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
            platform_name = self.platform.replace("client", "")
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
        # If subclass has already initialized transports (like Google clients), use them
        if hasattr(self, "transports") and self.transports:
            return self.transports

        # Otherwise, initialize transports if not already done
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
            module_name = transport_name.replace("Transport", "").lower()

            # Special cases for module names
            module_map = {
                "smtpemail": "email",
                "gdrive_files": "gdrive_files",
                "onedrive_files": "onedrive_files",
                "icloud_files": "icloud_files",
            }

            if module_name in module_map:
                module_name = module_map[module_name]

            # Import the module
            platform_module = self.platform
            transport_module = __import__(
                f"syft_client.platforms.{platform_module}.{module_name}",
                fromlist=[transport_name],
            )

            # Get the transport class and instantiate it
            transport_class = getattr(transport_module, transport_name)
            return transport_class(self.email)
        except Exception:
            return None

    def __repr__(self):
        """String representation using rich for proper formatting"""
        from io import StringIO

        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        # Create a string buffer to capture the rich output
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=100)

        # Create main table
        main_table = Table(show_header=False, show_edge=False, box=None, padding=0)
        main_table.add_column("", no_wrap=False)

        # Add project info if available
        project_info = ""
        if self.platform in ["google_personal", "google_org"]:
            # For Google Org, check if project_id is already loaded
            if (
                self.platform == "google_org"
                and hasattr(self, "project_id")
                and self.project_id
            ):
                project_info = f" [dim](project: {self.project_id})[/dim]"
            else:
                # Try to get from credentials.json
                try:
                    creds_path = None
                    if hasattr(self, "find_oauth_credentials"):
                        creds_path = self.find_oauth_credentials()
                    elif hasattr(self, "credentials_path"):
                        creds_path = self.credentials_path

                    if creds_path and creds_path.exists():
                        import json

                        with open(creds_path, "r") as f:
                            creds_data = json.load(f)
                            if "installed" in creds_data:
                                project_id = creds_data["installed"].get("project_id")
                                if project_id:
                                    project_info = (
                                        f" [dim](project: {project_id})[/dim]"
                                    )
                except:
                    pass

        # Don't show platform header - it's redundant when viewing the platform directly

        # Get transports and their status
        if self.get_transport_layers():
            for transport_name in self.get_transport_layers():
                # Initialize status indicators
                api_status = "[red]✗[/red]"  # Default to not enabled
                auth_status = "[dim]✗[/dim]"  # Not authenticated by default
                transport_style = "dim"
                message = ""

                # Try to get transport as attribute first
                transport_obj = getattr(self, transport_name, None)
                if transport_obj is None and hasattr(self, "transports"):
                    # Fallback to transports dict
                    transport_obj = self.transports.get(transport_name)

                # Check if transport is actually initialized and setup
                transport_initialized = False
                if transport_obj:
                    # Check if this is an initialized transport (not a stub)
                    if (
                        hasattr(transport_obj, "_setup_called")
                        and transport_obj._setup_called
                    ):
                        transport_initialized = True
                        auth_status = "[green]✓[/green]"
                    elif hasattr(transport_obj, "is_setup") and callable(
                        transport_obj.is_setup
                    ):
                        # For fully initialized transports, check is_setup
                        try:
                            if transport_obj.is_setup():
                                transport_initialized = True
                                auth_status = "[green]✓[/green]"
                        except:
                            pass

                # Use static method to check API status
                transport_map = None
                if self.platform == "google_personal":
                    # Import the transport classes to use their static methods
                    transport_map = {
                        "gmail": "syft_client.platforms.google_personal.gmail.GmailTransport",
                        "gdrive_files": "syft_client.platforms.google_personal.gdrive_files.GDriveFilesTransport",
                        "gsheets": "syft_client.platforms.google_personal.gsheets.GSheetsTransport",
                        "gforms": "syft_client.platforms.google_personal.gforms.GFormsTransport",
                    }
                elif self.platform == "google_org":
                    # Import the transport classes to use their static methods
                    transport_map = {
                        "gmail": "syft_client.platforms.google_org.gmail.GmailTransport",
                        "gdrive_files": "syft_client.platforms.google_org.gdrive_files.GDriveFilesTransport",
                        "gsheets": "syft_client.platforms.google_org.gsheets.GSheetsTransport",
                        "gforms": "syft_client.platforms.google_org.gforms.GFormsTransport",
                    }

                if transport_map and transport_name in transport_map:
                    try:
                        # Import the transport class
                        module_path, class_name = transport_map[transport_name].rsplit(
                            ".", 1
                        )
                        module = __import__(module_path, fromlist=[class_name])
                        transport_class = getattr(module, class_name)

                        # Call static method to check API
                        if transport_class.check_api_enabled(self):
                            api_status = "[green]✓[/green]"
                            transport_style = "green"
                        else:
                            api_status = "[red]✗[/red]"
                            transport_style = "dim"
                            # If API is disabled, show enable message
                            message = (
                                f" [dim](call .{transport_name}.enable_api())[/dim]"
                            )
                    except Exception as e:
                        # If check fails, see if it's an API disabled error
                        if "has not been used in project" in str(
                            e
                        ) and "before or it is disabled" in str(e):
                            api_status = "[red]✗[/red]"
                            message = (
                                f" [dim](call .{transport_name}.enable_api())[/dim]"
                            )

                # Set message based on transport initialization status
                if not transport_initialized:
                    # Transport is not initialized
                    if api_status == "[green]✓[/green]":
                        # API is enabled but transport not initialized
                        message = (
                            " [dim](call .init() to initialize)[/dim]"
                            if message == ""
                            else message
                        )
                    else:
                        # API is disabled and transport not initialized
                        if message == "":
                            message = " [dim](not initialized)[/dim]"

                # Get key features for additional info
                features = []
                if transport_obj:
                    if getattr(transport_obj, "is_keystore", False):
                        features.append("keystore")
                    if getattr(transport_obj, "is_notification_layer", False):
                        features.append("notifications")
                    if getattr(transport_obj, "guest_read_file", False):
                        features.append("public sharing")
                    if getattr(transport_obj, "is_html_compatible", False):
                        features.append("HTML")

                # Build feature string for display
                feature_str = ", ".join(features) if features else ""

                # Add transport row with dual status
                transport_row = f"  {api_status} {auth_status} [{transport_style}].{transport_name}[/{transport_style}]{message}"
                if feature_str:
                    transport_row += f" [dim]({feature_str})[/dim]"
                main_table.add_row(transport_row)
        else:
            main_table.add_row("  No transport layers available")

        # Create the panel with the table
        # Include project info in title if available
        title = f"{self.__class__.__name__}(email='{self.email}')"
        if project_info:
            # Extract just the project ID from the formatted string
            import re

            match = re.search(r"project: ([^)]+)", project_info)
            if match:
                title = f"{self.__class__.__name__}(email='{self.email}', project='{match.group(1)}')"

        panel = Panel(main_table, title=title, expand=False, width=100, padding=(1, 2))

        console.print(panel)
        output = string_buffer.getvalue()
        string_buffer.close()

        return output.strip()

    # ===== Configuration Management Methods =====

    def get_config_path(self) -> Path:
        """Get path to platform config file"""
        return Path.home() / ".syft" / self._sanitize_email() / "config.json"

    @property
    def config_path(self) -> Path:
        """Property for config path"""
        return self.get_config_path()

    def load_platform_config(self) -> Dict[str, Any]:
        """Load all platform settings from config file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, "r") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            if self.verbose:
                print(f"Failed to load platform config: {e}")
            return {}

    def save_platform_config(self, config: Dict[str, Any]) -> None:
        """Save wallet and transport preferences"""
        try:
            # Load existing config
            existing_config = self.load_platform_config()

            # Merge with new config
            existing_config.update(config)

            # Add metadata
            existing_config["last_updated"] = datetime.now().isoformat()
            existing_config["platform"] = self.platform
            existing_config["email"] = self.email

            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Save config
            with open(self.config_path, "w") as f:
                json.dump(existing_config, f, indent=2)

            # Set secure permissions
            self.config_path.chmod(0o600)

            if self.verbose:
                print(f"✓ Configuration saved to {self.config_path}")

        except Exception as e:
            if self.verbose:
                print(f"Failed to save platform config: {e}")
            raise
