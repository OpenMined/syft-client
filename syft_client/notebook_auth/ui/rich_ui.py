"""Rich-based UI for notebook authentication flow."""

from typing import Callable, Optional, Tuple
from rich.console import Console
import time

try:
    from .rich_components import RichComponents
except ImportError:
    # Fallback for direct imports
    from rich_components import RichComponents


class RichAuthUI:
    """
    Manages the Rich-based UI flow for Google Workspace authentication.

    This is a drop-in replacement for NotebookAuthUI using Rich instead of ipywidgets.
    """

    def __init__(self, console: Optional[Console] = None):
        """Initialize the Rich UI."""
        self.console = console or Console()
        self.components = RichComponents(self.console)

    def display(self):
        """Display initial UI (no-op for Rich, as we print directly)."""
        self.console.print("\n")
        self.components.display_panel(
            "[bold cyan]Google Workspace Authentication Setup[/bold cyan]\n"
            "This wizard will guide you through setting up OAuth credentials for Google Workspace APIs.",
            title="🔐 Authentication Setup",
            border_style="cyan",
        )

    def show_drive_mounting(self, on_mount: Callable[[], bool]) -> None:
        """
        Show Drive mount step (Colab only).

        Args:
            on_mount: Callback to execute mount, returns success bool
        """
        self.components.display_panel(
            "First, we need to mount your Google Drive to save OAuth credentials.\n\n"
            "[dim]Your OAuth credentials will be saved to:[/dim]\n"
            "[cyan]/MyDrive/.syft_credentials/[/cyan]\n\n"
            "[dim]This ensures you only need to configure OAuth once![/dim]",
            title="📂 Google Drive Setup",
            border_style="blue",
        )

        if self.components.confirm_action(
            "Mount Google Drive now?", default=True, emoji="📂"
        ):
            with self.components.show_spinner("Mounting Google Drive..."):
                time.sleep(1)  # Give visual feedback
                success = on_mount()

            if success:
                self.components.display_success(
                    "Google Drive mounted successfully!\n"
                    "[dim]Credentials will be saved to: /MyDrive/.syft_credentials/[/dim]"
                )
            else:
                self.components.display_error("Failed to mount Google Drive")
        else:
            self.components.display_warning("Drive mount skipped")

    def show_checking_cached_credentials(self):
        """Show checking for cached credentials."""
        with self.components.show_spinner("Checking for saved credentials..."):
            time.sleep(0.5)  # Give visual feedback

    def show_cached_found(
        self,
        email: str,
        project_id: str,
        on_continue: Callable,
        on_reconfigure: Callable,
    ) -> None:
        """
        Show cached credentials found screen and handle user choice.

        Args:
            email: User email
            project_id: GCP project ID
            on_continue: Callback to continue with cached creds
            on_reconfigure: Callback to run setup again
        """
        self.components.display_panel(
            "[green]✅ Found saved OAuth credentials![/green]\n\n"
            f"[bold]Project:[/bold] [cyan]{project_id}[/cyan]\n"
            f"[bold]User:[/bold] {email}\n\n"
            "[dim]💡 Using saved credentials. Skip OAuth setup![/dim]",
            title="🔐 Saved Configuration Found",
            border_style="green",
        )

        if self.components.confirm_action(
            "Continue with saved setup?", default=True, emoji="➡️"
        ):
            on_continue()
        else:
            on_reconfigure()

    def show_tos_check(
        self,
        user_name: str,
        console_url: str,
        on_accepted: Callable,
        _on_retry: Callable,
    ):
        """
        Show Terms of Service acceptance required.

        Args:
            user_name: User's first name
            console_url: GCP Console URL
            on_accepted: Callback when user says they accepted
            on_retry: Callback to check ToS again
        """
        self.components.display_panel(
            f"[yellow]⚠️ Terms of Service Required[/yellow]\n\n"
            f"Hey {user_name}, please accept GCP's Terms of Service.\n\n"
            f"[link={console_url}]🔗 Click here to accept Terms of Service[/link]\n"
            f"Or visit: [cyan]{console_url}[/cyan]",
            title="📋 Terms of Service",
            border_style="yellow",
        )

        if self.components.confirm_action(
            "I've accepted the Terms of Service", default=False, emoji="✓"
        ):
            on_accepted()

    def show_tos_accepted(self, user_name: str):
        """Show ToS accepted confirmation."""
        self.components.display_success(f"Terms of Service accepted, {user_name}.")

    def show_project_selection(
        self,
        user_name: str,
        projects: list[dict],
        on_select: Callable[[str], None],
    ):
        """
        Show project selection screen.

        Args:
            user_name: User's first name
            projects: List of project dicts with 'project_id' and 'name'
            on_select: Callback with selected project_id or 'CREATE_NEW'
        """
        if projects:
            self.console.print(
                f"[bold]Hey {user_name}![/bold] Which project would you like to use?\n"
            )

            options = [
                {"label": f"{p['name']} ({p['project_id']})", "value": p["project_id"]}
                for p in projects
            ]

            selected = self.components.select_from_menu(
                title="Select Your GCP Project",
                options=options,
                show_create_new=True,
                emoji="📁",
            )

            on_select(selected)
        else:
            # No projects, must create one
            self.console.print(
                f"[bold]Hey {user_name}![/bold] Let's create a GCP project for your Workspace APIs.\n"
            )
            on_select("CREATE_NEW")

    def show_project_creation(self, project_name: str):
        """Show project creation in progress."""
        self.console.print(
            f"\n[bold]Creating project:[/bold] [cyan]{project_name}[/cyan]\n"
        )

    def show_project_created(self, project_id: str):
        """Show project created successfully."""
        self.components.display_success(
            f"Project created successfully!\n[bold]Project ID:[/bold] [cyan]{project_id}[/cyan]"
        )

    def show_oauth_consent_instructions(
        self, project_id: str, user_email: str, on_done: Callable
    ):
        """
        Show OAuth consent screen setup instructions.

        Args:
            project_id: GCP project ID
            user_email: User's email address
            on_done: Callback when user confirms completion
        """
        consent_url = f"https://console.cloud.google.com/apis/credentials/consent?project={project_id}"

        steps = [
            "[bold]User Type:[/bold] Select [cyan]External[/cyan], then click [bold]CREATE[/bold]",
            f"[bold]App Information:[/bold]\n"
            f"  • App name: [cyan]My Workspace App[/cyan] (or any name)\n"
            f"  • User support email: [cyan]{user_email}[/cyan]\n"
            f"  • Developer contact: [cyan]{user_email}[/cyan]",
            "Click [bold]SAVE AND CONTINUE[/bold]",
            "[bold]Scopes:[/bold] Skip this (click [bold]SAVE AND CONTINUE[/bold])",
            "[bold]Test users:[/bold] Skip this (click [bold]SAVE AND CONTINUE[/bold])",
            "[bold]Summary:[/bold] Click [bold]BACK TO DASHBOARD[/bold]",
        ]

        notes = [
            "We're using non-restricted scopes only, so no test users or verification needed!"
        ]

        self.components.display_instructions(
            title="🔧 OAuth Consent Screen Setup",
            steps=steps,
            url=consent_url,
            notes=notes,
        )

        if self.components.confirm_action(
            "I have configured the OAuth consent screen", default=False, emoji="✓"
        ):
            on_done()

    def show_oauth_client_instructions(self, project_id: str, on_done: Callable):
        """
        Show OAuth client ID creation instructions.

        Args:
            project_id: GCP project ID
            on_done: Callback when user confirms completion
        """
        credentials_url = (
            f"https://console.cloud.google.com/apis/credentials?project={project_id}"
        )

        steps = [
            "Click [bold]+ CREATE CREDENTIALS[/bold] at the top",
            "Select [bold]OAuth client ID[/bold]",
            "[bold]Application type:[/bold] Select [bold]Desktop app[/bold] (IMPORTANT!)",
            "[bold]Name:[/bold] [cyan]Workspace API Client[/cyan] (or any name)",
            "Click [bold]CREATE[/bold]",
            "A popup will show your client ID and secret",
            "Click [bold]DOWNLOAD JSON[/bold] (the download icon)",
            "The file will be named something like [cyan]client_secret_123456.json[/cyan]",
        ]

        notes = [
            "Make sure to select [bold]Desktop app[/bold] type, NOT Web application!"
        ]

        self.components.display_instructions(
            title="🔑 Create OAuth Client ID",
            steps=steps,
            url=credentials_url,
            notes=notes,
        )

        if self.components.confirm_action(
            "I have downloaded the client_secret.json file", default=False, emoji="✓"
        ):
            on_done()

    def show_paste_client_secret(self, on_submit: Callable[[str], Tuple[bool, str]]):
        """
        Show client secret paste screen.

        Args:
            on_submit: Callback that takes JSON string and returns (success, message)
        """
        self.components.display_panel(
            "Now paste the contents of your downloaded [cyan]client_secret.json[/cyan] file.\n\n"
            "[bold]📝 Instructions:[/bold]\n"
            "1. Open the downloaded [cyan]client_secret_....json[/cyan] file in a text editor\n"
            "2. Copy [bold]ALL[/bold] the content (Ctrl+A, Ctrl+C or Cmd+A, Cmd+C)\n"
            "3. Paste it when prompted below\n\n"
            "[dim]It should look like:[/dim]\n"
            '[dim]{"installed":{"client_id":"123456-abc.apps...","project_id":"...","auth_uri":"...",...}}[/dim]',
            title="📋 Paste OAuth Credentials",
            border_style="blue",
        )

        while True:
            try:
                content = self.components.get_multiline_input(
                    "Paste your client_secret.json content:",
                    placeholder="Paste the entire JSON content here...",
                    validate_json=False,  # We'll validate in on_submit
                )

                if not content.strip():
                    self.components.display_error(
                        "Please paste the JSON content. Try again."
                    )
                    continue

                success, message = on_submit(content)

                if success:
                    self.components.display_success(message)
                    break
                else:
                    self.components.display_error(message)
                    if not self.components.confirm_action(
                        "Try again?", default=True, emoji="🔄"
                    ):
                        raise RuntimeError("User cancelled client secret input")

            except KeyboardInterrupt:
                self.components.display_warning("Operation cancelled")
                raise

    def show_enabling_apis(self, apis: list[str]):
        """Show API enabling in progress."""
        self.console.print("\n[bold]⚙️ Enabling Workspace APIs...[/bold]\n")

        # Show initial status
        status = {api: "enabling" for api in apis}
        self.components.display_api_status(status, title="⚙️ Enabling APIs")

    def update_api_status(self, results: dict[str, str]):
        """
        Update API enabling status.

        Args:
            results: Dict mapping api_name to status ('enabled', 'already_enabled', 'error')
        """
        self.components.display_api_status(results, title="⚙️ API Status")

        self.components.display_info_box(
            "⏱️ APIs may take 1-2 minutes to fully propagate. We'll wait a bit before testing...",
            box_type="info",
            title="Note",
        )

    def show_oauth_flow(
        self, auth_url: str, on_submit: Callable[[str], Tuple[bool, str]]
    ):
        """
        Show OAuth authentication flow with manual URL paste.

        Args:
            auth_url: Authorization URL for user to visit
            on_submit: Callback that takes redirect URL and returns (success, message)
        """
        self.components.display_panel(
            "[bold cyan]Let's connect your Google account to enable Workspace APIs.[/bold cyan]\n\n"
            "[bold green]Step 1: Click the link below to authenticate[/bold green]\n"
            f"[link={auth_url}]🔐 Click here to authenticate with Google[/link]\n"
            f"Or visit: [cyan]{auth_url}[/cyan]\n\n"
            "[bold]What happens next:[/bold]\n"
            "1. Sign in with your Google account (if prompted)\n"
            "2. Review permissions - you'll see what access the app needs\n"
            '3. Click [bold]"Allow"[/bold] to grant access\n'
            "4. [bold yellow]Important:[/bold] Browser will show an error page - [bold green]THIS IS NORMAL![/bold green]\n\n"
            "[yellow]⚠️ You'll see \"This site can't be reached\" - Don't worry![/yellow]\n"
            'After clicking "Allow", your browser will try to open [cyan]http://localhost:8080[/cyan]\n'
            'and show an error like [bold]"This site can\'t be reached"[/bold] or [bold]"Unable to connect"[/bold].\n\n'
            "[bold green]🎯 This is completely normal and expected![/bold green] We just need the URL from your address bar.",
            title="🔐 Google Workspace Authentication",
            border_style="cyan",
        )

        self.components.display_info_box(
            "[bold]📋 Step 2: Copy the URL from your browser's address bar[/bold]\n\n"
            "After you see the error page, look at the [bold]top of your browser[/bold] where the URL is shown.\n\n"
            "[dim]🔍 The address bar will show something like:[/dim]\n"
            "[cyan]http://localhost:8080/?state=ABC123&code=4/0AeanS0ZWh7v-1234567890abcdefg&scope=https://...[/cyan]\n\n"
            "[bold]Instructions:[/bold]\n"
            "1. Click in the address bar (the URL field at the top)\n"
            "2. Select all the text (Ctrl+A on Windows/Linux, Cmd+A on Mac)\n"
            "3. Copy it (Ctrl+C on Windows/Linux, Cmd+C on Mac)\n"
            "4. Paste it when prompted below\n\n"
            '[dim]💡 Tip: Make sure to copy the ENTIRE URL including everything after the "?" mark.[/dim]',
            box_type="info",
            title="Copy URL Instructions",
        )

        while True:
            try:
                url = self.components.get_input(
                    "\n[bold]Step 3:[/bold] Paste the complete URL from your browser",
                )

                if not url.strip():
                    self.components.display_error(
                        "Please paste the URL from your browser's address bar"
                    )
                    continue

                with self.components.show_spinner("Authenticating..."):
                    time.sleep(0.5)  # Give visual feedback
                    success, message = on_submit(url)

                if success:
                    self.components.display_success(
                        f"{message}\n[dim]Your credentials have been saved. Proceeding to test APIs...[/dim]"
                    )
                    break
                else:
                    self.components.display_error(
                        f"{message}\n[dim]Please try again and make sure you copy the complete URL.[/dim]"
                    )
                    if not self.components.confirm_action(
                        "Try again?", default=True, emoji="🔄"
                    ):
                        raise RuntimeError("User cancelled OAuth flow")

            except KeyboardInterrupt:
                self.components.display_warning("Operation cancelled")
                raise

    def show_testing_apis(self, apis: list[str]):
        """Show API testing in progress."""
        self.console.print("\n[bold]🧪 Testing Workspace APIs...[/bold]\n")

        # Show testing status
        status = {api: "testing" for api in apis}
        self.components.display_api_status(status, title="🧪 Testing APIs")

    def update_test_results(self, results: dict[str, str]):
        """
        Update API test results.

        Args:
            results: Dict mapping api_name to status ('working' or 'error')
        """
        self.components.display_api_status(results, title="🧪 Test Results")

    def show_complete(self, user_name: str, project_id: str, _email: str):
        """
        Show setup complete screen.

        Args:
            user_name: User's first name
            project_id: GCP project ID
            _email: User email (currently unused, kept for API compatibility)
        """
        # Get API list from context (default to common ones)
        apis = ["gmail", "drive", "sheets", "forms"]

        self.components.display_completion(user_name, project_id, apis)

    def show_error(self, title: str, message: str):
        """Show error screen."""
        self.components.display_panel(
            f"[red]❌ {message}[/red]",
            title=title,
            border_style="red",
        )
