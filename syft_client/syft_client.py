"""
SyftClient class - Main client object that manages platforms and transport layers
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .environment import Environment, detect_environment
from .platforms.base import BasePlatformClient
from .platforms.detection import (
    Platform,
    PlatformDetector,
    detect_primary_platform,
    get_secondary_platforms,
)


def resolve_path(
    path: Union[str, Path], syftbox_folder: Optional[Union[str, Path]] = None
) -> Path:
    """
    Resolve syft:// paths to absolute filesystem paths.

    This function converts syft:// URLs to actual filesystem paths by replacing
    the syft:// prefix with the SyftBox folder location.

    Args:
        path: Path to resolve (e.g., "syft://path/to/dir")
        syftbox_folder: SyftBox folder location. If not provided, will use
                       SYFTBOX_FOLDER environment variable.

    Returns:
        Resolved pathlib.Path object

    Raises:
        ValueError: If syftbox_folder not provided and SYFTBOX_FOLDER env var not set
        ValueError: If path doesn't start with syft://

    Examples:
        >>> resolve_path("syft://datasites/user/data", "/home/user/SyftBox")
        PosixPath('/home/user/SyftBox/datasites/user/data')

        >>> os.environ['SYFTBOX_FOLDER'] = '/home/user/SyftBox'
        >>> resolve_path("syft://apps/myapp")
        PosixPath('/home/user/SyftBox/apps/myapp')
    """
    # Convert path to string for processing
    # Handle case where Path object might normalize syft:// to syft:/
    if isinstance(path, Path):
        path_str = str(path)
        # Fix Path normalization of syft:// -> syft:/
        if path_str.startswith("syft:/") and not path_str.startswith("syft://"):
            path_str = path_str.replace("syft:/", "syft://", 1)
    else:
        path_str = str(path)

    # Check if path starts with syft://
    if not path_str.startswith("syft://"):
        raise ValueError(f"Path must start with 'syft://', got: {path_str}")

    # Determine syftbox folder
    if syftbox_folder is not None:
        base_folder = Path(syftbox_folder)
    else:
        env_folder = os.environ.get("SYFTBOX_FOLDER")
        if env_folder is None:
            raise ValueError(
                "SYFTBOX_FOLDER environment variable not set. "
                "Please either:\n"
                "1. Set the environment variable: export SYFTBOX_FOLDER=/path/to/syftbox\n"
                "2. Pass syftbox_folder parameter: resolve_path(path, syftbox_folder='/path/to/syftbox')"
            )
        base_folder = Path(env_folder)

    # Remove syft:// prefix and resolve path
    relative_path = path_str[7:]  # Remove "syft://" (7 characters)

    # Handle empty path after syft://
    if not relative_path:
        return base_folder

    # Join with base folder and return
    return base_folder / relative_path


class SyftClient:
    """
    Main client object that manages multiple platforms for a single email

    A SyftClient represents an authenticated session for a single email account
    that can have multiple platforms (e.g., Gmail + Dropbox with same email).
    """

    def __init__(self, email: str):
        """
        Initialize a SyftClient for a specific email

        Args:
            email: The email address for this client
        """
        self.email = email
        self._platforms: Dict[str, BasePlatformClient] = {}
        self.transport_instances: Dict[str, Any] = {}  # platform:transport -> instance
        self.local_syftbox_dir: Optional[Path] = None
        self._sync = None  # Lazy-loaded sync manager
        self.verbose = True  # Default verbose mode
        self._job_client = None  # Cache for lazy-loaded job client

    @property
    def servers(self):
        import syft_serve as ss

        return ss.servers

    @property
    def platforms(self):
        """Provide attribute-style access to platforms"""

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
                from io import StringIO

                from rich.console import Console
                from rich.panel import Panel
                from rich.table import Table

                # Create a string buffer to capture the rich output
                string_buffer = StringIO()
                console = Console(file=string_buffer, force_terminal=True, width=100)

                # Create main table with single column for better formatting
                main_table = Table(
                    show_header=False, show_edge=False, box=None, padding=0
                )
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
                            project_info = (
                                f" [dim](project: {platform.project_id})[/dim]"
                            )
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
                                                project_info = f" [dim](project: {project_id})[/dim]"
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
                            if (
                                hasattr(transport, "_setup_called")
                                and transport._setup_called
                            ):
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
                                module_path, class_name = transport_map[
                                    transport_name
                                ].rsplit(".", 1)
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
                                    message = f" [dim](call .{transport_name}.enable_api())[/dim]"
                            except Exception as e:
                                # If check fails, see if it's an API disabled error
                                if "has not been used in project" in str(
                                    e
                                ) and "before or it is disabled" in str(e):
                                    api_status = "[red]✗[/red]"
                                    message = f" [dim](call .{transport_name}.enable_api())[/dim]"

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

        return PlatformRegistry(self._platforms)

    def _initialize_all_transports(self) -> None:
        """Initialize transport instances for all possible platforms"""
        from .platforms import get_platform_client

        # Initialize transports for secondary platforms
        for platform in get_secondary_platforms():
            try:
                platform_client = get_platform_client(platform, self.email)
                self._add_platform_transports(platform.value, platform_client)
            except:
                pass  # Skip if platform client can't be created

    def _add_platform_transports(
        self, platform_name: str, platform_client: BasePlatformClient
    ) -> None:
        """Add transport instances from a platform client to our registry"""
        platform_transports = platform_client.get_transport_instances()

        for transport_name, transport_instance in platform_transports.items():
            key = f"{platform_name}:{transport_name}"
            self.transport_instances[key] = transport_instance

    def add_platform(
        self, platform_client: BasePlatformClient, auth_data: Dict[str, Any]
    ) -> None:
        """
        Add an authenticated platform to this client

        Args:
            platform_client: The authenticated platform client
            auth_data: Authentication data from the platform
        """
        platform_name = platform_client.platform
        self._platforms[platform_name] = platform_client

        # Store auth data in the platform client for now
        platform_client._auth_data = auth_data

        # Add transports from this platform
        self._add_platform_transports(platform_name, platform_client)

    def _create_local_syftbox_directory(self) -> None:
        """Create the local SyftBox directory structure"""
        if not self.email:
            return

        # Always use home directory as the primary location
        # For Colab, we'll create a convenience symlink in /content
        syftbox_dir = Path.home() / f"SyftBox_{self.email}"

        if not syftbox_dir.exists():
            try:
                syftbox_dir.mkdir(exist_ok=True)
                print(f"📁 Created local SyftBox directory: {syftbox_dir}")

                # Create subdirectories
                subdirs = ["datasites", "apps"]
                for subdir in subdirs:
                    (syftbox_dir / subdir).mkdir(exist_ok=True)

            except Exception as e:
                print(f"⚠️  Could not create SyftBox directory: {e}")
        else:
            print(f"📁 Using existing SyftBox directory: {syftbox_dir}")

        # Store the path for later use
        self.local_syftbox_dir = syftbox_dir

        # Create Colab convenience symlink if in Colab environment
        from .core.colab_utils import setup_colab_symlink

        setup_colab_symlink(syftbox_dir, verbose=self.verbose)

    def _sanitize_email(self) -> str:
        """Sanitize email for use in file paths"""
        return self.email.replace("@", "_at_").replace(".", "_")

    # TODO: Rethink this strategy, when syft-job is an isolated app
    def _setup_job_directories(self) -> None:
        """
        Setup job directory structure if syft-job is available.
        Creates: SyftBox/datasites/<email>/app_data/job/{inbox,approved,done}
        """
        # Check if syft-job is available (silently skip if not)
        try:
            import syft_job
        except ImportError:
            return

        # Use the .folder property to get SyftBox directory
        syftbox_dir = self.get_syftbox_directory()
        if not syftbox_dir:
            return

        try:
            # Create the job base directory structure
            job_base_dir = syftbox_dir / "datasites" / self.email / "app_data" / "job"
            job_base_dir.mkdir(parents=True, exist_ok=True)

        except Exception as e:
            # Print error if directory creation fails
            print(f"⚠️  Could not create job directories: {e}")

    # TODO: Temporary workaround until we shift from syft-serve to using
    # app scheduler for scheduling apps in syft-client
    def _create_job_runner_functions(self, syftbox_folder: str, poll_interval: int = 1):
        """Factory that returns syft-serve compatible functions"""

        def start_runner():
            """Function compatible with syft-serve"""
            import os
            import tempfile
            import threading
            from pathlib import Path

            # Use a file-based lock
            lock_file = (
                Path(tempfile.gettempdir())
                / f"job_runner_{abs(hash(syftbox_folder))}.lock"
            )

            # Try to create lock file atomically
            try:
                fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
            except OSError:
                # Lock file exists, check if process is still running
                try:
                    with open(lock_file, "r") as f:
                        pid = int(f.read().strip())
                        os.kill(pid, 0)  # Check if process exists
                    return {"status": "already_running"}
                except (ValueError, ProcessLookupError, FileNotFoundError):
                    # Stale lock file, remove it
                    lock_file.unlink(missing_ok=True)
                    try:
                        fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                        os.write(fd, str(os.getpid()).encode())
                        os.close(fd)
                    except OSError:
                        return {"status": "error", "message": "Failed to acquire lock"}

            def _main_job_runner():

                from syft_job.job_runner import create_runner

                runner = create_runner(str(syftbox_folder), poll_interval)
                runner.run()

            # Start the job
            thread = threading.Thread(target=_main_job_runner, daemon=True)
            thread.start()

            return {"syftbox_folder": syftbox_folder, "poll_interval": poll_interval}

        return start_runner

    def _setup_job_runner(self) -> None:
        """
        Setup job runner if syft-job is available
        """

        # Check if syft-job is available (silently skip if not)
        try:
            import syft_job

            # if self.verbose:
            #     print("✓ syft-job module found, setting up job runner...")
        except ImportError:
            if self.verbose:
                print("⚠️  syft-job not found, skipping job runner setup")
            return

        # lazy load
        import requests
        import syft_serve as ss
        from syft_serve._exceptions import ServerAlreadyExistsError

        # Setup Job Directories
        self._setup_job_directories()

        # Create Job Runner
        # Step 1: Create the functions
        start_fn = self._create_job_runner_functions(self.folder, poll_interval=1)

        # Step 2: Create syft-serve server
        try:
            # if self.verbose:
            #     print(f"🚀 Starting job runner server for {self._sanitize_email()}...")
            server = ss.create(
                name=f"job_runner_{self._sanitize_email()}",
                endpoints={
                    "/start": start_fn,
                },
                dependencies=["syft-job>=0.1.6"],
            )
            # if self.verbose:
            #     print(f"✓ Job runner started on port {server.port}")
        except ServerAlreadyExistsError:
            # if self.verbose:
            #     print(f"ℹ️  Job runner already exists for {self._sanitize_email()}")
            server = ss.servers[f"job_runner_{self._sanitize_email()}"]
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to create job runner: {e}")
            raise

        res = requests.get(f"{server.url}/start")
        res.raise_for_status()
        # if self.verbose:
        #     print("✓ Job runner started successfully")

    def get_syftbox_directory(self) -> Optional[Path]:
        """Get the local SyftBox directory path"""
        if self.local_syftbox_dir:
            return self.local_syftbox_dir
        elif self.email:
            # Calculate the path even if not created yet
            # Check if we're in Colab
            environment = detect_environment()
            if environment == Environment.COLAB:
                # In Colab, use /content directory
                base_dir = Path("/content")
            else:
                # Otherwise use home directory
                base_dir = Path.home()
            return base_dir / f"SyftBox_{self.email}"
        return None

    def download_gdrive_folder(self, folder_name: str, local_path: str, recursive: bool = True) -> bool:
        """
        Download entire folder from Google Drive to local system (convenience method)
        
        This is a shorthand for client.platforms.google_org.download_gdrive_folder()
        
        Args:
            folder_name: Name of the folder on Google Drive to download
            local_path: Local directory path where the folder should be downloaded
            recursive: Whether to download subfolders recursively (default: True)
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            ValueError: If Google Org platform is not available or set up
        """
        # Check if Google Org platform is available
        if "google_org" not in self._platforms:
            raise ValueError(
                "Google Org platform not available. Please set up Google Workspace authentication first.\n"
                "Try: client.platforms.google_org.authenticate()"
            )
        
        google_org_client = self._platforms["google_org"]
        
        # Check if the platform is authenticated and set up
        if not hasattr(google_org_client, 'gdrive_files') or not google_org_client.gdrive_files.is_setup():
            raise ValueError(
                "Google Drive is not set up. Please authenticate and set up Google Drive first.\n"
                "Try: client.platforms.google_org.authenticate()"
            )
        
        # Delegate to the Google Org platform
        return google_org_client.download_gdrive_folder(folder_name, local_path, recursive)

    @property
    def folder(self) -> Optional[str]:
        """Get the local SyftBox directory path as a string"""
        syftbox_dir = self.get_syftbox_directory()
        return str(syftbox_dir) if syftbox_dir else None

    def _get_job_client(self):
        """
        Get the syft-job client instance (lazy-loaded and cached)

        Returns:
            Job client from syft_job.get_client(folder)

        Raises:
            ImportError: If syft-job package is not installed
        """
        if self._job_client is None:
            try:
                import syft_job as sj

                self._job_client = sj.get_client(self.folder)
            except ImportError:
                raise ImportError(
                    "syft-job package is not installed. "
                    "Install it with: pip install syft-client[job]"
                )
        return self._job_client

    @property
    def jobs(self):
        """
        Access to jobs interface from syft-job package

        Returns:
            Jobs interface from job_client.jobs
        """
        return self._get_job_client().jobs

    def submit_bash_job(self, *args, **kwargs):
        """
        Submit a bash job using the syft-job package

        This method delegates to job_client.submit_bash_job()

        Args:
            *args: Positional arguments passed to submit_bash_job
            **kwargs: Keyword arguments passed to submit_bash_job

        Returns:
            Result from job_client.submit_bash_job()
        """
        return self._get_job_client().submit_bash_job(*args, **kwargs)

    def submit_python_job(self, *args, **kwargs):
        """
        Submit a python job using the syft-job package

        This method delegates to job_client.submit_python_job()

        Args:
            *args: Positional arguments passed to submit_python_job
            **kwargs: Keyword arguments passed to submit_python_job

        Returns:
            Result from job_client.submit_python_job()
        """
        return self._get_job_client().submit_python_job(*args, **kwargs)

    @property
    def sync(self):
        """Lazy-loaded sync manager for messaging and peer management"""
        if self._sync is None:
            from .sync import SyncManager

            self._sync = SyncManager(self)
        return self._sync

    @property
    def _watcher_manager(self):
        """Internal watcher manager access"""
        if not hasattr(self, "__watcher_manager"):
            from .sync.watcher import WatcherManager

            self.__watcher_manager = WatcherManager(self)
        return self.__watcher_manager

    @property
    def _receiver_manager(self):
        """Internal receiver manager access"""
        if not hasattr(self, "__receiver_manager"):
            from .sync.receiver import ReceiverManager

            self.__receiver_manager = ReceiverManager(self)
        return self.__receiver_manager

    @property
    def watcher(self):
        """Get the watcher syft-serve Server object for viewing logs"""
        try:
            import syft_serve as ss

            server_name = (
                f"watcher_sender_{self.email.replace('@', '_at_').replace('.', '_')}"
            )

            # Try to get the server
            servers = ss.servers
            for server in servers:
                if server.name == server_name:
                    return server

            # Server not found
            return None
        except ImportError:
            # syft-serve not installed
            return None

    @property
    def receiver(self):
        """Get the receiver syft-serve Server object for viewing logs"""
        try:
            import syft_serve as ss

            server_name = (
                f"receiver_{self.email.replace('@', '_at_').replace('.', '_')}"
            )

            # Try to get the server
            servers = ss.servers
            for server in servers:
                if server.name == server_name:
                    return server

            # Server not found
            return None
        except ImportError:
            # syft-serve not installed
            return None

    @property
    def job_runner(self):
        """Get the job runner syft-serve Server object for viewing logs"""
        try:
            import syft_serve as ss

            server_name = (
                f"job_runner_{self.email.replace('@', '_at_').replace('.', '_')}"
            )

            # Try to get the server
            servers = ss.servers
            for server in servers:
                if server.name == server_name:
                    return server

            # Server not found
            return None
        except ImportError:
            # syft-serve not installed
            return None

    @property
    def logs(self):
        """Combined live logs view for all servers"""

        class LogsView:
            def __init__(self, client):
                self.client = client

            def _repr_html_(self):
                """Generate HTML for combined live logs display"""
                # Get all three servers
                servers = []
                if self.client.watcher:
                    servers.append(("Watcher", self.client.watcher))
                if self.client.receiver:
                    servers.append(("Receiver", self.client.receiver))
                if self.client.job_runner:
                    servers.append(("Job Runner", self.client.job_runner))

                if not servers:
                    return "<div style='padding: 20px; color: #666;'>No servers running</div>"

                # Detect dark mode
                try:
                    from jupyter_dark_detect import is_dark

                    is_dark_mode = is_dark()
                except:
                    is_dark_mode = False

                # Theme colors
                if is_dark_mode:
                    bg_color = "#1e1e1e"
                    border_color = "#3e3e3e"
                    text_color = "#e0e0e0"
                    label_color = "#a0a0a0"
                    log_bg = "#1a1a1a"
                    error_bg = "#1a1a1a"
                    log_text_color = "#9ca3af"
                    error_text_color = "#ff6b6b"
                else:
                    bg_color = "#ffffff"
                    border_color = "#ddd"
                    text_color = "#333"
                    label_color = "#666"
                    log_bg = "#f8f9fa"
                    error_bg = "#fef2f2"
                    log_text_color = "#374151"
                    error_text_color = "#d73a49"

                # Generate unique ID for this instance
                import uuid

                instance_id = str(uuid.uuid4())[:8]

                # Build HTML
                html_parts = [
                    f"""
                <div style="background: {bg_color}; border: 1px solid {border_color}; border-radius: 5px; padding: 15px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                    <h3 style="margin: 0 0 15px 0; color: {text_color};">📊 Live Server Logs - {self.client.email}</h3>
                """
                ]

                # Create a section for each server
                for server_name, server in servers:
                    server_id = f"{server_name.lower().replace(' ', '_')}_{instance_id}"
                    html_parts.append(
                        f"""
                    <div style="margin-bottom: 20px;">
                        <h4 style="color: {text_color}; margin: 0 0 10px 0;">
                            {'🚀' if server_name == 'Watcher' else '📥' if server_name == 'Receiver' else '🏃'} {server_name}
                            <span style="color: {label_color}; font-size: 0.9em;">(port {server.port})</span>
                        </h4>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                            <div style="padding: 8px; background: {log_bg}; border-radius: 3px; border: 1px solid {border_color};">
                                <div style="color: {label_color}; font-size: 11px; margin-bottom: 5px;">stdout:</div>
                                <div id="stdout-{server_id}" style="font-size: 11px; color: {log_text_color}; height: 120px; overflow-y: auto; font-family: monospace; white-space: pre-wrap; word-wrap: break-word;">
                                    <em style="color: #888;">Loading...</em>
                                </div>
                            </div>
                            <div style="padding: 8px; background: {error_bg}; border-radius: 3px; border: 1px solid {border_color};">
                                <div style="color: {label_color}; font-size: 11px; margin-bottom: 5px;">stderr:</div>
                                <div id="stderr-{server_id}" style="font-size: 11px; color: {error_text_color}; height: 120px; overflow-y: auto; font-family: monospace; white-space: pre-wrap; word-wrap: break-word;">
                                    <em style="color: #888;">Loading...</em>
                                </div>
                            </div>
                        </div>
                    </div>
                    """
                    )

                # Add JavaScript for all servers
                html_parts.append(
                    """
                    <script>
                    (function() {
                """
                )

                # Create update functions for each server
                for server_name, server in servers:
                    server_id = f"{server_name.lower().replace(' ', '_')}_{instance_id}"
                    html_parts.append(
                        f"""
                        // {server_name} update function
                        const update_{server_id} = async function() {{
                            const port = {server.port};
                            const stdoutDiv = document.getElementById('stdout-{server_id}');
                            const stderrDiv = document.getElementById('stderr-{server_id}');

                            if (!stdoutDiv || !stderrDiv) return;

                            let baseUrl = 'http://localhost:' + port;
                            if (window.location.hostname.includes('googleusercontent.com')) {{
                                baseUrl = window.location.origin + '/proxy/' + port;
                            }}

                            try {{
                                // Fetch stdout
                                const stdoutResponse = await fetch(baseUrl + '/logs/stdout?lines=30');
                                if (stdoutResponse.ok) {{
                                    const stdoutData = await stdoutResponse.json();
                                    if (stdoutData.lines && stdoutData.lines.length > 0) {{
                                        // Check if we're at the bottom before updating
                                        const wasAtBottom = stdoutDiv.scrollHeight - stdoutDiv.scrollTop <= stdoutDiv.clientHeight + 5;

                                        stdoutDiv.innerHTML = stdoutData.lines
                                            .map(line => line.replace(/</g, '&lt;').replace(/>/g, '&gt;'))
                                            .join('');

                                        // Only auto-scroll if we were already at the bottom
                                        if (wasAtBottom) {{
                                            stdoutDiv.scrollTop = stdoutDiv.scrollHeight;
                                        }}
                                    }} else {{
                                        stdoutDiv.innerHTML = '<em style="color: #888;">No output</em>';
                                    }}
                                }}

                                // Fetch stderr
                                const stderrResponse = await fetch(baseUrl + '/logs/stderr?lines=30');
                                if (stderrResponse.ok) {{
                                    const stderrData = await stderrResponse.json();
                                    if (stderrData.lines && stderrData.lines.length > 0) {{
                                        // Check if we're at the bottom before updating
                                        const wasAtBottom = stderrDiv.scrollHeight - stderrDiv.scrollTop <= stderrDiv.clientHeight + 5;

                                        stderrDiv.innerHTML = stderrData.lines
                                            .map(line => line.replace(/</g, '&lt;').replace(/>/g, '&gt;'))
                                            .join('');

                                        // Only auto-scroll if we were already at the bottom
                                        if (wasAtBottom) {{
                                            stderrDiv.scrollTop = stderrDiv.scrollHeight;
                                        }}
                                    }} else {{
                                        stderrDiv.innerHTML = '<em style="color: #888;">No errors</em>';
                                    }}
                                }}
                            }} catch (error) {{
                                // Server might be down
                            }}
                        }};
                    """
                    )

                # Initial update and set intervals
                html_parts.append(
                    """
                        // Clean up any existing intervals
                        const intervalKey = 'syftLogsInterval_' + '"""
                    + instance_id
                    + """';
                        if (window[intervalKey]) {
                            clearInterval(window[intervalKey]);
                        }

                        // Initial update for all servers
                """
                )

                for server_name, server in servers:
                    server_id = f"{server_name.lower().replace(' ', '_')}_{instance_id}"
                    html_parts.append(f"        update_{server_id}();\n")

                html_parts.append(
                    """
                        // Set up polling
                        window[intervalKey] = setInterval(function() {
                """
                )

                for server_name, server in servers:
                    server_id = f"{server_name.lower().replace(' ', '_')}_{instance_id}"
                    html_parts.append(f"            update_{server_id}();\n")

                html_parts.append(
                    """
                        }, 1000);
                    })();
                    </script>
                </div>
                """
                )

                return "".join(html_parts)

            def __repr__(self):
                """Text representation for non-notebook environments"""
                servers_status = []
                if self.client.watcher:
                    servers_status.append(f"Watcher: port {self.client.watcher.port}")
                if self.client.receiver:
                    servers_status.append(f"Receiver: port {self.client.receiver.port}")
                if self.client.job_runner:
                    servers_status.append(
                        f"Job Runner: port {self.client.job_runner.port}"
                    )

                if servers_status:
                    return f"LogsView({', '.join(servers_status)})"
                else:
                    return "LogsView(No servers running)"

        return LogsView(self)

    # High-level sync API methods
    def send_to_peers(self, path: str) -> Dict[str, bool]:
        """
        Send file/folder to all peers

        Args:
            path: Path to file/folder (supports syft:// URLs)

        Returns:
            Dict mapping peer emails to success status
        """
        return self.sync.send_to_peers(path)

    def send_to(
        self,
        path: str,
        recipient: str,
        requested_latency_ms: Optional[int] = None,
        priority: str = "normal",
        transport: Optional[str] = None,
    ) -> bool:
        """
        Send file/folder to specific recipient

        Args:
            path: Path to file/folder (supports syft:// URLs)
            recipient: Email address of recipient
            requested_latency_ms: Desired latency in milliseconds (optional)
            priority: "urgent", "normal", or "background" (default: "normal")
            transport: Specific transport to use (e.g., "gdrive_files", "gsheets", "gmail").
                      If None, automatically selects best transport.

        Returns:
            True if successful
        """
        return self.sync.send_to(
            path, recipient, requested_latency_ms, priority, transport
        )

    def send_deletion_to_peers(self, path: str) -> Dict[str, bool]:
        """
        Send deletion message to all peers

        Args:
            path: Path to the deleted file (supports syft:// URLs)

        Returns:
            Dict mapping peer emails to success status
        """
        return self.sync.send_deletion_to_peers(path)

    def send_deletion(self, path: str, recipient: str) -> bool:
        """
        Send deletion message to specific recipient

        Args:
            path: Path to the deleted file (supports syft:// URLs)
            recipient: Email address of recipient

        Returns:
            True if successful
        """
        return self.sync.send_deletion(path, recipient)

    def send_move_to_peers(self, source_path: str, dest_path: str) -> Dict[str, bool]:
        """
        Send move message to all peers

        Args:
            source_path: Path to the source file/directory (supports syft:// URLs)
            dest_path: Path to the destination file/directory (supports syft:// URLs)

        Returns:
            Dict mapping peer emails to success status
        """
        return self.sync.send_move_to_peers(source_path, dest_path)

    def send_move(self, source_path: str, dest_path: str, recipient: str) -> bool:
        """
        Send move message to specific recipient

        Args:
            source_path: Path to the source file/directory (supports syft:// URLs)
            dest_path: Path to the destination file/directory (supports syft:// URLs)
            recipient: Email address of recipient

        Returns:
            True if successful
        """
        return self.sync.send_move(source_path, dest_path, recipient)

    def add_peer(self, email: str) -> bool:
        """
        Add a peer for bidirectional communication

        Args:
            email: Email address to add as peer

        Returns:
            True if successful
        """
        return self.sync.add_peer(email)

    def delete_peer(self, email: str) -> bool:
        """
        Delete a peer completely, removing all transport objects and local caches

        This will:
        1. Delete all Google Drive folders associated with the peer
        2. Delete all Google Sheets associated with the peer
        3. Remove Gmail labels associated with the peer
        4. Clear local peer cache files
        5. Invalidate in-memory caches

        Args:
            email: Email address of peer to delete

        Returns:
            True if peer was successfully deleted
        """
        return self.sync.delete_peer(email)

    def check_peer_requests(self) -> Dict[str, List]:
        """
        Check all transports for incoming peer requests

        Returns:
            Dictionary mapping platform.transport to list of PeerRequest objects
        """
        return self.sync.peers_manager.check_all_peer_requests(verbose=True)

    def start_watcher(self, **kwargs):
        """
        Start the file watcher for automatic synchronization

        Args:
            paths: Optional list of paths to watch
            exclude_patterns: Optional list of patterns to exclude
            bidirectional: Whether to poll for incoming messages (default: True)
            check_interval: Inbox polling interval in seconds (default: 30)
            verbose: Whether to show status messages (default: True)

        Returns:
            Status dictionary with watcher information
        """
        return self._watcher_manager.start(**kwargs)

    def start_receiver(self, **kwargs):
        """
        Start the inbox receiver for automatic message processing

        Args:
            check_interval: Seconds between inbox checks (default: 30)
            process_immediately: Process existing messages on start (default: True)
            transports: Specific transports to monitor (default: all)
            auto_accept: Auto-accept peer requests (default: True)
            verbose: Show status messages (default: True)

        Returns:
            Status dictionary with receiver information
        """
        return self._receiver_manager.start(**kwargs)

    @property
    def peers(self):
        """Access peers with list and dict-style indexing"""

        class PeersProperty:
            def __init__(self, sync_manager, client):
                self._sync = sync_manager
                self._client = client  # Store reference to the client

            def __getitem__(self, key):
                if isinstance(key, int):
                    # List-style access: peers[0]
                    peer_list = self._sync.peers
                    if 0 <= key < len(peer_list):
                        email = peer_list[key]
                        peer = self._sync.peers_manager.get_peer(email)
                        if peer:
                            # Inject client reference
                            peer._client = self._client
                        return peer
                    else:
                        raise IndexError(f"Peer index {key} out of range")
                elif isinstance(key, str):
                    # Dict-style access: peers['email@example.com']
                    peer = self._sync.peers_manager.get_peer(key)
                    if peer is None:
                        raise KeyError(f"Peer '{key}' not found")
                    # Inject client reference
                    peer._client = self._client
                    return peer
                else:
                    raise TypeError(f"Invalid key type: {type(key)}")

            def __len__(self):
                return len(self._sync.peers)

            def __iter__(self):
                # Allow iteration over peer emails
                return iter(self._sync.peers)

            def list(self):
                """Get list of peer emails"""
                return self._sync.peers

            def all(self):
                """Get all peer objects"""
                return [
                    self._sync.peers_manager.get_peer(email)
                    for email in self._sync.peers
                ]

            def clear_caches(self):
                """Clear all peer caches and force re-detection from online sources"""
                return self._sync.peers_manager.clear_all_caches()

            @property
            def requests(self):
                """Access peer requests"""

                class PeerRequestsProperty:
                    def __init__(self, sync_manager):
                        self._sync = sync_manager
                        self._requests_cache = None

                    def _get_all_requests(self):
                        """Get all peer requests organized by email"""
                        if self._requests_cache is None:
                            try:
                                requests_data = (
                                    self._sync.peers_manager.check_all_peer_requests(
                                        verbose=False
                                    )
                                )
                                # Group by email
                                by_email = {}
                                for transport_key, reqs in requests_data.items():
                                    for req in reqs:
                                        if req.email not in by_email:
                                            by_email[req.email] = {
                                                "email": req.email,
                                                "transports": [],
                                                "platforms": [],
                                            }
                                        by_email[req.email]["transports"].append(
                                            req.transport
                                        )
                                        by_email[req.email]["platforms"].append(
                                            req.platform
                                        )
                                self._requests_cache = by_email
                            except:
                                self._requests_cache = {}
                        return self._requests_cache

                    def __getitem__(self, key):
                        """Access requests by index or email"""
                        all_requests = self._get_all_requests()

                        if isinstance(key, int):
                            # Index access: requests[0]
                            emails = sorted(all_requests.keys())
                            if 0 <= key < len(emails):
                                email = emails[key]
                                return all_requests[email]
                            else:
                                raise IndexError(f"Request index {key} out of range")
                        elif isinstance(key, str):
                            # Email access: requests['email@example.com']
                            if key in all_requests:
                                return all_requests[key]
                            else:
                                raise KeyError(f"No peer request from '{key}'")
                        else:
                            raise TypeError(f"Invalid key type: {type(key)}")

                    def __repr__(self):
                        # Get peer requests
                        all_requests = self._get_all_requests()
                        total = len(all_requests)

                        if total == 0:
                            return "No pending peer requests"

                        # Build string representation
                        lines = [f"Peer Requests ({total}):"]

                        # Display each unique email
                        for email in sorted(all_requests.keys()):
                            data = all_requests[email]
                            transports_str = ", ".join(sorted(set(data["transports"])))
                            lines.append(f"  • {email} (via {transports_str})")

                        lines.append("\nAccept with: client.add_peer('email')")
                        return "\n".join(lines)

                    def __len__(self):
                        return len(self._get_all_requests())

                    def __iter__(self):
                        """Allow iteration over request emails"""
                        return iter(sorted(self._get_all_requests().keys()))

                    def list(self):
                        """Get list of unique emails with pending requests"""
                        return sorted(self._get_all_requests().keys())

                    def check(self):
                        """Manually check for new peer requests"""
                        self._requests_cache = None  # Clear cache
                        return self._sync.peers_manager.check_all_peer_requests(
                            verbose=True
                        )

                return PeerRequestsProperty(self._sync)

            def __repr__(self):
                """Display peers and peer requests in a compact format"""
                from io import StringIO

                from rich.console import Console
                from rich.panel import Panel
                from rich.text import Text

                # Create string buffer for rich output
                string_buffer = StringIO()
                console = Console(file=string_buffer, force_terminal=True, width=75)

                # Get peers and peer requests
                peers_list = self._sync.peers

                # Check for peer requests
                try:
                    peer_requests_data = (
                        self._sync.peers_manager.check_all_peer_requests(verbose=False)
                    )
                    # Flatten to unique emails
                    peer_requests = set()
                    for transport_key, requests in peer_requests_data.items():
                        for request in requests:
                            peer_requests.add(request.email)
                    peer_requests = sorted(list(peer_requests))
                except:
                    peer_requests = []

                # Build content lines
                lines = []

                # Peers section
                if peers_list:
                    lines.append(
                        Text("client.peers", style="bold green")
                        + Text(f"  [0] or ['email']", style="dim")
                    )
                    for i, email in enumerate(peers_list):
                        peer = self._sync.peers_manager.get_peer(email)
                        if peer:
                            verified_transports = peer.get_verified_transports()
                            transports_str = (
                                ", ".join(verified_transports)
                                if verified_transports
                                else "none"
                            )
                            lines.append(
                                Text(
                                    f"  [{i}] {email:<28} ✓ {transports_str}", style=""
                                )
                            )
                else:
                    lines.append(
                        Text("client.peers", style="bold green")
                        + Text("  None", style="dim")
                    )

                # Separator
                if peers_list and peer_requests:
                    lines.append(Text(""))

                # Requests section
                if peer_requests:
                    lines.append(
                        Text("client.peers.requests", style="bold yellow")
                        + Text(f"  [0] or ['email']", style="dim")
                    )
                    for i, email in enumerate(peer_requests):
                        # Find which transports the request came from
                        request_transports = []
                        for transport_key, requests in peer_requests_data.items():
                            for request in requests:
                                if request.email == email:
                                    request_transports.append(request.transport)

                        transports_str = (
                            ", ".join(set(request_transports))
                            if request_transports
                            else "?"
                        )
                        lines.append(
                            Text(
                                f"  [{i}] {email:<28} ⏳ via {transports_str}", style=""
                            )
                        )
                elif peers_list:
                    if lines:
                        lines.append(Text(""))
                    lines.append(
                        Text("client.peers.requests", style="bold yellow")
                        + Text("  None", style="dim")
                    )

                # Empty state
                if not peers_list and not peer_requests:
                    lines.append(
                        Text("No peers yet. ", style="dim")
                        + Text("Add with: client.add_peer('email')", style="dim italic")
                    )

                # Create panel with all lines
                content = Text("\n").join(lines)
                title = Text("Peers & Requests", style="bold") + Text(
                    f"  ({len(peers_list)} active, {len(peer_requests)} pending)",
                    style="dim",
                )

                panel = Panel(
                    content,
                    title=title,
                    title_align="left",
                    padding=(1, 2),
                    expand=False,
                )

                console.print(panel)
                return string_buffer.getvalue().strip()

        return PeersProperty(self.sync, self)

    def get_peer(self, email: str):
        """
        Get a specific peer object

        Args:
            email: Email address of the peer

        Returns:
            Peer object with transport information
        """
        return self.sync.peers_manager.get_peer(email)

    @property
    def platform_names(self) -> List[str]:
        """Get list of authenticated platform names"""
        return list(self._platforms.keys())

    def get_platform(self, platform_name: str) -> Optional[BasePlatformClient]:
        """Get a specific platform client by name"""
        return self._platforms.get(platform_name)

    def __getattr__(self, name: str):
        """Allow attribute-style access to platforms"""
        # First check if it's a platform
        if name in self._platforms:
            return self._platforms[name]
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def get_transports(self, platform_name: str) -> List[str]:
        """Get transport layers for a specific platform"""
        platform = self.get_platform(platform_name)
        return platform.get_transport_layers() if platform else []

    @property
    def all_transports(self) -> Dict[str, List[str]]:
        """Get all transport layers grouped by platform"""
        return {
            platform_name: platform.get_transport_layers()
            for platform_name, platform in self._platforms.items()
        }

    @property
    def one_step_transports(self) -> List[str]:
        """Get list of transport layers that are one step from being logged in (login_complexity == 1)"""
        one_step = []

        # Simply iterate through all instantiated transports
        for key, transport_instance in self.transport_instances.items():
            if (
                hasattr(transport_instance, "login_complexity")
                and transport_instance.login_complexity == 1
            ):
                one_step.append(key)

        return one_step

    def __repr__(self) -> str:
        """String representation using rich for proper formatting"""
        import sys
        from io import StringIO

        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        # Show progress while loading
        total_steps = 3
        current_step = 1
        sys.stdout.write(f"\r[{current_step}/{total_steps}] Loading client info...")
        sys.stdout.flush()

        # Create a string buffer to capture the rich output
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=100)

        # Create main table with single column for better formatting
        main_table = Table(show_header=False, show_edge=False, box=None, padding=0)
        main_table.add_column("", no_wrap=False)

        # Add folder path
        main_table.add_row(f"[dim].folder[/dim] = {self.folder}")

        # Add platforms section
        main_table.add_row("")  # Empty row for spacing
        main_table.add_row(
            "[dim].platforms[/dim] [dim](for peer-to-peer communication)[/dim]"
        )

        # Update progress
        current_step += 1
        sys.stdout.write(f"\r{' ' * 80}\r")  # Clear previous line
        sys.stdout.write(
            f"[{current_step}/{total_steps}] Checking platforms and transports..."
        )
        sys.stdout.flush()

        # Get peer counts by platform and transport
        platform_peer_counts = {}
        transport_peer_counts = {}
        try:
            if hasattr(self, "sync") and hasattr(self.sync, "peers_manager"):
                # Get all peers
                peers_dict = self.sync.peers_manager.get_peers_dict()
                for email, peer in peers_dict.items():
                    if peer.platform:
                        # Count by platform
                        if peer.platform not in platform_peer_counts:
                            platform_peer_counts[peer.platform] = 0
                        platform_peer_counts[peer.platform] += 1

                        # Count by transport
                        for transport in peer.get_verified_transports():
                            key = f"{peer.platform}.{transport}"
                            if key not in transport_peer_counts:
                                transport_peer_counts[key] = 0
                            transport_peer_counts[key] += 1
        except:
            pass

        # Add each platform with its transports
        for platform_name, platform in self._platforms.items():
            # Platform header with peer count
            platform_header = f"  [bold yellow].{platform_name}[/bold yellow]"

            # Add peer count for this platform
            if platform_name in platform_peer_counts:
                peer_count = platform_peer_counts[platform_name]
                platform_header += (
                    f" [dim]({peer_count} peer{'s' if peer_count != 1 else ''})[/dim]"
                )

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

                        if creds_path and Path(creds_path).exists():
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

                # Add peer count for this transport
                transport_peer_info = ""
                transport_key = f"{platform_name}.{transport_name}"
                if transport_key in transport_peer_counts:
                    peer_count = transport_peer_counts[transport_key]
                    transport_peer_info = f" [dim]({peer_count} peer{'s' if peer_count != 1 else ''})[/dim]"

                # Show both statuses
                main_table.add_row(
                    f"    {api_status} {auth_status} [{transport_style}].{transport_name}[/{transport_style}]{transport_peer_info}{message}"
                )

        # Update progress
        current_step += 1
        sys.stdout.write(f"\r{' ' * 80}\r")  # Clear previous line
        sys.stdout.write(f"[{current_step}/{total_steps}] Loading peer information...")
        sys.stdout.flush()

        # Add peers section if sync is available
        try:
            if hasattr(self, "sync") and hasattr(self.sync, "peers"):
                # Get peer counts
                peers_list = self.sync.peers
                peer_count = len(peers_list)

                # Check for requests
                request_count = 0
                try:
                    requests_data = self.sync.peers_manager.check_all_peer_requests(
                        verbose=False
                    )
                    # Count unique emails across all transports
                    unique_emails = set()
                    for transport_key, reqs in requests_data.items():
                        for req in reqs:
                            unique_emails.add(req.email)
                    request_count = len(unique_emails)
                except:
                    pass

                # Add separator
                main_table.add_row("")
                main_table.add_row("[dim]━" * 50 + "[/dim]")
                main_table.add_row("")

                # Add contacts section header
                if peer_count > 0 or request_count > 0:
                    main_table.add_row(
                        f"[bold cyan].peers[/bold cyan]  [dim]({peer_count} active, {request_count} pending)[/dim]"
                    )

                    # Show active contacts
                    if peer_count > 0:
                        main_table.add_row("")
                        for i, email in enumerate(peers_list[:3]):  # Show first 3
                            main_table.add_row(f"  [{i}] {email}")
                        if peer_count > 3:
                            main_table.add_row(
                                f"  [dim]... and {peer_count - 3} more[/dim]"
                            )

                    # Show pending requests
                    if request_count > 0:
                        main_table.add_row("")
                        main_table.add_row(
                            f"  [yellow]⏳ {request_count} pending request{'s' if request_count != 1 else ''}[/yellow]"
                        )
                else:
                    main_table.add_row(
                        "[bold cyan].peers[/bold cyan]  [dim](none)[/dim]"
                    )
                    main_table.add_row(
                        "  [dim]Add peers with: client.add_peer('email')[/dim]"
                    )
        except:
            # If there's any error accessing contacts, just skip this section
            pass

        # Clear the progress message before final rendering
        sys.stdout.write(f"\r{' ' * 80}\r")
        sys.stdout.flush()

        # Create the panel
        panel = Panel(
            main_table,
            title=f"SyftClient.email = '{self.email}'",
            expand=False,
            width=100,
            padding=(1, 2),
        )

        # First capture the output to string
        console.print(panel)
        output = string_buffer.getvalue()
        string_buffer.close()

        # Return the output
        return output.strip()

    def __str__(self) -> str:
        """User-friendly string representation"""
        lines = [f"SyftClient - {self.email}"]

        # Platform info
        for platform_name, platform in self._platforms.items():
            transports = platform.get_transport_layers()
            lines.append(f"  • {platform_name}: {', '.join(transports)}")

        # Peers summary
        try:
            if hasattr(self, "sync") and hasattr(self.sync, "peers"):
                peers_list = self.sync.peers
                peer_count = len(peers_list)

                # Count requests
                request_count = 0
                try:
                    requests_data = self.sync.peers_manager.check_all_peer_requests(
                        verbose=False
                    )
                    unique_emails = set()
                    for transport_key, reqs in requests_data.items():
                        for req in reqs:
                            unique_emails.add(req.email)
                    request_count = len(unique_emails)
                except:
                    pass

                # Add peers line
                if peer_count > 0 or request_count > 0:
                    lines.append(
                        f"  • peers: {peer_count} active, {request_count} pending"
                    )
                else:
                    lines.append("  • peers: none")
        except:
            pass

        return "\n".join(lines)

    def reset_wallet(self, confirm: bool = True) -> bool:
        """
        Reset the wallet by deleting all stored credentials and tokens.

        Args:
            confirm: If True, ask for confirmation before deleting (default: True)

        Returns:
            bool: True if wallet was reset, False if cancelled
        """
        import shutil
        from pathlib import Path

        # Get wallet directory path
        wallet_dir = Path.home() / ".syft"

        if not wallet_dir.exists():
            print("No wallet directory found at ~/.syft")
            return True

        if confirm:
            # Show what will be deleted
            print(f"\n⚠️  WARNING: This will delete all stored credentials!")
            print(f"\nWallet directory: {wallet_dir}")

            # Count files that will be deleted
            file_count = sum(1 for _ in wallet_dir.rglob("*") if _.is_file())
            if file_count > 0:
                print(f"Files to be deleted: {file_count}")

                # Show some example files
                example_files = list(wallet_dir.rglob("*"))[:5]
                for f in example_files:
                    if f.is_file():
                        print(f"  - {f.relative_to(wallet_dir)}")
                if file_count > 5:
                    print(f"  ... and {file_count - 5} more files")

            response = input(
                "\nAre you sure you want to delete all wallet data? (yes/no): "
            )
            if response.lower() != "yes":
                print("Wallet reset cancelled.")
                return False

        try:
            # Delete the entire wallet directory
            shutil.rmtree(wallet_dir)
            print(f"\n✓ Wallet directory deleted: {wallet_dir}")
            print("All stored credentials have been removed.")
            print("\nYou will need to authenticate again on your next login.")
            return True
        except Exception as e:
            print(f"\n✗ Error deleting wallet: {e}")
            return False

    def _login(
        self,
        provider: Optional[str] = None,
        verbose: bool = False,
        init_transport: bool = True,
        wizard: Optional[bool] = None,
        accept_requests: bool = True,
        skip_server_setup: bool = False,
        kill_servers: bool = False,
    ) -> None:
        """
        Instance method that handles the actual login process

        Args:
            provider: Optional provider override
            verbose: Whether to print progress
            init_transport: Whether to initialize transport layers
            wizard: Whether to run interactive setup wizard

        Raises:
            Exception: If authentication fails
        """
        # Progress tracking
        import sys
        import time

        total_steps = 14  # Added steps for peer requests, cache warming, and job runner
        current_step = 0

        def print_progress(step: int, message: str, is_final: bool = False):
            """Print progress with environment-aware output"""
            if verbose:
                if environment == Environment.COLAB:
                    # In Colab, use clear_output for updating progress
                    from IPython.display import clear_output

                    clear_output(wait=True)
                    if is_final:
                        print(f"✅ {message}")
                    else:
                        print(f"[{step}/{total_steps}] {message}...")
                else:
                    # In terminal/Jupyter, use carriage returns for clean progress
                    if is_final:
                        # Clear the line first, then print final message
                        sys.stdout.write(f"\r{' ' * 80}\r")
                        sys.stdout.flush()
                        print(f"✅ {message}")
                    else:
                        # Progress message with carriage return
                        sys.stdout.write(
                            f"\r[{step}/{total_steps}] {message}...{' ' * 40}\r"
                        )
                        sys.stdout.flush()
                        # Small delay to make progress visible
                        time.sleep(0.1)

        # Environment detection first (before any progress printing)
        environment = detect_environment()

        # Step 1: Starting login
        current_step += 1
        print_progress(current_step, f"Starting login for {self.email}")

        # Step 2: Platform detection
        current_step += 1
        print_progress(current_step, "Detecting email platform")
        platform = detect_primary_platform(self.email, provider)

        # Step 3: Environment detection
        current_step += 1
        print_progress(current_step, "Detecting environment")

        # Step 4: Create platform client
        from .platforms import get_platform_client

        try:
            current_step += 1
            # Create user-friendly platform description for initialization
            if platform.value == "google_personal":
                init_desc = "Google client"
            elif platform.value == "google_org":
                init_desc = "Google Workspace client"
            elif platform.value == "microsoft":
                init_desc = "Microsoft client"
            else:
                init_desc = f"{platform.value} client"

            print_progress(current_step, f"Initializing {init_desc}")
            client = get_platform_client(
                platform, self.email, init_transport=init_transport, wizard=wizard
            )

            # Step 5: Authenticate
            current_step += 1
            # Create simple, non-scary platform description
            if platform.value in ["google_personal", "google_org"]:
                platform_desc = f"Google ({self.email})"
            elif platform.value == "microsoft":
                platform_desc = f"Microsoft ({self.email})"
            else:
                platform_desc = f"{platform.value} ({self.email})"

            print_progress(current_step, f"Authenticating via {platform_desc}")
            auth_result = client.authenticate()

            # Add the authenticated platform to this client
            self.add_platform(client, auth_result)

            # Step 6: Setup local environment
            current_step += 1
            print_progress(current_step, "Setting up local SyftBox directory")

            # Temporarily suppress output from directory creation
            import contextlib
            import io

            if verbose:
                f = io.StringIO()
                with contextlib.redirect_stdout(f):
                    self._create_local_syftbox_directory()
                # Check if it was created or exists
                output = f.getvalue()
                if "Created" in output:
                    pass  # Progress already shown
                elif "Using existing" in output:
                    pass  # Progress already shown
            else:
                self._create_local_syftbox_directory()

            # Clear peer caches
            if verbose:
                f = io.StringIO()
                with contextlib.redirect_stdout(f):
                    try:
                        self.sync.peers_manager.clear_all_caches(verbose=True)
                    except:
                        pass
            else:
                try:
                    self.sync.peers_manager.clear_all_caches(verbose=False)
                except:
                    pass

            # Job runner will be setup later with progress tracking

            # Step 7: Initialize transports
            current_step += 1
            print_progress(current_step, "Activating peer-to-peer channels")
            if init_transport:
                self._initialize_all_transports()

            # Check for secondary platforms (don't count as step)
            secondary_platforms = get_secondary_platforms()

            # Step 8: Check for peer requests
            current_step += 1
            print_progress(current_step, "Checking for peer requests")
            peer_request_output = None
            accepted_peers = []
            try:
                # Check for peer requests
                if hasattr(self, "sync") and hasattr(self.sync, "peers_manager"):
                    # Get all peer requests
                    peer_requests_data = (
                        self.sync.peers_manager.check_all_peer_requests(verbose=False)
                    )

                    # Collect unique emails from all requests
                    unique_peer_emails = set()
                    for transport_key, requests in peer_requests_data.items():
                        for request in requests:
                            unique_peer_emails.add(request.email)

                    # Accept requests if flag is True
                    if accept_requests and unique_peer_emails:
                        for peer_email in unique_peer_emails:
                            try:
                                # Silently accept each peer
                                success = self.add_peer(peer_email)
                                if success:
                                    accepted_peers.append(peer_email)
                            except:
                                # Continue even if one fails
                                pass

                    # Generate output message
                    if unique_peer_emails:
                        if accept_requests and accepted_peers:
                            peer_request_output = f"📬 Automatically accepted {len(accepted_peers)} peer request{'s' if len(accepted_peers) != 1 else ''}: {', '.join(accepted_peers)}"
                        elif not accept_requests:
                            import contextlib
                            import io

                            f = io.StringIO()
                            with contextlib.redirect_stdout(f):
                                self.sync.peers_manager.check_all_peer_requests(
                                    verbose=True
                                )
                            peer_request_output = f.getvalue().strip()
            except Exception:
                # If there's any error checking peer requests, just continue
                pass
            current_step += 1

            # Kill existing servers if requested (do this even if skip_server_setup)
            verbose = True
            if kill_servers:
                print_progress(
                    current_step,
                    "Shutting down existing servers for this email if any exist...",
                )
                try:
                    import syft_serve as ss

                    # Kill only servers for this specific email
                    sanitized_email = self.email.replace("@", "_at_").replace(".", "_")

                    server_names = [
                        f"watcher_sender_{sanitized_email}",
                        f"receiver_{sanitized_email}",
                        f"job_runner_{sanitized_email}",
                    ]

                    killed_count = 0

                    for server_name in server_names:
                        try:
                            if server_name in ss.servers:
                                ss.servers[server_name].force_terminate()
                                killed_count += 1
                        except Exception as e:
                            if verbose:
                                print(
                                    f"\r⚠️  Failed to kill {server_name}: {e}",
                                    flush=True,
                                )

                    # Only show message if we actually killed servers
                    # if killed_count > 0 and verbose:
                    current_step += 1
                    print_progress(
                        current_step, f"✓ Cleaned up {killed_count} existing server(s)"
                    )
                except Exception as e:

                    if verbose:
                        print(f"⚠️  Error killing existing servers: {e}")

            if not skip_server_setup:
                # Warm up sync history before starting watcher
                if self.local_syftbox_dir:
                    from .sync.watcher.sync_history import SyncHistory

                    sync_history = SyncHistory(self.local_syftbox_dir)
                    # Warmup is internal initialization - keep quiet during login
                    sync_history.warm_up_from_directory(verbose=False)

                # Step 9: Start watcher and receiver
                current_step += 1
                print_progress(current_step, "Starting watcher")
                # Start watcher and receiver
                # If we killed servers, reset the manager state
                if kill_servers:
                    # Force managers to think servers are not running
                    if hasattr(self, "_SyftClient__watcher_manager"):
                        self._watcher_manager._server = None
                    if hasattr(self, "_SyftClient__receiver_manager"):
                        self._receiver_manager._server = None

                self.start_watcher()

                current_step += 1
                print_progress(current_step, "Starting receiver")
                self.start_receiver()

                current_step += 1
                print_progress(current_step, "Starting job runner")
                try:
                    self._setup_job_runner()
                except Exception as e:
                    if verbose:
                        print(f"\n⚠️  Failed to setup job runner: {e}")
                    # Don't fail login if job runner fails
                    pass

            # Step 9: Warm the cache
            current_step += 1
            print_progress(current_step, "Getting list of active transports")

            # Final success message with peer count
            peer_count = 0
            try:
                if hasattr(self, "sync") and hasattr(self.sync, "peers"):
                    peer_count = len(self.sync.peers)
            except:
                pass

            # Get list of active transports
            active_transports = []
            for platform_name, platform in self._platforms.items():
                for transport in platform.get_transport_layers():
                    if hasattr(platform, transport):
                        transport_obj = getattr(platform, transport)
                        if (
                            hasattr(transport_obj, "is_setup")
                            and transport_obj.is_setup()
                        ):
                            active_transports.append(transport.title())

            if peer_count > 0:
                print_progress(
                    total_steps,
                    f"Connected peer-to-peer to {peer_count} peer{'s' if peer_count != 1 else ''} via: {', '.join(active_transports)}",
                    is_final=True,
                )
            else:
                print_progress(
                    total_steps,
                    f"Peer-to-peer ready via: {', '.join(active_transports)}",
                    is_final=True,
                )

            # Print peer request output if there were any
            if verbose and peer_request_output:
                print(f"\n{peer_request_output}")

        except NotImplementedError as e:
            if verbose:
                print(f"\n❌ Login failed: {e}")
            raise e
        except Exception as e:
            if verbose:
                print(f"\n❌ Authentication failed: {e}")
            raise

    @staticmethod
    def reset_wallet_static(confirm: bool = True) -> bool:
        """
        Static method to reset the wallet without needing a client instance.

        Args:
            confirm: If True, ask for confirmation before deleting (default: True)

        Returns:
            bool: True if wallet was reset, False if cancelled
        """
        # Create a dummy client just to use the instance method
        dummy = SyftClient("dummy@example.com")
        return dummy.reset_wallet(confirm)

    @staticmethod
    def login(
        email: Optional[str] = None,
        provider: Optional[str] = None,
        quickstart: bool = True,
        verbose: bool = True,
        init_transport: bool = True,
        wizard: Optional[bool] = None,
        accept_requests: bool = True,
        skip_server_setup: bool = False,
        kill_servers: bool = False,
        **kwargs,
    ) -> "SyftClient":
        """
        Simple login function for syft_client

        Args:
            email: Email address to authenticate as
            provider: Email provider name (e.g., 'google', 'microsoft'). Required if auto-detection fails.
            quickstart: If True and in supported environment, use fastest available login
            verbose: If True (default), show login progress. Set to False for silent login
            init_transport: If True (default), initialize transport layers during login. If False, skip transport initialization.
            wizard: If True, run interactive setup wizard for credentials. If None, auto-detect based on missing credentials.
            accept_requests: If True (default), automatically accept all pending peer requests. Set to False to skip.
            skip_server_setup: If True, skip starting watcher/receiver/job runner servers.
            kill_servers: If True, kill all existing servers for this user before starting new ones.
            **kwargs: Additional arguments for authentication

        Returns:
            SyftClient: Authenticated client object with platform and transport layers
        """
        # Step 0: Validate email input
        if email is None:
            environment = detect_environment()
            if environment == Environment.COLAB:
                # In Colab, try to get email from auth
                try:
                    from google.colab import auth as colab_auth

                    # Authenticate the Colab user
                    colab_auth.authenticate_user()

                    # Use the Drive API to get the email address
                    # This is more reliable than using google.auth.default()
                    from googleapiclient.discovery import build

                    service = build("drive", "v3")
                    about = service.about().get(fields="user(emailAddress)").execute()
                    email = about["user"]["emailAddress"]

                    if email and "@" in email:
                        print(f"Auto-detected email from Colab: {email}")
                    else:
                        raise ValueError(
                            "Could not detect email from Colab auth. Please specify: login(email='your@gmail.com')"
                        )
                except Exception as e:
                    # If anything fails, show the actual error for debugging
                    import traceback

                    print(f"Debug: Colab auth error: {e}")
                    traceback.print_exc()
                    raise ValueError(
                        "Please specify an email: login(email='your@gmail.com')"
                    )
            else:
                # Look for existing emails in ~/.syft
                from pathlib import Path

                syft_dir = Path.home() / ".syft"

                if syft_dir.exists():
                    # Find email-like directory names
                    email_dirs = []
                    for item in syft_dir.iterdir():
                        if item.is_dir() and "_at_" in item.name:
                            # Convert back from safe format to email
                            # Format is: email_at_domain_com -> email@domain.com
                            parts = item.name.split("_at_")
                            if len(parts) == 2:
                                local_part = parts[0]
                                domain_parts = parts[1].split("_")
                                if len(domain_parts) >= 2:
                                    # Reconstruct domain with dots
                                    domain = ".".join(domain_parts)
                                    email_candidate = f"{local_part}@{domain}"
                                    # Basic email validation
                                    if "." in domain:
                                        email_dirs.append((item, email_candidate))

                    if len(email_dirs) == 1:
                        # Only one email found, use it
                        _, email = email_dirs[0]
                        print(f"📧 Using email from ~/.syft: {email}")
                    elif len(email_dirs) > 1:
                        # Multiple emails found, ask user to choose
                        print("\n📧 Multiple email accounts found in ~/.syft:")
                        for i, (_, email_addr) in enumerate(email_dirs):
                            print(f"  {i+1}. {email_addr}")
                        print(f"  {len(email_dirs)+1}. Enter a different email")

                        choice = input(
                            f"\nSelect an option (1-{len(email_dirs)+1}): "
                        ).strip()

                        try:
                            choice_idx = int(choice) - 1
                            if 0 <= choice_idx < len(email_dirs):
                                _, email = email_dirs[choice_idx]
                            elif choice_idx == len(email_dirs):
                                email = input("Enter your email: ").strip()
                                if not email:
                                    raise ValueError("Email cannot be empty")
                            else:
                                raise ValueError("Invalid choice")
                        except (ValueError, IndexError):
                            raise ValueError(
                                "Invalid selection. Please run login() again."
                            )
                    else:
                        raise ValueError(
                            "Please specify an email: login(email='your@email.com')"
                        )
                else:
                    raise ValueError(
                        "Please specify an email: login(email='your@email.com')"
                    )

        # Create SyftClient and login
        client = SyftClient(email)
        client._login(
            provider=provider,
            verbose=verbose,
            init_transport=init_transport,
            wizard=wizard,
            accept_requests=accept_requests,
            skip_server_setup=skip_server_setup,
            kill_servers=kill_servers,
        )
        return client
