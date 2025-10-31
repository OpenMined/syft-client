"""Main orchestrator for Google Workspace authentication flow."""

import json
import time
from typing import Optional

from google.auth import default
from google.oauth2.credentials import Credentials

from .core import APIManager, CredentialHandler, OAuthFlow, ProjectManager
from .storage import DriveStorage, LocalStorage
from .ui import NotebookAuthUI


class GoogleWorkspaceAuth:
    """
    Orchestrates the complete Google Workspace authentication flow.

    This is the main entry point that coordinates:
    - Environment detection (Colab vs local Jupyter)
    - Storage backend selection
    - UI display
    - OAuth flow
    - API enabling and testing
    """

    def __init__(
        self,
        email: str,
        scopes: Optional[list[str]] = None,
        verbose: bool = True,
    ):
        """
        Initialize Google Workspace authentication.

        Args:
            email: User's Google email address
            scopes: List of scope names (['gmail', 'drive', 'sheets', 'forms'])
            verbose: Whether to show progress messages
        """
        self.email = email
        self.scope_names = scopes or ["gmail", "drive", "sheets", "forms"]
        self.scopes = OAuthFlow.get_scopes(self.scope_names)
        self.verbose = verbose

        # Detect environment
        self.environment = self._detect_environment()

        # Create storage backend
        self.storage = self._create_storage()

        # Create UI
        self.ui = NotebookAuthUI()

        # State
        self.credentials: Optional[Credentials] = None
        self.project_id: Optional[str] = None
        self.user_info: Optional[dict] = None
        self.gcp_credentials = None  # For project management

    def _detect_environment(self) -> str:
        """Detect if running in Colab or local Jupyter."""
        try:
            import google.colab  # noqa: F401

            return "colab"
        except ImportError:
            return "jupyter"

    def _create_storage(self):
        """Create appropriate storage backend."""
        if self.environment == "colab":
            return DriveStorage()
        else:
            return LocalStorage()

    def run(self, force_new: bool = False) -> Credentials:
        """
        Run the complete authentication flow.

        Args:
            force_new: Force new setup even if cached credentials exist

        Returns:
            OAuth2 Credentials ready to use with Google APIs

        Raises:
            RuntimeError: If authentication fails
        """
        # Display UI
        self.ui.display()

        # Step 1: Handle Colab Drive mount
        if self.environment == "colab":
            if not self.storage.is_drive_mounted():
                self.ui.show_drive_mount(self._mount_drive)
                time.sleep(2)  # Give user time to see the button

                # Wait for mount to complete
                while not self.storage.is_drive_mounted():
                    time.sleep(1)

        # Step 2: Check for cached credentials
        if not force_new:
            self.ui.show_checking_cache()
            time.sleep(0.5)

            cached_creds = self.storage.load_credentials(self.email, self.scopes)

            if cached_creds:
                # Validate cached credentials
                if CredentialHandler.needs_refresh(cached_creds):
                    try:
                        cached_creds = CredentialHandler.refresh(cached_creds)
                        self.storage.save_credentials(self.email, cached_creds)
                    except Exception:
                        cached_creds = None

                if cached_creds and CredentialHandler.validate(cached_creds):
                    # Check if we have saved setup
                    project_info = self.storage.load_project_info(self.email)

                    if project_info:
                        self.project_id = project_info.get("project_id")

                        # Show cached found screen
                        continue_event = {"done": False}
                        reconfigure_event = {"done": False}

                        def on_continue():
                            continue_event["done"] = True

                        def on_reconfigure():
                            reconfigure_event["done"] = True

                        self.ui.show_cached_found(
                            self.email, self.project_id, on_continue, on_reconfigure
                        )

                        # Wait for user choice
                        while (
                            not continue_event["done"] and not reconfigure_event["done"]
                        ):
                            time.sleep(0.5)

                        if continue_event["done"]:
                            self.credentials = cached_creds
                            # Test APIs and return
                            self._test_and_complete()
                            return self.credentials

                        # Fall through to new setup if reconfigure chosen

        # Step 3: Run full setup
        return self._run_full_setup()

    def _mount_drive(self) -> bool:
        """Mount Google Drive (Colab only)."""
        try:
            self.storage.mount_drive()
            return True
        except Exception:
            return False

    def _run_full_setup(self) -> Credentials:
        """Run the complete setup wizard."""
        # Step 1: Authenticate with GCP (for project management)
        self._authenticate_gcp()

        # Step 2: Check Terms of Service
        self._check_tos()

        # Step 3: Get or create project
        self._get_or_create_project()

        # Step 4: Configure OAuth consent screen
        self._setup_oauth_consent()

        # Step 5: Create OAuth client
        self._setup_oauth_client()

        # Step 6: Run OAuth flow to get user credentials
        self._run_oauth_flow()

        # Step 7: Enable APIs
        self._enable_apis()

        # Step 8: Test APIs
        self._test_and_complete()

        return self.credentials

    def _authenticate_gcp(self):
        """Authenticate with GCP for project management."""
        try:
            from google.colab import auth as colab_auth

            colab_auth.authenticate_user()
            self.gcp_credentials, _ = default()

            # Get user info
            self.user_info = ProjectManager.get_user_info(self.gcp_credentials)

        except Exception as e:
            self.ui.show_error(
                "Authentication Error", f"Failed to authenticate with GCP: {e}"
            )
            raise RuntimeError(f"GCP authentication failed: {e}")

    def _check_tos(self):
        """Check if user has accepted GCP Terms of Service."""
        tos_accepted, result = ProjectManager.check_tos(
            self.gcp_credentials, self.user_info["email"]
        )

        if not tos_accepted:
            # Show ToS screen
            accepted_event = {"done": False}

            def on_accepted():
                accepted_event["done"] = True

            def on_retry():
                # Just set done and we'll check again
                pass

            user_name = self.user_info.get("first_name", "there")
            console_url = result  # Result is the console URL

            self.ui.show_tos_check(user_name, console_url, on_accepted, on_retry)

            # Wait for user to accept
            while not accepted_event["done"]:
                time.sleep(1)
                # Re-check ToS
                tos_accepted, _ = ProjectManager.check_tos(
                    self.gcp_credentials, self.user_info["email"]
                )
                if tos_accepted:
                    break

        # Show ToS accepted
        user_name = self.user_info.get("first_name", "there")
        self.ui.show_tos_accepted(user_name)
        time.sleep(1)

    def _get_or_create_project(self):
        """Get existing project or create new one."""
        projects = ProjectManager.list_projects(self.gcp_credentials)
        user_name = self.user_info.get("first_name", "there")

        selected_event = {"project_id": None}

        def on_select(project_id_or_create):
            selected_event["project_id"] = project_id_or_create

        self.ui.show_project_selection(user_name, projects, on_select)

        # Wait for selection
        while selected_event["project_id"] is None:
            time.sleep(0.5)

        if selected_event["project_id"] == "CREATE_NEW":
            # Create new project
            project_id = ProjectManager.generate_project_id()
            self.ui.show_project_creation(project_id)

            success, error = ProjectManager.create_project(
                self.gcp_credentials, project_id
            )

            if not success:
                self.ui.show_error("Project Creation Failed", error)
                raise RuntimeError(f"Failed to create project: {error}")

            self.project_id = project_id
            self.ui.show_project_created(project_id)
            time.sleep(1)
        else:
            self.project_id = selected_event["project_id"]

    def _setup_oauth_consent(self):
        """Guide user through OAuth consent screen setup."""
        done_event = {"done": False}

        def on_done():
            done_event["done"] = True

        self.ui.show_oauth_consent_instructions(
            self.project_id, self.user_info["email"], on_done
        )

        # Wait for user to complete
        while not done_event["done"]:
            time.sleep(0.5)

    def _setup_oauth_client(self):
        """Guide user through OAuth client creation and get client secret."""
        # Check if we already have client secret saved
        client_secret = self.storage.load_client_secret(self.email)

        if not client_secret:
            # Need to create OAuth client
            done_event = {"done": False}

            def on_done():
                done_event["done"] = True

            self.ui.show_oauth_client_instructions(self.project_id, on_done)

            # Wait for user to complete
            while not done_event["done"]:
                time.sleep(0.5)

            # Now get the client secret JSON
            parsed_event = {"done": False, "client_secret": None}

            def on_submit(json_str):
                try:
                    client_secret_dict = json.loads(json_str)

                    if not OAuthFlow.validate_client_secret(client_secret_dict):
                        return False, "Invalid client secret format"

                    # Save it
                    self.storage.save_client_secret(self.email, client_secret_dict)

                    # Save project info
                    project_info = {
                        "project_id": self.project_id,
                        "user_email": self.user_info["email"],
                        "user_name": self.user_info["first_name"],
                    }
                    self.storage.save_project_info(self.email, project_info)

                    parsed_event["client_secret"] = client_secret_dict
                    parsed_event["done"] = True

                    return True, "Credentials parsed and saved successfully!"

                except json.JSONDecodeError:
                    return False, "Invalid JSON format"
                except Exception as e:
                    return False, str(e)

            self.ui.show_paste_client_secret(on_submit)

            # Wait for parsing
            while not parsed_event["done"]:
                time.sleep(0.5)

            client_secret = parsed_event["client_secret"]

        return client_secret

    def _run_oauth_flow(self):
        """Run OAuth flow to get user credentials."""
        # Get client secret
        client_secret = self.storage.load_client_secret(self.email)

        if not client_secret:
            raise RuntimeError("No client secret found")

        # Create OAuth flow
        flow = OAuthFlow.create_flow(client_secret, self.scopes)

        # Get authorization URL
        auth_url, state = OAuthFlow.get_auth_url(flow)

        # Show OAuth flow UI
        completed_event = {"done": False, "credentials": None}

        def on_submit(redirect_url):
            try:
                credentials = OAuthFlow.exchange_code(flow, redirect_url)
                completed_event["credentials"] = credentials
                completed_event["done"] = True

                # Save credentials
                self.storage.save_credentials(self.email, credentials)

                return True, "Authentication successful!"

            except ValueError as e:
                return False, str(e)
            except Exception as e:
                return False, f"Authentication failed: {e}"

        self.ui.show_oauth_flow(auth_url, on_submit)

        # Wait for completion
        while not completed_event["done"]:
            time.sleep(0.5)

        self.credentials = completed_event["credentials"]

    def _enable_apis(self):
        """Enable all Workspace APIs."""
        self.ui.show_enabling_apis(self.scope_names)
        time.sleep(1)

        # Enable APIs
        results = APIManager.enable_all(
            self.gcp_credentials, self.project_id, self.scope_names
        )

        # Update UI with results
        self.ui.update_api_status(results)
        time.sleep(2)

        # Wait for APIs to propagate
        time.sleep(30)

    def _test_and_complete(self):
        """Test all APIs and show completion."""
        self.ui.show_testing_apis(self.scope_names)
        time.sleep(1)

        # Test APIs
        results = APIManager.test_all(self.credentials, self.scope_names)

        # Update UI with results
        self.ui.update_test_results(results)
        time.sleep(2)

        # Show complete screen
        user_name = (
            self.user_info.get("first_name", "there") if self.user_info else "there"
        )
        project_id = self.project_id or "unknown"

        self.ui.show_complete(user_name, project_id, self.email)
