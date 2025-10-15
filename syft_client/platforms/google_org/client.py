"""Google Organizational (Workspace) platform client implementation using OAuth2"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from ...auth.wallets import LocalFileWallet, get_wallet_class
from ...environment import Environment
from ..base import BasePlatformClient

# Try importing Colab auth
COLAB_AVAILABLE = False
try:
    from google.colab import auth as colab_auth

    COLAB_AVAILABLE = True
except ImportError:
    colab_auth = None
    COLAB_AVAILABLE = False
except AttributeError:
    colab_auth = None
    COLAB_AVAILABLE = True


class GoogleOrgClient(BasePlatformClient):
    """Client for Google Workspace (organizational) accounts using OAuth2"""

    # OAuth2 scopes for all Google services (same as personal)
    SCOPES = [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/forms.body",
    ]

    def __init__(
        self,
        email: str,
        verbose: bool = False,
        wizard: Optional[bool] = None,
        init_transport: bool = True,
    ):
        super().__init__(email, verbose=verbose)
        self.platform = "google_org"
        self.wizard = wizard
        self.init_transport = init_transport

        # OAuth2 state
        self.credentials: Optional[Credentials] = None
        self.wallet = None

        # Load project info from config
        self.project_id = None
        self.project_name = None
        self._load_project_info()

        # Initialize transport layers if requested
        if init_transport:
            self._initialize_transport_layers()
        else:
            # Create uninitialized transport stubs
            self._create_transport_stubs()

    def _initialize_transport_layers(self) -> None:
        """Initialize all transport layers for Google Workspace"""
        from .gdrive_files import GDriveFilesTransport
        from .gforms import GFormsTransport
        from .gmail import GmailTransport
        from .gsheets import GSheetsTransport

        # Create transport instances and set as attributes
        self.gmail = GmailTransport(self.email)
        self.gdrive_files = GDriveFilesTransport(self.email)
        self.gsheets = GSheetsTransport(self.email)
        self.gforms = GFormsTransport(self.email)

        # Set platform reference for better repr
        for transport in [self.gmail, self.gdrive_files, self.gsheets, self.gforms]:
            transport._platform_client = self

        # In Colab, automatically setup transports that support Colab auth
        if self.current_environment == Environment.COLAB:
            # Setup non-Gmail transports with Colab auth
            for transport_name, transport in [
                ("gdrive_files", self.gdrive_files),
                ("gsheets", self.gsheets),
                ("gforms", self.gforms),
            ]:
                try:
                    # Pass None to use Colab auth
                    transport.setup(None)
                except Exception:
                    # Ignore setup failures (e.g., API not enabled)
                    pass

        # Keep transports dict for backward compatibility
        from ..base import TransportRegistry

        self.transports = TransportRegistry(
            {
                "gmail": self.gmail,
                "gdrive_files": self.gdrive_files,
                "gsheets": self.gsheets,
                "gforms": self.gforms,
            }
        )

        # Pass references to TransportRegistry for __repr__
        self.transports._email = self.email
        self.transports._platform = self.platform
        self.transports._credentials_path = self.find_oauth_credentials()

    def _create_transport_stubs(self) -> None:
        """Create uninitialized transport stubs that require explicit setup"""
        from ..base import TransportRegistry

        # Create wrapper class for uninitialized transports
        class UninitializedTransport:
            def __init__(self, transport_name: str, platform_client):
                self._transport_name = transport_name
                self._platform_client = platform_client
                self._real_transport = None
                self._setup_called = False

                # Set default attributes based on transport type
                # These match the static attributes from the actual transport classes
                if transport_name == "gmail":
                    self.is_keystore = True
                    self.is_notification_layer = True
                    self.is_html_compatible = True
                    self.is_reply_compatible = True
                    self.guest_submit = False
                    self.guest_read_file = False
                    self.guest_read_folder = False
                elif transport_name == "gdrive_files":
                    self.is_keystore = True
                    self.is_notification_layer = False
                    self.is_html_compatible = False
                    self.is_reply_compatible = False
                    self.guest_submit = False
                    self.guest_read_file = True
                    self.guest_read_folder = True
                elif transport_name == "gsheets":
                    self.is_keystore = True
                    self.is_notification_layer = False
                    self.is_html_compatible = False
                    self.is_reply_compatible = False
                    self.guest_submit = False
                    self.guest_read_file = True
                    self.guest_read_folder = False
                elif transport_name == "gforms":
                    self.is_keystore = False
                    self.is_notification_layer = False
                    self.is_html_compatible = True
                    self.is_reply_compatible = False
                    self.guest_submit = True
                    self.guest_read_file = False
                    self.guest_read_folder = False
                else:
                    # Default values
                    self.is_keystore = False
                    self.is_notification_layer = False
                    self.is_html_compatible = False
                    self.is_reply_compatible = False
                    self.guest_submit = False
                    self.guest_read_file = False
                    self.guest_read_folder = False

            def init(self, verbose: bool = True) -> bool:
                """Initialize and set up this transport"""
                from rich.console import Console
                from rich.panel import Panel

                if verbose:
                    # Show initialization start
                    print(f"\nInitializing {self._transport_name} transport...")

                # Map transport names to their classes
                transport_classes = {
                    "gmail": lambda: __import__(
                        "syft_client.platforms.google_org.gmail",
                        fromlist=["GmailTransport"],
                    ).GmailTransport,
                    "gdrive_files": lambda: __import__(
                        "syft_client.platforms.google_org.gdrive_files",
                        fromlist=["GDriveFilesTransport"],
                    ).GDriveFilesTransport,
                    "gsheets": lambda: __import__(
                        "syft_client.platforms.google_org.gsheets",
                        fromlist=["GSheetsTransport"],
                    ).GSheetsTransport,
                    "gforms": lambda: __import__(
                        "syft_client.platforms.google_org.gforms",
                        fromlist=["GFormsTransport"],
                    ).GFormsTransport,
                }

                # Create the real transport
                if verbose:
                    print(f"  • Creating {self._transport_name} transport instance...")
                transport_class = transport_classes[self._transport_name]()
                self._real_transport = transport_class(self._platform_client.email)
                self._real_transport._platform_client = self._platform_client

                # Replace ourselves in the platform client
                setattr(
                    self._platform_client, self._transport_name, self._real_transport
                )
                self._platform_client.transports[self._transport_name] = (
                    self._real_transport
                )

                # Set up with credentials if available
                if (
                    hasattr(self._platform_client, "credentials")
                    and self._platform_client.credentials
                ):
                    if verbose:
                        print("  • Setting up with OAuth2 credentials...")
                    success = self._real_transport.setup(
                        {"credentials": self._platform_client.credentials}
                    )
                    if success and verbose:
                        print("  ✓ OAuth2 credentials configured")
                    elif not success and verbose:
                        print("  ✗ Failed to configure credentials")
                else:
                    # Check if we're in Colab - transports can use Colab auth
                    from ...environment import Environment

                    if self._real_transport.environment == Environment.COLAB:
                        if verbose:
                            print("  • Setting up with Colab authentication...")
                        # Call setup without credentials - transport will use Colab auth
                        success = self._real_transport.setup(None)
                        if success and verbose:
                            print("  ✓ Colab authentication configured")
                        elif not success and verbose:
                            print("  ✗ Failed to configure with Colab auth")
                    else:
                        if verbose:
                            print(
                                "  • No credentials available (transport created but not authenticated)"
                            )
                        success = False

                self._setup_called = True

                if success and verbose:
                    # Create info panel with next steps
                    info_lines = [
                        f"[bold green]✓ {self._transport_name} transport initialized successfully![/bold green]",
                        "",
                        "[bold]What you can do now:[/bold]",
                    ]

                    # Add transport-specific suggestions
                    if self._transport_name == "gmail":
                        info_lines.extend(
                            [
                                "  • Send emails: [cyan].send(recipient, data, subject)[/cyan]",
                                "  • Read emails: [cyan].receive(limit=10)[/cyan]",
                                "  • Test setup: [cyan].test()[/cyan]",
                            ]
                        )
                    elif self._transport_name == "gdrive_files":
                        info_lines.extend(
                            [
                                "  • List files: [cyan].list_files()[/cyan]",
                                "  • Upload file: [cyan].upload_file(filepath)[/cyan]",
                                "  • Download file: [cyan].download_file(file_id, save_path)[/cyan]",
                            ]
                        )
                    elif self._transport_name == "gsheets":
                        info_lines.extend(
                            [
                                "  • Read sheet: [cyan].read_sheet(spreadsheet_id, range)[/cyan]",
                                "  • Write data: [cyan].write_sheet(spreadsheet_id, range, values)[/cyan]",
                                "  • Create sheet: [cyan].create_sheet(title)[/cyan]",
                            ]
                        )
                    elif self._transport_name == "gforms":
                        info_lines.extend(
                            [
                                "  • List forms: [cyan].list_forms()[/cyan]",
                                "  • Get responses: [cyan].get_responses(form_id)[/cyan]",
                                "  • Create form: [cyan].create_form(title)[/cyan]",
                            ]
                        )

                    info_lines.extend(
                        [
                            "",
                            f"[dim]Access via: client.platforms.google_org.{self._transport_name}[/dim]",
                        ]
                    )

                    # Use console only for the panel
                    console = Console()
                    panel = Panel(
                        "\n".join(info_lines), expand=False, border_style="green"
                    )
                    print()  # Add spacing before panel
                    console.print(panel)

                return success

            def is_setup(self) -> bool:
                """Check if transport is set up"""
                return self._setup_called and self._real_transport is not None

            @property
            def login_complexity(self) -> int:
                """Return the login complexity for this transport type"""
                # All Google Org transports have 0 additional complexity after OAuth2
                return 0

            def __repr__(self):
                """String representation for uninitialized transport"""
                from io import StringIO

                from rich.console import Console
                from rich.panel import Panel

                # Create a string buffer to capture the rich output
                string_buffer = StringIO()
                console = Console(file=string_buffer, force_terminal=True, width=70)

                # Get platform name
                platform_name = getattr(self._platform_client, "platform", "unknown")

                info_lines = [
                    f"[bold red]✗ {self._transport_name} transport is not initialized[/bold red]",
                    "",
                    f"[yellow]Please call .init() to initialize this transport.[/yellow]",
                    "",
                    f"[dim]Access path: client.platforms.{platform_name}.{self._transport_name}[/dim]",
                ]

                panel = Panel(
                    "\n".join(info_lines),
                    title=f"{self._transport_name.title()} Transport",
                    expand=False,
                    border_style="red",
                )

                console.print(panel)
                output = string_buffer.getvalue()
                string_buffer.close()

                return output.strip()

            def enable_api(self) -> None:
                """Show instructions for enabling the API even when transport is not initialized"""
                # Map transport names to their classes
                transport_classes = {
                    "gmail": "syft_client.platforms.google_org.gmail.GmailTransport",
                    "gdrive_files": "syft_client.platforms.google_org.gdrive_files.GDriveFilesTransport",
                    "gsheets": "syft_client.platforms.google_org.gsheets.GSheetsTransport",
                    "gforms": "syft_client.platforms.google_org.gforms.GFormsTransport",
                }

                if self._transport_name in transport_classes:
                    # Import and call the static method
                    module_path, class_name = transport_classes[
                        self._transport_name
                    ].rsplit(".", 1)
                    module = __import__(module_path, fromlist=[class_name])
                    transport_class = getattr(module, class_name)

                    # Get project_id from platform client if available
                    project_id = getattr(self._platform_client, "project_id", None)
                    transport_class.enable_api_static(
                        self._transport_name, self._platform_client.email, project_id
                    )

            def disable_api(self) -> None:
                """Show instructions for disabling the API even when transport is not initialized"""
                # Map transport names to their classes
                transport_classes = {
                    "gmail": "syft_client.platforms.google_org.gmail.GmailTransport",
                    "gdrive_files": "syft_client.platforms.google_org.gdrive_files.GDriveFilesTransport",
                    "gsheets": "syft_client.platforms.google_org.gsheets.GSheetsTransport",
                    "gforms": "syft_client.platforms.google_org.gforms.GFormsTransport",
                }

                if self._transport_name in transport_classes:
                    # Import and call the static method
                    module_path, class_name = transport_classes[
                        self._transport_name
                    ].rsplit(".", 1)
                    module = __import__(module_path, fromlist=[class_name])
                    transport_class = getattr(module, class_name)

                    # Get project_id from platform client if available
                    project_id = getattr(self._platform_client, "project_id", None)
                    transport_class.disable_api_static(
                        self._transport_name, self._platform_client.email, project_id
                    )

            def test(self, test_data: str = "test123", cleanup: bool = True):
                """Test transport - requires initialization first"""
                if not self._setup_called or not self._real_transport:
                    print(f"❌ Transport '{self._transport_name}' is not initialized")
                    print(f"   Please call .init() first to initialize the transport")
                    return {"success": False, "error": "Transport not initialized"}

                # Delegate to real transport
                if hasattr(self._real_transport, "test"):
                    return self._real_transport.test(
                        test_data=test_data, cleanup=cleanup
                    )
                else:
                    return {
                        "success": False,
                        "error": f"Transport '{self._transport_name}' does not support test()",
                    }

            def __getattr__(self, name):
                # List of attributes that should be accessible without initialization
                allowed_attrs = [
                    "init",
                    "setup",
                    "is_setup",
                    "_transport_name",
                    "_platform_client",
                    "_real_transport",
                    "_setup_called",
                    "login_complexity",
                    "is_keystore",
                    "is_notification_layer",
                    "is_html_compatible",
                    "is_reply_compatible",
                    "guest_submit",
                    "guest_read_file",
                    "guest_read_folder",
                    "enable_api",
                    "disable_api",
                    "test",
                ]

                # Service attributes that should return None when not initialized
                service_attrs = [
                    "gmail_service",
                    "drive_service",
                    "sheets_service",
                    "forms_service",
                ]

                if name in allowed_attrs:
                    return object.__getattribute__(self, name)

                # For service attributes, return None if not initialized
                if name in service_attrs:
                    if not self._setup_called:
                        return None
                    elif self._real_transport:
                        return getattr(self._real_transport, name, None)
                    else:
                        return None

                if not self._setup_called:
                    raise RuntimeError(
                        f"Transport '{self._transport_name}' is not initialized. Please call .init() first."
                    )
                if self._real_transport:
                    return getattr(self._real_transport, name)
                raise AttributeError(
                    f"'{self.__class__.__name__}' object has no attribute '{name}'"
                )

        # Create stub instances
        self.gmail = UninitializedTransport("gmail", self)
        self.gdrive_files = UninitializedTransport("gdrive_files", self)
        self.gsheets = UninitializedTransport("gsheets", self)
        self.gforms = UninitializedTransport("gforms", self)

        # Create transports registry
        self.transports = TransportRegistry(
            {
                "gmail": self.gmail,
                "gdrive_files": self.gdrive_files,
                "gsheets": self.gsheets,
                "gforms": self.gforms,
            }
        )

        # Pass references to TransportRegistry for __repr__
        self.transports._email = self.email
        self.transports._platform = self.platform
        self.transports._credentials_path = self.find_oauth_credentials()

    def _load_project_info(self) -> None:
        """Load project info from config.json if it exists"""
        try:
            config_path = Path.home() / ".syft" / self._sanitize_email() / "config.json"
            if config_path.exists():
                with open(config_path, "r") as f:
                    config_data = json.load(f)
                    self.project_id = config_data.get("google_org_project_id")
                    self.project_name = config_data.get("google_org_project_name")
        except:
            pass  # Ignore errors, project info is optional

    def initialize_transport(self, transport_name: str) -> bool:
        """Initialize a single transport layer"""
        if not hasattr(self, "transports"):
            from ..base import TransportRegistry

            self.transports = TransportRegistry({})

        # Map transport names to their classes
        transport_map = {
            "gmail": lambda: __import__(
                "syft_client.platforms.google_org.gmail", fromlist=["GmailTransport"]
            ).GmailTransport,
            "gdrive_files": lambda: __import__(
                "syft_client.platforms.google_org.gdrive_files",
                fromlist=["GDriveFilesTransport"],
            ).GDriveFilesTransport,
            "gsheets": lambda: __import__(
                "syft_client.platforms.google_org.gsheets",
                fromlist=["GSheetsTransport"],
            ).GSheetsTransport,
            "gforms": lambda: __import__(
                "syft_client.platforms.google_org.gforms", fromlist=["GFormsTransport"]
            ).GFormsTransport,
        }

        if transport_name not in transport_map:
            raise ValueError(f"Unknown transport: {transport_name}")

        # Create the transport instance
        transport_class = transport_map[transport_name]()
        transport = transport_class(self.email)
        transport._platform_client = self

        # Add to transports registry and as attribute
        self.transports[transport_name] = transport
        setattr(self, transport_name, transport)

        # Update registry references
        self.transports._email = self.email
        self.transports._platform = self.platform
        self.transports._credentials_path = self.find_oauth_credentials()

        # Set up the transport with credentials if available
        if hasattr(self, "credentials") and self.credentials:
            return transport.setup({"credentials": self.credentials})

        return True

    # ===== Core Authentication Methods (Main Flow) =====

    def authenticate(self) -> Dict[str, Any]:
        """
        Main authentication entry point - orchestrates entire flow.

        Flow:
        1. Load wallet configuration
        2. Get or create wallet
        3. Check for cached token
        4. If no token, run OAuth2 flow
        5. If first time, configure wallet
        6. Store token in wallet
        7. If first time, setup transports
        """
        try:
            # Check if we're in Colab and can use automatic auth
            if self.current_environment == Environment.COLAB and COLAB_AVAILABLE:
                # Try Colab authentication first
                if self.authenticate_colab():
                    # For Colab, we still need to setup transports but skip wallet/OAuth2
                    config = self.load_platform_config()
                    is_first_time = not config.get("setup_completed", False)

                    if is_first_time:
                        if self.init_transport:
                            # Setup transport layers (but only non-Gmail ones will work)
                            if self.verbose:
                                print(
                                    "\n⚠️  Note: Gmail requires OAuth2 setup and won't work with Colab auth"
                                )
                                print(
                                    "   Other services (Drive, Sheets, Forms) will work automatically"
                                )

                            # In Colab, skip wizard unless explicitly requested
                            show_wizard = (
                                self.wizard if self.wizard is not None else False
                            )
                            transport_result = self.setup_transport_layers(
                                show_wizard=show_wizard
                            )

                            successful_transports = transport_result.get(
                                "configured", []
                            )
                            failed_transports = transport_result.get("failed", [])
                        else:
                            # Skip transport setup when init_transport=False
                            successful_transports = []
                            failed_transports = []

                        # Mark setup as completed
                        config["setup_completed"] = datetime.now().isoformat()
                        config["colab_auth"] = True
                        self.save_platform_config(config)
                    else:
                        successful_transports = []
                        failed_transports = []

                    return {
                        "email": self.email,
                        "auth_method": "colab",
                        "platform": self.platform,
                        "wallet": "colab_builtin",
                        "active_transports": successful_transports,
                        "failed_transports": failed_transports,
                    }

            # Regular OAuth2 flow
            # Step 1 & 2: Initialize wallet
            self.wallet = self.get_or_create_wallet()

            # Step 3: Check for cached token
            cached_credentials = self.check_cached_token()

            if not cached_credentials:
                # Step 4: Run OAuth2 flow
                self.credentials = self.authenticate_oauth2()
                if not self.credentials:
                    raise RuntimeError("OAuth2 authentication failed")

                # Note: Token is already stored in wallet by authenticate_oauth2

            # Check if this is first time setup
            config = self.load_platform_config()
            is_first_time = not config.get("setup_completed", False)

            if is_first_time:
                # Step 5: Configure wallet preference for first-time users
                if not config.get("wallet_config"):
                    self.configure_wallet_preference()

                if self.init_transport:
                    # Step 7: Setup transport layers for first-time users
                    # For non-Colab, default to showing wizard unless wizard=False
                    show_wizard = self.wizard if self.wizard is not None else True
                    transport_result = self.setup_transport_layers(
                        show_wizard=show_wizard
                    )

                    successful_transports = transport_result.get("configured", [])
                    failed_transports = transport_result.get("failed", [])
                else:
                    # Skip transport setup when init_transport=False
                    successful_transports = []
                    failed_transports = []

                # Mark setup as completed
                config["setup_completed"] = datetime.now().isoformat()
                self.save_platform_config(config)
            else:
                # For returning users
                if self.init_transport:
                    # Check and setup transports
                    successful_transports = []
                    failed_transports = []

                    for transport_name, transport in self.transports.items():
                        if hasattr(transport, "is_setup") and transport.is_setup():
                            # Transport reports it's already setup
                            successful_transports.append(transport_name)
                        else:
                            # Skip Gmail in Colab mode since it requires OAuth2
                            if (
                                self.current_environment == Environment.COLAB
                                and transport_name == "gmail"
                                and not self.credentials
                            ):
                                continue

                            # Try to set it up
                            try:
                                # In Colab mode, we may not have explicit credentials
                                if (
                                    self.current_environment == Environment.COLAB
                                    and not self.credentials
                                ):
                                    setup_data = None  # Transports will handle Colab auth internally
                                else:
                                    setup_data = {"credentials": self.credentials}
                                if transport.setup(setup_data):
                                    successful_transports.append(transport_name)
                                else:
                                    failed_transports.append(transport_name)
                            except Exception:
                                failed_transports.append(transport_name)
                else:
                    # Skip transport setup when init_transport=False
                    successful_transports = []
                    failed_transports = []

            if self.init_transport and not successful_transports:
                raise ValueError("Failed to setup any transport layers")

            if self.verbose:
                print(f"\n✅ Authentication complete!")
                print(f"Active transports: {', '.join(successful_transports)}")

            return {
                "email": self.email,
                "auth_method": "oauth2",
                "wallet": self.wallet.name,
                "active_transports": successful_transports,
                "failed_transports": failed_transports,
            }

        except Exception as e:
            raise RuntimeError(f"Authentication failed: {e}")

    def authenticate_oauth2(self) -> Optional[Credentials]:
        """
        Run OAuth2-specific authentication flow.

        Returns raw Google credentials object.
        """
        # Step 1: Look for credentials.json
        credentials_file = self.find_oauth_credentials()

        # Step 2: Run wizard if needed
        if not credentials_file:
            credentials_file = self.run_oauth_wizard()
            if not credentials_file:
                return None

        # Step 3: Execute OAuth2 flow
        try:
            self.credentials = self.execute_oauth_flow(credentials_file)

            # Step 4: Convert to token data for storage
            token_data = {
                "token": self.credentials.token,
                "refresh_token": self.credentials.refresh_token,
                "token_uri": self.credentials.token_uri,
                "client_id": self.credentials.client_id,
                "client_secret": self.credentials.client_secret,
                "scopes": self.credentials.scopes,
                "expiry": (
                    self.credentials.expiry.isoformat()
                    if self.credentials.expiry
                    else None
                ),
            }

            # Step 5: Store in wallet
            self.store_token_in_wallet(token_data)

            return self.credentials

        except Exception as e:
            if self.verbose:
                print(f"✗ OAuth2 flow failed: {e}")
            raise

    def authenticate_colab(self) -> bool:
        """
        Authenticate using Google Colab's built-in authentication.

        This only works for Google Drive, Sheets, and Forms - NOT Gmail.

        Returns:
            bool: True if successful, False otherwise
        """

        # Try importing Colab auth
        COLAB_AVAILABLE = False
        try:
            from google.colab import auth as colab_auth

            COLAB_AVAILABLE = True
        except ImportError:
            colab_auth = None
            COLAB_AVAILABLE = False
        except AttributeError:
            colab_auth = None
            COLAB_AVAILABLE = True

        if not COLAB_AVAILABLE or self.current_environment != Environment.COLAB:
            return False

        try:
            if self.verbose:
                print("🔐 Authenticating with Google Colab...")

            # Authenticate the Colab user
            colab_auth.authenticate_user()

            # Get the email address from Drive API
            from googleapiclient.discovery import build

            service = build("drive", "v3")
            about = service.about().get(fields="user(emailAddress)").execute()
            authenticated_email = about["user"]["emailAddress"]

            # Verify it matches our expected email
            if authenticated_email != self.email:
                if self.verbose:
                    print(
                        f"⚠️  Colab authenticated as {authenticated_email}, but expected {self.email}"
                    )
                return False

            if self.verbose:
                print(f"✅ Authenticated via Google Colab as {self.email}")

            # Mark as authenticated for non-Gmail transports
            return True

        except Exception as e:
            if self.verbose:
                print(f"❌ Colab authentication failed: {e}")
            return False

    # ===== Wallet Integration Methods =====

    def load_wallet_config(self) -> Optional[Dict[str, Any]]:
        """Load wallet configuration from ~/.syft/[email]/config.json"""
        try:
            if self.config_path.exists():
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                    return config.get("wallet_config", None)
            return None
        except Exception as e:
            if self.verbose:
                print(f"Failed to load wallet config: {e}")
            return None

    def get_or_create_wallet(self) -> Any:  # Returns wallet instance
        """Get configured wallet or create default LocalFileWallet"""
        # Load saved configuration
        config = self.load_wallet_config()

        if config:
            # Try to use configured wallet
            try:
                wallet_type = config.get("preferred_wallet", "local_file")
                wallet_config = config.get("wallet_config", {})

                wallet_class = get_wallet_class(wallet_type)
                wallet = wallet_class(wallet_config)

                # Test if wallet is accessible
                if wallet.test_connection():
                    if self.verbose:
                        print(f"✓ Using {wallet.name} wallet")
                    return wallet
                else:
                    if self.verbose:
                        print(
                            f"⚠️  {wallet.name} wallet not accessible, falling back to local storage"
                        )
            except Exception as e:
                if self.verbose:
                    print(f"⚠️  Failed to initialize configured wallet: {e}")

        # Fall back to default LocalFileWallet
        if self.verbose:
            print("Using default local file wallet")

        return LocalFileWallet({})

    def configure_wallet_preference(self) -> Dict[str, Any]:
        """Interactive wallet selection for first-time users"""
        from ...auth.wallets import AVAILABLE_WALLETS

        print("\n🔐 Choose your token storage preference")
        print("=" * 50)
        print("\nTokens allow Syft to access Google services on your behalf.")
        print("Where would you like to store them?\n")

        # For now, we only have LocalFileWallet, but show the structure for future wallets
        options = [
            ("1", "local_file", "Local File Storage", "Simple, works everywhere"),
            # Future options:
            # ("2", "1password", "1Password", "Secure, syncs across devices"),
            # ("3", "keychain", "macOS Keychain", "Native Mac integration"),
        ]

        for num, key, name, desc in options:
            if key in AVAILABLE_WALLETS:
                print(f"{num}. {name} - {desc}")

        # Get user choice
        while True:
            try:
                choice = input("\nYour choice [1]: ").strip() or "1"

                # Find the selected wallet
                for num, key, name, desc in options:
                    if choice == num and key in AVAILABLE_WALLETS:
                        wallet_type = key
                        wallet_name = name
                        break
                else:
                    print("Invalid choice. Please try again.")
                    continue

                # For now, we only have local_file, so no additional config needed
                wallet_config = {
                    "preferred_wallet": wallet_type,
                    "wallet_config": {},
                    "fallback_wallet": "local_file",
                }

                # Save the preference
                self.save_platform_config({"wallet_config": wallet_config})

                print(f"\n✓ {wallet_name} configured successfully!")
                print("Future logins will use this storage method.")

                return wallet_config

            except KeyboardInterrupt:
                print("\n\nWallet configuration cancelled.")
                # Default to local file
                return {
                    "preferred_wallet": "local_file",
                    "wallet_config": {},
                    "fallback_wallet": "local_file",
                }

    def store_token_in_wallet(self, token_data: Dict[str, Any]) -> bool:
        """Store OAuth2 token using configured wallet"""
        if not self.wallet:
            self.wallet = self.get_or_create_wallet()

        try:
            success = self.wallet.store_token(
                service=self.platform, account=self.email, token_data=token_data
            )

            if success and self.verbose:
                print(f"✓ Token stored in {self.wallet.name}")

            return success
        except Exception as e:
            if self.verbose:
                print(f"✗ Failed to store token: {e}")
            return False

    def load_token_from_wallet(self) -> Optional[Dict[str, Any]]:
        """Retrieve OAuth2 token from configured wallet"""
        if not self.wallet:
            self.wallet = self.get_or_create_wallet()

        try:
            token_data = self.wallet.retrieve_token(
                service=self.platform, account=self.email
            )

            if token_data and self.verbose:
                print(f"✓ Token loaded from {self.wallet.name}")

            return token_data
        except Exception as e:
            if self.verbose:
                print(f"✗ Failed to load token: {e}")
            return None

    # ===== Token Management Methods =====

    def check_cached_token(self) -> Optional[Credentials]:
        """Check for existing valid token in wallet"""
        # Try to load token from wallet
        token_data = self.load_token_from_wallet()

        if not token_data:
            return None

        try:
            # Convert to Google Credentials object
            self.credentials = Credentials.from_authorized_user_info(
                token_data, self.SCOPES
            )

            # Check if token is valid
            if self.validate_token():
                return self.credentials

            # Try to refresh if expired
            if self.refresh_token_if_needed():
                return self.credentials

            return None
        except Exception as e:
            if self.verbose:
                print(f"Failed to load cached token: {e}")
            return None

    def refresh_token_if_needed(self) -> bool:
        """Refresh token if expired, update in wallet"""
        if not self.credentials:
            return False

        try:
            # Check if token needs refresh
            if self.credentials.expired:
                if self.verbose:
                    print("Token expired, refreshing...")

                # Refresh the token
                self.credentials.refresh(Request())

                # Save refreshed token back to wallet
                token_data = {
                    "token": self.credentials.token,
                    "refresh_token": self.credentials.refresh_token,
                    "token_uri": self.credentials.token_uri,
                    "client_id": self.credentials.client_id,
                    "client_secret": self.credentials.client_secret,
                    "scopes": self.credentials.scopes,
                    "expiry": (
                        self.credentials.expiry.isoformat()
                        if self.credentials.expiry
                        else None
                    ),
                }

                if self.store_token_in_wallet(token_data):
                    if self.verbose:
                        print("✓ Token refreshed and saved")
                    return True
                else:
                    if self.verbose:
                        print("✗ Failed to save refreshed token")
                    return False

            return True  # Token is still valid

        except Exception as e:
            if self.verbose:
                print(f"Failed to refresh token: {e}")
            return False

    def validate_token(self) -> bool:
        """Test if current token works with simple API call"""
        if not self.credentials:
            return False

        # Check if we have a recent validation cached
        if self.wallet:
            # Try getting metadata from wallet
            metadata = None
            if hasattr(self.wallet, "get_token_metadata"):
                metadata = self.wallet.get_token_metadata(self.platform, self.email)

            # If no metadata or no last_validated, check if it's in the token data itself
            if not metadata or "last_validated" not in metadata:
                token_data = self.wallet.retrieve_token(self.platform, self.email)
                if (
                    token_data
                    and isinstance(token_data, dict)
                    and "metadata" in token_data
                ):
                    metadata = token_data["metadata"]

            if metadata and "last_validated" in metadata:
                last_validated = datetime.fromisoformat(metadata["last_validated"])
                time_since_validation = datetime.now() - last_validated

                # If validated within last 24 hours, skip API call
                if time_since_validation.total_seconds() < 24 * 60 * 60:
                    if self.verbose:
                        print(
                            f"✓ Token validated (cached from {last_validated.strftime('%Y-%m-%d %H:%M')})"
                        )
                    return True

        try:
            # Try a simple API call to validate the token
            # We'll use the Gmail API to get user profile
            from googleapiclient.discovery import build

            service = build("gmail", "v1", credentials=self.credentials)
            result = service.users().getProfile(userId="me").execute()

            if self.verbose:
                print(
                    f"✓ Token validated for: {result.get('emailAddress', self.email)}"
                )

            # Update validation timestamp in wallet metadata
            if self.wallet and hasattr(self.wallet, "update_token_metadata"):
                self.wallet.update_token_metadata(
                    self.platform,
                    self.email,
                    {"last_validated": datetime.now().isoformat()},
                )

            return True
        except Exception as e:
            if self.verbose:
                print(f"✗ Token validation failed: {e}")
            return False

    # ===== Credentials & Wizard Methods =====

    def find_oauth_credentials(self) -> Optional[Path]:
        """Locate OAuth2 app credentials (credentials.json)"""
        # Check email-specific directory first
        email_dir = Path.home() / ".syft" / self._sanitize_email()

        possible_paths = [
            email_dir / "credentials.json",  # Email-specific location (preferred)
            Path.home() / ".syft" / "credentials.json",  # Legacy location
            Path.home() / ".syft" / "google_oauth" / "credentials.json",  # Old location
            Path("credentials.json"),  # Current directory fallback
        ]

        for path in possible_paths:
            if path.exists():
                if self.verbose:
                    print(f"✓ Found credentials at: {path}")
                return path

        if self.verbose:
            print("✗ No credentials.json found")
            print(f"   Expected location: {email_dir / 'credentials.json'}")
        return None

    def run_oauth_wizard(self) -> Optional[Path]:
        """Run interactive wizard to create OAuth2 app credentials"""
        from .wizard import check_or_create_credentials

        if self.verbose:
            print("\n🔧 OAuth2 credentials not found. Starting setup wizard...")

        # Run the wizard
        creds_file = check_or_create_credentials(email=self.email, verbose=self.verbose)

        if not creds_file:
            if self.verbose:
                print("✗ OAuth2 setup cancelled or failed")
            return None

        return creds_file

    def wizard(self) -> None:
        """Public entry point for manual wizard launch"""
        from .wizard import create_oauth2_wizard

        create_oauth2_wizard(self.email, verbose=True, is_workspace=True)

    # ===== OAuth2 Flow Methods =====

    def execute_oauth_flow(self, credentials_file: Path) -> Credentials:
        """Execute OAuth2 browser flow and return credentials"""
        if self.verbose:
            print(f"\n🔐 Starting OAuth2 authentication for {self.email}")
            print("A browser window will open for Google sign-in...")
            print("\n⚠️  Google Workspace accounts may require admin consent")

        # Create the flow
        flow = self.create_oauth_client(credentials_file)

        # Run the local server to handle the OAuth2 callback
        self.credentials = flow.run_local_server(port=0)

        if self.verbose:
            print("✓ OAuth2 authentication successful")

        return self.credentials

    def create_oauth_client(self, credentials_file: Path) -> InstalledAppFlow:
        """Create OAuth2 flow object for testing/mocking"""
        return InstalledAppFlow.from_client_secrets_file(
            str(credentials_file), self.SCOPES
        )

    # ===== Transport Setup Methods =====

    def setup_transport_layers(self, show_wizard: bool = True) -> Dict[str, Any]:
        """Interactive transport setup for first-time users"""
        # For Colab without wizard, auto-configure available services
        if self.current_environment == Environment.COLAB and not show_wizard:
            # Auto-configure all non-Gmail services
            transports_to_setup = ["gdrive_files", "gsheets", "gforms"]
            configured = []
            failed = []

            for transport_id in transports_to_setup:
                if self.setup_transport(transport_id):
                    configured.append(transport_id)
                else:
                    failed.append(transport_id)

            if self.verbose and configured:
                print(f"\n✅ Auto-configured Colab services: {', '.join(configured)}")
            if self.verbose and failed:
                print(f"\n⚠️  Failed to configure: {', '.join(failed)}")

            return {
                "configured": configured,
                "failed": failed,
                "skipped": ["gmail"],  # Gmail requires OAuth2
            }

        # Show interactive wizard
        print("\n🚀 Let's set up your Google Workspace services!")
        print("=" * 50)

        # Get available transports
        available = self.show_available_transports()

        # Show what's available
        print("\nAvailable services:")
        for i, transport in enumerate(available, 1):
            status = "✓ Configured" if transport["configured"] else "○ Not configured"
            required = " (Required)" if transport["required"] else ""
            print(f"\n{i}. {transport['name']}{required} - {status}")
            print(f"   {transport['description']}")
            print(f"   Features: {', '.join(transport['features'])}")

        # Quick setup options
        print("\n\nQuick setup options:")
        print("1. Basic - Gmail only (recommended for testing)")
        print("2. Standard - Gmail + Google Drive")
        print("3. Full - All services")
        print("4. Custom - Choose individually")
        print("5. Skip for now")

        choice = input("\nYour choice [3]: ").strip() or "3"

        transports_to_setup = []
        if choice == "1":
            transports_to_setup = ["gmail"]
        elif choice == "2":
            transports_to_setup = ["gmail", "gdrive_files"]
        elif choice == "3":
            transports_to_setup = ["gmail", "gdrive_files", "gsheets", "gforms"]
        elif choice == "4":
            # Custom selection
            print("\nSelect services to set up (comma-separated numbers):")
            for i, transport in enumerate(available, 1):
                print(f"{i}. {transport['name']}")

            selections = input("\nYour selections: ").strip()
            if selections:
                try:
                    indices = [int(x.strip()) - 1 for x in selections.split(",")]
                    transports_to_setup = [
                        available[i]["id"] for i in indices if 0 <= i < len(available)
                    ]
                except:
                    print("Invalid selection, using default (Gmail only)")
                    transports_to_setup = ["gmail"]
        else:
            print("\nSkipping transport setup. You can configure them later.")
            return {"configured": [], "skipped": [t["id"] for t in available]}

        # Set up selected transports
        configured = []
        failed = []

        for transport_id in transports_to_setup:
            if self.setup_transport(transport_id):
                configured.append(transport_id)
            else:
                failed.append(transport_id)

        # Summary
        print(f"\n✅ Setup complete!")
        if configured:
            print(f"Configured: {', '.join(configured)}")
        if failed:
            print(f"Failed: {', '.join(failed)}")

        return {
            "configured": configured,
            "failed": failed,
            "skipped": [
                t["id"] for t in available if t["id"] not in configured + failed
            ],
        }

    def check_transport_status(self) -> Dict[str, Dict[str, Any]]:
        """Check configuration status of all transports"""
        status = {}

        # Load saved config
        config = self.load_platform_config()
        transport_config = config.get("transports", {})

        for transport_name, transport in self.transports.items():
            status[transport_name] = {
                "name": transport.__class__.__name__,
                "configured": False,
                "active": False,
                "features": [],
            }

            # Check if transport has been set up
            if hasattr(transport, "_setup_verified"):
                status[transport_name]["configured"] = transport._setup_verified
                status[transport_name]["active"] = transport._setup_verified

            # Add saved config info
            if transport_name in transport_config:
                status[transport_name].update(transport_config[transport_name])

            # Get transport features
            if hasattr(transport, "is_notification_layer"):
                if transport.is_notification_layer:
                    status[transport_name]["features"].append("notifications")
            if hasattr(transport, "is_keystore"):
                if transport.is_keystore:
                    status[transport_name]["features"].append("keystore")
            if hasattr(transport, "is_html_compatible"):
                if transport.is_html_compatible:
                    status[transport_name]["features"].append("html")

        return status

    def show_available_transports(self) -> List[Dict[str, Any]]:
        """List available transports with descriptions and status"""
        transport_info = {
            "gmail": {
                "name": "Gmail",
                "description": "Send and receive emails with attachments",
                "features": [
                    "Email notifications",
                    "Backend data transfer",
                    "HTML support",
                ],
                "setup_complexity": 1,  # Needs label/filter creation
                "required": True,
            },
            "gdrive_files": {
                "name": "Google Drive",
                "description": "Store and share files in the cloud",
                "features": ["File upload/download", "Folder organization", "Sharing"],
                "setup_complexity": 0,  # Just folder creation
                "required": False,
            },
            "gsheets": {
                "name": "Google Sheets",
                "description": "Create and manage spreadsheets",
                "features": ["Data tables", "CSV export", "Public sharing"],
                "setup_complexity": 0,  # No setup needed
                "required": False,
            },
            "gforms": {
                "name": "Google Forms",
                "description": "Create forms for data collection",
                "features": ["Dynamic forms", "Response collection"],
                "setup_complexity": 0,  # No setup needed
                "required": False,
            },
        }

        # Get current status
        status = self.check_transport_status()

        # Build transport list
        transports = []
        for transport_id, info in transport_info.items():
            transport_data = {
                "id": transport_id,
                "name": info["name"],
                "description": info["description"],
                "features": info["features"],
                "setup_complexity": info["setup_complexity"],
                "required": info.get("required", False),
                "configured": status.get(transport_id, {}).get("configured", False),
                "active": status.get(transport_id, {}).get("active", False),
            }
            transports.append(transport_data)

        return transports

    def setup_transport(self, name: str) -> bool:
        """Configure a specific transport"""
        if name not in self.transports:
            if self.verbose:
                print(f"✗ Unknown transport: {name}")
            return False

        transport = self.transports[name]

        # Check if already configured
        if hasattr(transport, "is_setup") and transport.is_setup():
            if self.verbose:
                print(f"✓ {name} is already configured!")
            return True

        if self.verbose:
            print(f"\nSetting up {name}...")

        # Ensure we have credentials (unless in Colab with built-in auth)
        if not self.credentials and self.current_environment != Environment.COLAB:
            if self.verbose:
                print("✗ No credentials available. Please authenticate first.")
            return False

        # Call the transport's setup method
        try:
            # In Colab mode, we may not have explicit credentials
            if self.current_environment == Environment.COLAB and not self.credentials:
                setup_data = None  # Transports will handle Colab auth internally
            else:
                setup_data = {"credentials": self.credentials}
            success = transport.setup(setup_data)

            if success:
                if self.verbose:
                    print(f"✓ {name} setup successful")

                # Update config
                config = self.load_platform_config()
                if "transports" not in config:
                    config["transports"] = {}

                config["transports"][name] = {
                    "configured": True,
                    "configured_at": datetime.now().isoformat(),
                    "active": True,
                }
                self.save_platform_config(config)

            else:
                if self.verbose:
                    print(f"✗ {name} setup failed")

            return success

        except Exception as e:
            if self.verbose:
                print(f"✗ {name} setup error: {e}")
                import traceback

                traceback.print_exc()
            return False

    def configure_transports(self) -> Dict[str, Any]:
        """Interactive wizard for adding transports later"""
        print("\n🔧 Transport Configuration")
        print("=" * 50)

        # Check current status
        status = self.check_transport_status()
        available = self.show_available_transports()

        configured = [t for t in available if t["configured"]]
        not_configured = [t for t in available if not t["configured"]]

        if configured:
            print("\n✅ Currently configured:")
            for t in configured:
                print(f"   • {t['name']}")

        if not not_configured:
            print("\n✓ All transports are already configured!")
            reconfigure = input("\nWould you like to reconfigure any? (y/n): ").lower()
            if reconfigure != "y":
                return {"message": "All transports already configured"}
            # Show all for reconfiguration
            not_configured = available
        else:
            print("\n○ Not yet configured:")
            for t in not_configured:
                print(f"   • {t['name']} - {t['description']}")

        print("\nWhich would you like to set up?")
        for i, transport in enumerate(not_configured, 1):
            print(f"{i}. {transport['name']}")
        print("0. Cancel")

        choice = input("\nSelect (0-{}): ".format(len(not_configured))).strip()

        if choice == "0" or not choice:
            print("Configuration cancelled.")
            return {"cancelled": True}

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(not_configured):
                transport = not_configured[idx]
                if self.setup_transport(transport["id"]):
                    print(f"\n✓ {transport['name']} configured successfully!")

                    # Ask if they want to configure more
                    more = input("\nConfigure another transport? (y/n): ").lower()
                    if more == "y":
                        return self.configure_transports()  # Recursive call

                    return {"configured": [transport["id"]]}
                else:
                    return {"failed": [transport["id"]]}
            else:
                print("Invalid selection.")
                return {"error": "Invalid selection"}

        except ValueError:
            print("Invalid input.")
            return {"error": "Invalid input"}

    # ===== Configuration Methods =====
    # Config methods are now inherited from BasePlatformClient

    # ===== Google Drive Folder Operations =====

    def download_gdrive_folder(self, folder_name: str, local_path: str, recursive: bool = True) -> bool:
        """
        Download entire folder from Google Drive to local system
        
        Args:
            folder_name: Name of the folder on Google Drive to download
            local_path: Local directory path where the folder should be downloaded
            recursive: Whether to download subfolders recursively (default: True)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.gdrive_files or not self.gdrive_files.is_setup():
            if self.verbose:
                print("❌ Google Drive transport is not set up")
            return False
            
        try:
            import os
            from pathlib import Path
            
            # Validate local path
            local_path = Path(local_path).resolve()
            if not local_path.exists():
                if self.verbose:
                    print(f"❌ Local path does not exist: {local_path}")
                return False
                
            if not local_path.is_dir():
                if self.verbose:
                    print(f"❌ Local path is not a directory: {local_path}")
                return False
            
            # Find the folder on Google Drive
            folder_id = self._find_gdrive_folder_by_name(folder_name)
            if not folder_id:
                if self.verbose:
                    print(f"❌ Folder '{folder_name}' not found on Google Drive")
                return False
            
            # Create local folder
            local_folder_path = local_path / folder_name
            local_folder_path.mkdir(exist_ok=True)
            
            if self.verbose:
                print(f"📁 Downloading folder '{folder_name}' to {local_folder_path}")
            
            # Download folder contents and track downloaded files
            downloaded_files = []
            success = self._download_folder_contents(folder_id, local_folder_path, recursive, downloaded_files)
            
            if success:
                print(f"✅ Successfully downloaded folder '{folder_name}'")
                if downloaded_files:
                    print(f"\n📋 Downloaded files ({len(downloaded_files)} total):")
                    for file_path in downloaded_files:
                        print(f"   • {file_path}")
                else:
                    print("   📂 Folder was empty or contained only Google Workspace files")
            elif not success:
                print(f"❌ Failed to download folder '{folder_name}'")
                
            return success
            
        except Exception as e:    
            print(f"❌ Error downloading folder: {e}")
            return False
    
    def _find_gdrive_folder_by_name(self, folder_name: str) -> Optional[str]:
        """Find a folder by name on Google Drive and return its ID"""
        try:
            # Search for folder by name
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = (
                self.gdrive_files.drive_service.files()
                .list(q=query, fields="files(id, name)", pageSize=10)
                .execute()
            )
            
            files = results.get("files", [])
            if not files:
                return None
                
            if len(files) > 1:
                raise ValueError(
                    f"Multiple folders named '{folder_name}' found on Google Drive. "
                    f"Handling duplicate folder names is not implemented yet. "
                    f"Please ensure folder names are unique or specify the folder by ID."
                )
                
            return files[0]["id"]
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error searching for folder: {e}")
            return None
    
    def _download_folder_contents(self, folder_id: str, local_folder_path: Path, recursive: bool = True, downloaded_files: List[str] = None) -> bool:
        """Download all contents of a Google Drive folder to local path"""
        if downloaded_files is None:
            downloaded_files = []
            
        try:
            # List all items in the folder
            query = f"'{folder_id}' in parents and trashed=false"
            results = (
                self.gdrive_files.drive_service.files()
                .list(
                    q=query,
                    fields="files(id, name, mimeType, size)",
                    pageSize=1000
                )
                .execute()
            )
            
            files = results.get("files", [])
            if not files:
                if self.verbose:
                    print(f"   📂 Empty folder")
                return True
            
            download_count = 0
            error_count = 0
            
            for file in files:
                file_id = file["id"]
                file_name = file["name"]
                mime_type = file["mimeType"]
                
                if mime_type == "application/vnd.google-apps.folder":
                    # Handle subfolder
                    if recursive:
                        subfolder_path = local_folder_path / file_name
                        subfolder_path.mkdir(exist_ok=True)
                        
                        if self.verbose:
                            print(f"   📁 Downloading subfolder: {file_name}")
                        
                        if self._download_folder_contents(file_id, subfolder_path, recursive, downloaded_files):
                            download_count += 1
                        else:
                            error_count += 1
                    else:
                        if self.verbose:
                            print(f"   ⏭️  Skipping subfolder (recursive=False): {file_name}")
                else:
                    # Handle regular file
                    local_file_path = local_folder_path / file_name
                    
                    if self._download_gdrive_file(file_id, file_name, local_file_path, mime_type):
                        download_count += 1
                        # Track downloaded file with relative path from the root download folder
                        relative_path = local_file_path.relative_to(local_folder_path.parent)
                        downloaded_files.append(str(relative_path))
                        if self.verbose:
                            print(f"   ✅ Downloaded: {file_name}")
                    else:
                        error_count += 1
                        if self.verbose:
                            print(f"   ❌ Failed to download: {file_name}")
            
            if self.verbose:
                print(f"   📊 Downloaded {download_count} items, {error_count} errors")
            
            return error_count == 0
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error downloading folder contents: {e}")
            return False
    
    def _download_gdrive_file(self, file_id: str, file_name: str, local_path: Path, mime_type: str) -> bool:
        """Download a single file from Google Drive to local path"""
        try:
            from googleapiclient.http import MediaIoBaseDownload
            
            # Skip Google Workspace files for now (Docs, Sheets, etc.)
            if mime_type.startswith("application/vnd.google-apps."):
                if self.verbose:
                    print(f"   ⏭️  Skipping Google Workspace file: {file_name}")
                return True
            
            # Download regular files only
            request = self.gdrive_files.drive_service.files().get_media(fileId=file_id)
            
            # Download to local file
            with open(local_path, 'wb') as local_file:
                downloader = MediaIoBaseDownload(local_file, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
            
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"   ❌ Error downloading file {file_name}: {e}")
            return False

    # ===== Legacy/Existing Methods (To be refactored) =====

    def get_transport_layers(self) -> List[str]:
        """Get list of available transport layers"""
        # Always return what transports are available for this platform
        # whether they're initialized or not
        if hasattr(self, "transports") and self.transports:
            return list(self.transports.keys())
        else:
            # Return what would be available if initialized
            return ["gmail", "gdrive_files", "gsheets", "gforms"]

    # get_transport_instances() is now inherited from BasePlatformClient

    @property
    def login_complexity(self) -> int:
        """OAuth2 authentication complexity for Google Workspace"""
        from ...environment import Environment

        # Check for cached credentials
        if self._has_cached_credentials():
            return 0

        if self.current_environment == Environment.COLAB:
            return 1  # Single step - Colab built-in OAuth
        else:
            # OAuth2 flow required with possible admin consent
            return 3  # OAuth2 redirect + admin consent

    def _has_cached_credentials(self) -> bool:
        """Check if we have cached OAuth2 tokens"""
        try:
            # Quick check without full wallet initialization
            wallet = LocalFileWallet({})
            token_data = wallet.retrieve_token(
                service=self.platform, account=self.email
            )
            return token_data is not None
        except:
            return False
