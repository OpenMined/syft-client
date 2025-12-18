"""
Gmail OAuth2 authentication for notifications.
"""

import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

try:
    from .base import AuthProvider
except ImportError:
    from notifications_base import AuthProvider

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def is_colab() -> bool:
    """Check if running in Google Colab."""
    import importlib.util

    return importlib.util.find_spec("google.colab") is not None


def is_headless() -> bool:
    """Check if running in a headless environment (no display)."""
    import os

    # No DISPLAY means no GUI
    if os.environ.get("DISPLAY") is None and sys.platform != "darwin":
        return True
    # Check if we're in a notebook but not Colab (e.g., Jupyter on server)
    try:
        from IPython import get_ipython

        if get_ipython() is not None:
            # Running in IPython/Jupyter - check if we have a display
            if os.environ.get("DISPLAY") is None:
                return True
    except ImportError:
        pass
    return False


class GmailAuth(AuthProvider):
    def setup_auth(self, credentials_path: Path) -> Credentials:
        credentials_path = Path(credentials_path).expanduser()

        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)

        # Use manual flow in Colab or headless environments
        if is_colab() or is_headless():
            creds = self._run_manual_flow(flow)
        else:
            try:
                creds = flow.run_local_server(port=0)
            except Exception as e:
                # Fallback to manual flow if local server fails
                print(f"Local server failed ({e}), using manual flow...")
                creds = self._run_manual_flow(flow)

        return creds

    def _run_manual_flow(self, flow: InstalledAppFlow) -> Credentials:
        """
        Run OAuth flow manually - prints URL, user visits and pastes code.
        Works in Colab and headless environments.
        """
        # Set redirect URI to localhost for manual code extraction
        # User will be redirected to localhost (which won't load) but can copy code from URL
        flow.redirect_uri = "http://localhost:1/"

        # Generate authorization URL
        auth_url, _ = flow.authorization_url(
            prompt="consent",
            access_type="offline",  # Get refresh token
        )

        print("\n" + "=" * 60)
        print("Gmail OAuth Authorization Required")
        print("=" * 60)
        print("\n1. Click this link to authorize Gmail access:\n")
        print(f"   {auth_url}\n")
        print("2. Sign in with your Google account")
        print("3. Click 'Allow' to grant Gmail send permission")
        print("4. You'll be redirected to a page that won't load - that's OK!")
        print("5. Copy the 'code' parameter from the URL bar")
        print("   (It looks like: http://localhost:1/?code=4/0XXXXX...&scope=...)")
        print("   Just copy the part after 'code=' and before '&scope'\n")

        # Get code from user
        code = input("Enter authorization code: ").strip()

        # Clean up code if user copied extra stuff
        if "code=" in code:
            # User pasted full URL, extract code
            import re

            match = re.search(r"code=([^&]+)", code)
            if match:
                code = match.group(1)

        # URL decode the code (it may contain %2F etc)
        from urllib.parse import unquote

        code = unquote(code)

        # Exchange code for credentials
        flow.fetch_token(code=code)

        print("\n✅ Gmail authorization successful!\n")

        return flow.credentials

    def load_credentials(self, token_path: Path) -> Credentials:
        token_path = Path(token_path).expanduser()

        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

            with open(token_path, "w") as f:
                f.write(creds.to_json())

        return creds
