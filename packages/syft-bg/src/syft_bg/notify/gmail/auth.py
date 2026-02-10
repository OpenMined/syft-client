"""Gmail OAuth authentication."""

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def run_oauth_flow_manual(flow: InstalledAppFlow) -> Credentials:
    """Run OAuth flow manually without browser auto-launch.

    This works in headless environments like Colab, SSH, and containers.
    """
    # Generate authorization URL
    auth_url, _ = flow.authorization_url(prompt="consent")

    print()
    print("Please visit this URL to authorize the application:")
    print()
    print(f"    {auth_url}")
    print()

    # Get the authorization code from user
    code = input("Enter the authorization code: ").strip()

    # Exchange code for credentials
    flow.fetch_token(code=code)
    return flow.credentials


class GmailAuth:
    """Handles Gmail OAuth authentication."""

    def setup_auth(self, credentials_path: Path) -> Credentials:
        """Run OAuth flow to get Gmail credentials."""
        credentials_path = Path(credentials_path).expanduser()
        flow = InstalledAppFlow.from_client_secrets_file(
            str(credentials_path), GMAIL_SCOPES
        )
        return run_oauth_flow_manual(flow)

    def load_credentials(self, token_path: Path) -> Credentials:
        """Load credentials from token file, refreshing if needed."""
        token_path = Path(token_path).expanduser()
        creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "w") as f:
                f.write(creds.to_json())

        return creds
