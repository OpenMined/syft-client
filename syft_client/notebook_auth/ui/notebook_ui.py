"""Main UI container for notebook authentication flow."""

from typing import Callable

import ipywidgets as widgets
from IPython.display import display

from .components import UIComponents


class NotebookAuthUI:
    """
    Manages the interactive UI flow for Google Workspace authentication.

    Extracted from scratch.py and cleaned up with separated concerns:
    - UI logic here
    - Business logic in core modules
    - Reusable components in UIComponents
    """

    def __init__(self):
        """Initialize the UI container."""
        self.container = widgets.VBox()
        self.current_step = None

    def display(self):
        """Display the UI container."""
        display(self.container)

    def show_drive_mounting(self, on_mount: Callable[[], bool]) -> None:
        """
        Show Drive mount step (Colab only).

        Args:
            on_mount: Callback to execute mount, returns success bool
        """
        message = widgets.HTML(
            value="""
            <p style='margin-bottom: 15px;'>First, we need to mount your Google Drive to save OAuth credentials.</p>
            <p style='font-size: 13px; color: #5f6368; background: #f1f3f4; padding: 12px; border-radius: 4px;'>
                Your OAuth credentials will be saved to:<br>
                <code>/MyDrive/.syft_credentials/</code><br><br>
                This ensures you only need to configure OAuth once!
            </p>
            """
        )

        mount_btn = UIComponents.create_button("📂 Mount Google Drive", None)

        def handle_mount(btn):
            btn.disabled = True
            btn.description = "Mounting..."

            try:
                success = on_mount()

                if success:
                    success_msg = widgets.HTML(
                        value="""
                        <p style='color: #34a853; font-size: 16px;'>✅ Google Drive mounted successfully!</p>
                        <p style='font-size: 12px; color: #5f6368; margin-top: 10px;'>
                            Credentials will be saved to: <code>/MyDrive/.syft_credentials/</code>
                        </p>
                        """
                    )
                    card = UIComponents.create_card(
                        "📂 Google Drive Setup", [success_msg]
                    )
                    self.container.children = [card]
                else:
                    error_msg = widgets.HTML(
                        value="<p style='color: #d93025;'>❌ Failed to mount Google Drive</p>"
                    )
                    card = UIComponents.create_card(
                        "📂 Google Drive Setup", [error_msg]
                    )
                    self.container.children = [card]

            except Exception as e:
                error_msg = widgets.HTML(
                    value=f"<p style='color: #d93025;'>❌ Error: {str(e)}</p>"
                )
                card = UIComponents.create_card("📂 Google Drive Setup", [error_msg])
                self.container.children = [card]

        mount_btn.on_click(handle_mount)

        card = UIComponents.create_card("📂 Google Drive Setup", [message], [mount_btn])
        self.container.children = [card]

    def show_checking_cached_credentials(self):
        """Show checking for cached credentials."""
        message, progress = UIComponents.create_progress(
            "Checking for saved credentials...", 50
        )
        card = UIComponents.create_card("🔍 Loading", [message, progress])
        self.container.children = [card]

    def show_cached_found(
        self,
        email: str,
        project_id: str,
        on_continue: Callable,
        on_reconfigure: Callable,
    ):
        """
        Show cached credentials found screen.

        Args:
            email: User email
            project_id: GCP project ID
            on_continue: Callback to continue with cached creds
            on_reconfigure: Callback to run setup again
        """
        found_msg = widgets.HTML(
            value=f"""
            <p style='color: #34a853; font-size: 16px;'>✅ Found saved OAuth credentials!</p>
            <p style='color: #5f6368; margin-top: 10px;'>
                Project: <code>{project_id}</code><br>
                User: <b>{email}</b>
            </p>
            <p style='font-size: 13px; color: #5f6368; background: #e8f5e9; padding: 10px; border-radius: 4px; margin-top: 10px;'>
                💡 Using saved credentials. Skip OAuth setup!
            </p>
            """
        )

        continue_btn = UIComponents.create_button(
            "Continue with saved setup →", lambda b: on_continue()
        )
        reconfigure_btn = UIComponents.create_button(
            "↻ Reconfigure OAuth", lambda b: on_reconfigure(), style=""
        )

        card = UIComponents.create_card(
            "🔐 Saved Configuration Found", [found_msg], [continue_btn, reconfigure_btn]
        )
        self.container.children = [card]

    def show_tos_check(
        self,
        user_name: str,
        console_url: str,
        on_accepted: Callable,
        on_retry: Callable,
    ):
        """
        Show Terms of Service acceptance required.

        Args:
            user_name: User's first name
            console_url: GCP Console URL
            on_accepted: Callback when user says they accepted
            on_retry: Callback to check ToS again
        """
        warning_msg = widgets.HTML(
            value=f"""
            <p style='color: #f9ab00; font-size: 16px; margin-bottom: 15px;'>⚠️ Terms of Service Required</p>
            <p style='margin-bottom: 15px;'>
                Hey {user_name}, please accept GCP's Terms of Service.
            </p>
            <p style='margin: 15px 0;'>
                <a href='{console_url}' target='_blank'
                   style='display: inline-block; background: #4285f4; color: white;
                          padding: 10px 20px; border-radius: 6px; text-decoration: none;'>
                    🔗 Accept Terms of Service
                </a>
            </p>
            """
        )

        check_btn = UIComponents.create_button(
            "✓ I've accepted it, continue", lambda b: on_accepted()
        )

        card = UIComponents.create_card(
            "📋 Terms of Service", [warning_msg], [check_btn]
        )
        self.container.children = [card]

    def show_tos_accepted(self, user_name: str):
        """Show ToS accepted confirmation."""
        success_msg = widgets.HTML(
            value=f"<p style='color: #34a853; font-size: 16px;'>✅ Terms of Service accepted, {user_name}.</p>"
        )
        card = UIComponents.create_card("📋 Terms of Service", [success_msg])
        self.container.children = [card]

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
            on_select: Callback with selected project_id or '🆕 Create a new project'
        """
        if projects:
            greeting = widgets.HTML(
                value=f"<p>Hey {user_name}! Which project would you like to use?</p>"
            )

            options = [f"{p['name']} ({p['project_id']})" for p in projects]
            options.append("🆕 Create a new project")

            dropdown = UIComponents.create_dropdown(options, "Project:")

            def handle_select(btn):
                selection = dropdown.value
                if selection == "🆕 Create a new project":
                    on_select("CREATE_NEW")
                else:
                    # Extract project_id from "Name (project-id)" format
                    project_id = selection.split("(")[-1].strip(")")
                    on_select(project_id)

            select_btn = UIComponents.create_button(
                "Continue with Selected Project →", handle_select
            )

            card = UIComponents.create_card(
                "📁 Select Your GCP Project", [greeting, dropdown], [select_btn]
            )
            self.container.children = [card]
        else:
            # No projects, must create one
            greeting = widgets.HTML(
                value=f"""
                <p style='font-size: 16px; margin-bottom: 15px;'>
                    Hey {user_name}, let's create a GCP project for your Workspace APIs.
                </p>
                """
            )

            card = UIComponents.create_card("📁 Select Your GCP Project", [greeting])
            self.container.children = [card]
            on_select("CREATE_NEW")

    def show_project_creation(self, project_name: str):
        """Show project creation in progress."""
        creating_msg = widgets.HTML(
            value=f"<p>Creating project: <code>{project_name}</code></p>"
        )
        _, progress = UIComponents.create_progress("Creating project...", 50)

        card = UIComponents.create_card("📁 Creating Project", [creating_msg, progress])
        self.container.children = [card]

    def show_project_created(self, project_id: str):
        """Show project created successfully."""
        success_msg = widgets.HTML(
            value=f"""
            <p style='color: #34a853; font-size: 16px;'>✅ Project created successfully!</p>
            <p style='color: #5f6368; margin-top: 10px;'>
                Project: <code>{project_id}</code>
            </p>
            """
        )
        card = UIComponents.create_card("📁 Creating Project", [success_msg])
        self.container.children = [card]

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

        instructions = widgets.HTML(
            value=f"""
            <p style='font-size: 16px; margin-bottom: 15px;'>
                Now let's configure your OAuth consent screen for Workspace APIs.
            </p>
            <p style='margin: 15px 0;'>
                <a href='{consent_url}' target='_blank'
                   style='display: inline-block; background: #4285f4; color: white;
                          padding: 12px 24px; border-radius: 6px; text-decoration: none; font-size: 16px;'>
                    🔧 Configure OAuth Consent Screen
                </a>
            </p>
            <div style='background: #f1f3f4; border-radius: 8px; padding: 20px; margin: 20px 0;'>
                <p style='font-weight: 500; margin: 0 0 15px 0; font-size: 15px; color: #202124;'>📝 Follow these steps:</p>
                <ol style='margin: 0; padding-left: 20px; line-height: 2; color: #202124;'>
                    <li><b>User Type:</b> Select <code>External</code>, then click <b>CREATE</b></li>
                    <li><b>App Information:</b>
                        <ul style='color: #202124;'>
                            <li>App name: <code>My Workspace App</code> (or any name)</li>
                            <li>User support email: <code>{user_email}</code></li>
                            <li>Developer contact: <code>{user_email}</code></li>
                        </ul>
                    </li>
                    <li>Click <b>SAVE AND CONTINUE</b></li>
                    <li><b>Scopes:</b> Skip this (click <b>SAVE AND CONTINUE</b>)</li>
                    <li><b>Test users:</b> Skip this (click <b>SAVE AND CONTINUE</b>)</li>
                    <li><b>Summary:</b> Click <b>BACK TO DASHBOARD</b></li>
                </ol>
            </div>
            <p style='font-size: 13px; color: #5f6368; background: #e8f5e9; padding: 12px; border-radius: 4px; margin-top: 15px;'>
                ℹ️ <b>Note:</b> We're using <b>non-restricted scopes only</b>, so no test users or verification needed!
            </p>
            """
        )

        checkbox = UIComponents.create_checkbox(
            "I have configured the OAuth consent screen", False
        )
        continue_btn = UIComponents.create_button(
            "Continue →", lambda b: on_done(), disabled=True
        )

        def on_checkbox_change(change):
            continue_btn.disabled = not change["new"]

        checkbox.observe(on_checkbox_change, names="value")

        card = UIComponents.create_card(
            "🔧 OAuth Consent Screen", [instructions, checkbox], [continue_btn]
        )
        self.container.children = [card]

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

        instructions = widgets.HTML(
            value=f"""
            <p style='font-size: 16px; margin-bottom: 15px;'>
                Now create OAuth 2.0 Client ID credentials.
            </p>
            <p style='margin: 15px 0;'>
                <a href='{credentials_url}' target='_blank'
                   style='display: inline-block; background: #4285f4; color: white;
                          padding: 12px 24px; border-radius: 6px; text-decoration: none; font-size: 16px;'>
                    🔑 Create OAuth Client ID
                </a>
            </p>
            <div style='background: #f1f3f4; border-radius: 8px; padding: 20px; margin: 20px 0;'>
                <p style='font-weight: 500; margin: 0 0 15px 0; font-size: 15px; color: #202124;'>📝 Follow these steps:</p>
                <ol style='margin: 0; padding-left: 20px; line-height: 2; color: #202124;'>
                    <li>Click <b>+ CREATE CREDENTIALS</b> at the top</li>
                    <li>Select <b>OAuth client ID</b></li>
                    <li><b>Application type:</b> Select <b>Desktop app</b> (IMPORTANT!)</li>
                    <li><b>Name:</b> <code>Workspace API Client</code> (or any name)</li>
                    <li>Click <b>CREATE</b></li>
                    <li>A popup will show your client ID and secret</li>
                    <li>Click <b>DOWNLOAD JSON</b> (the download icon)</li>
                    <li>The file will be named something like <code>client_secret_123456.json</code></li>
                </ol>
            </div>
            <p style='font-size: 13px; color: #f9ab00; background: #fef7e0; padding: 12px; border-radius: 4px; margin-top: 15px;'>
                ⚠️ <b>Important:</b> Make sure to select <b>Desktop app</b> type, NOT Web application!
            </p>
            """
        )

        checkbox = UIComponents.create_checkbox(
            "I have downloaded the client_secret.json file", False
        )
        continue_btn = UIComponents.create_button(
            "Continue →", lambda b: on_done(), disabled=True
        )

        def on_checkbox_change(change):
            continue_btn.disabled = not change["new"]

        checkbox.observe(on_checkbox_change, names="value")

        card = UIComponents.create_card(
            "🔑 Create OAuth Client ID", [instructions, checkbox], [continue_btn]
        )
        self.container.children = [card]

    def show_paste_client_secret(self, on_submit: Callable[[str], tuple[bool, str]]):
        """
        Show client secret paste screen.

        Args:
            on_submit: Callback that takes JSON string and returns (success, message)
        """
        instructions = widgets.HTML(
            value="""
            <p style='font-size: 16px; margin-bottom: 15px;'>
                Now paste the contents of your downloaded <code>client_secret.json</code> file below.
            </p>
            <div style='background: #f1f3f4; border-radius: 8px; padding: 20px; margin: 20px 0;'>
                <p style='font-weight: 500; margin: 0 0 10px 0; color: #202124;'>📝 Instructions:</p>
                <ol style='margin: 0; padding-left: 20px; line-height: 1.8; color: #202124;'>
                    <li>Open the downloaded <code>client_secret_....json</code> file in a text editor</li>
                    <li>Copy <b>ALL</b> the content (Ctrl+A, Ctrl+C or Cmd+A, Cmd+C)</li>
                    <li>Paste it into the text box below</li>
                </ol>
            </div>
            <p style='font-size: 12px; color: #5f6368; margin-bottom: 10px;'>
                It should look something like this:
            </p>
            <pre style='background: #f8f9fa; padding: 10px; border-radius: 4px; font-size: 11px; overflow-x: auto;'>{"installed":{"client_id":"123456-abc.apps.googleusercontent.com","project_id":"...","auth_uri":"...","token_uri":"...","auth_provider_x509_cert_url":"...","client_secret":"...","redirect_uris":["http://localhost"]}}</pre>
            """
        )

        textarea = UIComponents.create_text_input(
            "Paste your client_secret.json content here...",
            multiline=True,
            height="200px",
        )
        status = widgets.HTML(value="")

        def handle_submit(btn):
            btn.disabled = True
            content = textarea.value.strip()

            if not content:
                status.value = (
                    "<p style='color: #d93025;'>❌ Please paste the JSON content</p>"
                )
                btn.disabled = False
                return

            success, message = on_submit(content)

            if success:
                status.value = f"<p style='color: #34a853;'>✅ {message}</p>"
            else:
                status.value = f"<p style='color: #d93025;'>❌ {message}</p>"
                btn.disabled = False

        parse_btn = UIComponents.create_button("✅ Parse & Continue", handle_submit)

        card = UIComponents.create_card(
            "📋 Paste OAuth Credentials", [instructions, textarea, status], [parse_btn]
        )
        self.container.children = [card]

    def show_enabling_apis(self, apis: list[str]):
        """Show API enabling in progress."""
        status_html = "<div style='margin: 10px 0;'>"
        for api_name in apis:
            status_html += f"<div style='padding: 8px 0; border-bottom: 1px solid #e0e0e0;'><span>⏳ {api_name.title()} API</span> <span style='color: #5f6368;'>Waiting...</span></div>"
        status_html += "</div>"

        status_widget = widgets.HTML(value=status_html)
        _, progress = UIComponents.create_progress("Enabling APIs...", 0)

        card = UIComponents.create_card(
            "⚙️ Enabling Workspace APIs", [status_widget, progress]
        )
        self.container.children = [card]

    def update_api_status(self, results: dict[str, str]):
        """
        Update API enabling status.

        Args:
            results: Dict mapping api_name to status ('enabled', 'already_enabled', 'error')
        """
        status_html = "<div style='margin: 10px 0;'>"

        for api_name, status in results.items():
            if status in ["enabled", "already_enabled"]:
                icon = "✅"
                text = "Enabled"
                color = "#34a853"
            else:
                icon = "❌"
                text = "Error"
                color = "#d93025"

            status_html += f"<div style='padding: 8px 0; border-bottom: 1px solid #e0e0e0;'><span>{icon} {api_name.title()} API</span> <span style='color: {color};'>{text}</span></div>"

        status_html += "</div>"

        # Find the existing card and update it
        if self.container.children:
            self.container.children[0]
            status_widget = widgets.HTML(value=status_html)

            note = widgets.HTML(
                value="""
                <p style='font-size: 13px; color: #5f6368; background: #f1f3f4; padding: 10px; border-radius: 4px; margin-top: 10px;'>
                    ⏱️ <b>Note:</b> APIs may take 1-2 minutes to fully propagate. We'll wait a bit before testing...
                </p>
                """
            )

            card = UIComponents.create_card(
                "⚙️ Enabling Workspace APIs", [status_widget, note]
            )
            self.container.children = [card]

    def show_oauth_flow(
        self, auth_url: str, on_submit: Callable[[str], tuple[bool, str]]
    ):
        """
        Show OAuth authentication flow with manual URL paste.

        Args:
            auth_url: Authorization URL for user to visit
            on_submit: Callback that takes redirect URL and returns (success, message)
        """
        instructions = widgets.HTML(
            value=f"""
            <p style='font-size: 16px; margin-bottom: 20px; color: #202124;'>
                Let's connect your Google account to enable Workspace APIs.
            </p>

            <div style='text-align: center; margin: 20px 0;'>
                <a href='{auth_url}' target='_blank'
                   style='display: inline-block; background: #4285f4; color: white;
                          padding: 14px 28px; border-radius: 8px; text-decoration: none;
                          font-size: 16px; font-weight: 500; box-shadow: 0 2px 4px rgba(0,0,0,0.2);'>
                    🔐 Step 1: Click Here to Authenticate
                </a>
            </div>

            <div style='background: #e8f5e9; border-left: 4px solid #34a853; padding: 20px; border-radius: 4px; margin: 20px 0;'>
                <p style='font-weight: 500; margin: 0 0 15px 0; font-size: 15px; color: #1e7e34;'>
                    ✅ What happens next:
                </p>
                <ol style='margin: 0; padding-left: 20px; line-height: 2; color: #1e7e34;'>
                    <li style='margin-bottom: 8px;'><b>Sign in</b> with your Google account (if prompted)</li>
                    <li style='margin-bottom: 8px;'><b>Review permissions</b> - you'll see what access the app needs</li>
                    <li style='margin-bottom: 8px;'><b>Click "Allow"</b> to grant access</li>
                    <li style='margin-bottom: 8px;'><b>Important:</b> Browser will show an error page - <b>THIS IS NORMAL!</b> ✅</li>
                </ol>
            </div>

            <div style='background: #fff3cd; border-left: 4px solid #f9ab00; padding: 20px; border-radius: 4px; margin: 20px 0;'>
                <p style='font-weight: 500; margin: 0 0 15px 0; font-size: 15px; color: #856404;'>
                    ⚠️ You'll see "This site can't be reached" - Don't worry!
                </p>
                <p style='margin: 0 0 15px 0; color: #856404; line-height: 1.8;'>
                    After clicking "Allow", your browser will try to open <code>http://localhost:8080</code>
                    and show an error like <b>"This site can't be reached"</b> or <b>"Unable to connect"</b>.
                </p>
                <p style='margin: 0; color: #856404; font-weight: 500; line-height: 1.8;'>
                    🎯 <b>This is completely normal and expected!</b> We just need the URL from your address bar.
                </p>
            </div>

            <div style='background: #f1f3f4; border-radius: 8px; padding: 20px; margin: 20px 0;'>
                <p style='font-weight: 500; margin: 0 0 15px 0; font-size: 15px; color: #202124;'>
                    📋 Step 2: Copy the URL from your browser's address bar
                </p>
                <p style='margin: 0 0 15px 0; color: #202124; line-height: 1.8;'>
                    After you see the error page, look at the <b>top of your browser</b> where the URL is shown.
                </p>

                <div style='background: white; border: 2px solid #4285f4; border-radius: 6px; padding: 15px; margin: 15px 0;'>
                    <p style='margin: 0 0 8px 0; font-size: 12px; color: #5f6368;'>
                        🔍 The address bar will show something like this:
                    </p>
                    <code style='display: block; background: #f8f9fa; padding: 12px; border-radius: 4px;
                                 font-size: 13px; color: #d93025; word-break: break-all; font-family: monospace;'>
                        http://localhost:8080/?state=ABC123&code=4/0AeanS0ZWh7v-1234567890abcdefg&scope=https://www.googleapis.com/auth/gmail...
                    </code>
                </div>

                <ol style='margin: 15px 0 0 0; padding-left: 20px; line-height: 2; color: #202124;'>
                    <li style='margin-bottom: 8px;'>
                        <b>Click in the address bar</b> (the URL field at the top of your browser)
                    </li>
                    <li style='margin-bottom: 8px;'>
                        <b>Select all the text</b> (Ctrl+A on Windows/Linux, Cmd+A on Mac)
                    </li>
                    <li style='margin-bottom: 8px;'>
                        <b>Copy it</b> (Ctrl+C on Windows/Linux, Cmd+C on Mac)
                    </li>
                    <li style='margin-bottom: 8px;'>
                        <b>Paste it</b> in the box below
                    </li>
                </ol>

                <div style='background: #e3f2fd; border-radius: 4px; padding: 12px; margin: 15px 0 0 0;'>
                    <p style='margin: 0; color: #1565c0; font-size: 13px; line-height: 1.6;'>
                        💡 <b>Tip:</b> Make sure to copy the <b>ENTIRE URL</b> including everything after the "?" mark.
                        The part after "code=" is what we need!
                    </p>
                </div>
            </div>

            <p style='font-size: 14px; color: #202124; margin: 20px 0 10px 0; font-weight: 500;'>
                Step 3: Paste the complete URL here:
            </p>
            """
        )

        url_input = UIComponents.create_text_input(
            "Paste the complete URL from your browser address bar here...\nExample: http://localhost:8080/?state=...&code=...&scope=...",
            multiline=True,
            height="120px",
        )

        status = widgets.HTML(value="")

        def handle_submit(btn):
            btn.disabled = True
            url = url_input.value.strip()

            if not url:
                status.value = "<p style='color: #d93025;'>❌ Please paste the URL from your browser's address bar</p>"
                btn.disabled = False
                return

            success, message = on_submit(url)

            if success:
                status.value = f"""
                <p style='color: #34a853; font-size: 16px; font-weight: 500;'>✅ {message}</p>
                <p style='color: #5f6368; font-size: 13px; margin-top: 8px;'>
                    Your credentials have been saved. Proceeding to test APIs...
                </p>
                """
            else:
                status.value = f"""
                <p style='color: #d93025; font-weight: 500;'>❌ {message}</p>
                <p style='color: #5f6368; font-size: 13px; margin-top: 8px;'>
                    Please try again and make sure you copy the <b>complete URL</b> from your browser.
                </p>
                """
                btn.disabled = False

        continue_btn = UIComponents.create_button(
            "✅ Complete Authentication", handle_submit
        )

        card = UIComponents.create_card(
            "🔐 Google Workspace Authentication",
            [instructions, url_input, status],
            [continue_btn],
        )
        self.container.children = [card]

    def show_testing_apis(self, apis: list[str]):
        """Show API testing in progress."""
        status_html = "<div style='margin: 10px 0;'>"
        for api_name in apis:
            status_html += f"<div style='padding: 8px 0; border-bottom: 1px solid #e0e0e0;'><span>⏳ {api_name.title()} API</span> <span style='color: #5f6368;'>Testing...</span></div>"
        status_html += "</div>"

        status_widget = widgets.HTML(value=status_html)
        message, progress = UIComponents.create_progress(
            "Testing APIs with OAuth credentials...", 40
        )

        card = UIComponents.create_card(
            "🧪 Testing Workspace APIs", [message, progress, status_widget]
        )
        self.container.children = [card]

    def update_test_results(self, results: dict[str, str]):
        """
        Update API test results.

        Args:
            results: Dict mapping api_name to status ('working' or 'error')
        """
        status_html = "<div style='margin: 10px 0;'>"

        for api_name, status in results.items():
            if status == "working":
                icon = "✅"
                text = "Working ✓"
                color = "#34a853"
            else:
                icon = "❌"
                text = "Failed"
                color = "#d93025"

            status_html += f"<div style='padding: 8px 0; border-bottom: 1px solid #e0e0e0;'><span>{icon} {api_name.title()} API</span> <span style='color: {color};'>{text}</span></div>"

        status_html += "</div>"

        status_widget = widgets.HTML(value=status_html)
        _, progress = UIComponents.create_progress("Testing complete!", 100)

        card = UIComponents.create_card(
            "🧪 Testing Workspace APIs", [progress, status_widget]
        )
        self.container.children = [card]

    def show_complete(self, user_name: str, project_id: str, email: str):
        """
        Show setup complete screen.

        Args:
            user_name: User's first name
            project_id: GCP project ID
            email: User email
        """
        success_html = f"""
        <div style='margin: 10px 0;'>
            <p style='color: #34a853; font-size: 18px; font-weight: 500; margin: 10px 0;'>
                🎉 All set, {user_name}!
            </p>
            <p style='color: #5f6368; font-size: 15px; margin: 15px 0;'>
                Your Google Workspace APIs are fully configured and tested!
            </p>
            <div style='background: #f1f3f4; border-radius: 6px; padding: 15px; margin: 15px 0;'>
                <p style='margin: 0 0 8px 0; color: #5f6368; font-size: 13px;'>Your project:</p>
                <code style='font-size: 14px; font-weight: 500;'>{project_id}</code>
            </div>
            <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 15px 0;'>
                <div style='text-align: center; padding: 15px; background: #e8f5e9; border-radius: 6px;'>
                    <div style='font-size: 24px;'>✅</div>
                    <div style='font-size: 12px; color: #5f6368; margin-top: 5px;'>Gmail API</div>
                </div>
                <div style='text-align: center; padding: 15px; background: #e8f5e9; border-radius: 6px;'>
                    <div style='font-size: 24px;'>✅</div>
                    <div style='font-size: 12px; color: #5f6368; margin-top: 5px;'>Drive API</div>
                </div>
                <div style='text-align: center; padding: 15px; background: #e8f5e9; border-radius: 6px;'>
                    <div style='font-size: 24px;'>✅</div>
                    <div style='font-size: 12px; color: #5f6368; margin-top: 5px;'>Sheets API</div>
                </div>
                <div style='text-align: center; padding: 15px; background: #e8f5e9; border-radius: 6px;'>
                    <div style='font-size: 24px;'>✅</div>
                    <div style='font-size: 12px; color: #5f6368; margin-top: 5px;'>Forms API</div>
                </div>
            </div>
            <div style='background: #e8f5e9; border-left: 4px solid #34a853; padding: 15px; border-radius: 4px; margin: 20px 0;'>
                <p style='margin: 0 0 10px 0; font-weight: 500; color: #1e7e34;'>💾 Credentials Saved</p>
                <p style='margin: 0; font-size: 13px; color: #1e7e34; line-height: 1.6;'>
                    Your OAuth credentials are saved.<br><br>
                    Next time you run this setup, we'll automatically load your saved credentials!
                </p>
            </div>
        </div>
        """

        success_widget = widgets.HTML(value=success_html)

        card = UIComponents.create_card("✨ Setup Complete!", [success_widget])
        self.container.children = [card]

    def show_error(self, title: str, message: str):
        """Show error screen."""
        error_msg = widgets.HTML(value=f"<p style='color: #d93025;'>❌ {message}</p>")
        card = UIComponents.create_card(title, [error_msg])
        self.container.children = [card]
