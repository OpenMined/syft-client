class PlatformRegistry:
    def __init__(self, platforms_dict):
        self._platforms = platforms_dict
        self._parent_client = self  # Reference to parent SyftClient

    def __getattr__(self, name):
        if name in self._platforms:
            return self._platforms[name]
        raise AttributeError(f"'platforms' object has no attribute '{name}'")

    def __getitem__(self, key):
        return self._platforms[key]

    def __contains__(self, key):
        return key in self._platforms

    def items(self):
        return self._platforms.items()

    def keys(self):
        return self._platforms.keys()

    def values(self):
        return self._platforms.values()

    def get(self, key, default=None):
        return self._platforms.get(key, default)

    def __dir__(self):
        """Support tab completion for platform names"""
        # Include dict methods and platform names
        return list(self._platforms.keys()) + ["items", "keys", "values", "get"]

    def __repr__(self):
        """String representation showing platforms and their transports"""
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from io import StringIO

        # Create a string buffer to capture the rich output
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=100)

        # Create main table with single column for better formatting
        main_table = Table(show_header=False, show_edge=False, box=None, padding=0)
        main_table.add_column("", no_wrap=False)

        # Add each platform with its transports
        for platform_name, platform in self._platforms.items():
            # Platform header with project info
            platform_header = f"[bold yellow].{platform_name}[/bold yellow]"

            # Try to get project ID from credentials or auth data
            project_info = ""
            if platform_name in ["google_personal", "google_org"]:
                # For Google Org, check if project_id is already loaded
                if (
                    platform_name == "google_org"
                    and hasattr(platform, "project_id")
                    and platform.project_id
                ):
                    project_info = f" [dim](project: {platform.project_id})[/dim]"
                else:
                    # Try to get project ID from credentials file
                    try:
                        creds_path = None
                        if hasattr(platform, "find_oauth_credentials"):
                            creds_path = platform.find_oauth_credentials()
                        elif hasattr(platform, "credentials_path"):
                            creds_path = platform.credentials_path

                        if creds_path and creds_path.exists():
                            import json

                            with open(creds_path, "r") as f:
                                creds_data = json.load(f)
                                if "installed" in creds_data:
                                    project_id = creds_data["installed"].get(
                                        "project_id"
                                    )
                                    if project_id:
                                        project_info = (
                                            f" [dim](project: {project_id})[/dim]"
                                        )
                    except:
                        pass

            main_table.add_row(platform_header + project_info)

            # Get all available transport names (including uninitialized)
            transport_names = platform.get_transport_layers()

            for transport_name in transport_names:
                # Initialize status indicators
                api_status = "[red]✗[/red]"  # Default to not enabled
                auth_status = "[dim]✗[/dim]"  # Not authenticated by default
                transport_style = "dim"
                message = ""

                # Check if transport is actually initialized and setup
                transport_initialized = False
                if (
                    hasattr(platform, "transports")
                    and transport_name in platform.transports
                ):
                    transport = platform.transports[transport_name]
                    # Check if this is an initialized transport (not a stub)
                    if hasattr(transport, "_setup_called") and transport._setup_called:
                        transport_initialized = True
                        auth_status = "[green]✓[/green]"
                    elif hasattr(transport, "is_setup") and callable(
                        transport.is_setup
                    ):
                        # For fully initialized transports, check is_setup
                        try:
                            if transport.is_setup():
                                transport_initialized = True
                                auth_status = "[green]✓[/green]"
                        except:
                            pass

                # Use static method to check API status
                # This works regardless of whether transport is initialized
                transport_map = None
                if platform_name == "google_personal":
                    # Import the transport classes to use their static methods
                    transport_map = {
                        "gmail": "syft_client.platforms.google_personal.gmail.GmailTransport",
                        "gdrive_files": "syft_client.platforms.google_personal.gdrive_files.GDriveFilesTransport",
                        "gsheets": "syft_client.platforms.google_personal.gsheets.GSheetsTransport",
                        "gforms": "syft_client.platforms.google_personal.gforms.GFormsTransport",
                    }
                elif platform_name == "google_org":
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
                        if transport_class.check_api_enabled(platform):
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

                # Show both statuses
                main_table.add_row(
                    f"  {api_status} {auth_status} [{transport_style}].{transport_name}[/{transport_style}]{message}"
                )

        # Create the panel
        panel = Panel(
            main_table,
            title="Platforms",
            expand=False,
            width=100,
            padding=(1, 2),
        )

        console.print(panel)
        output = string_buffer.getvalue()
        string_buffer.close()

        return output.strip()
