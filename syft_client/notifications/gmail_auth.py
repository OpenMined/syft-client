"""
Gmail OAuth2 authentication for notifications.
"""

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def setup_gmail_oauth(token_path: Path) -> Credentials:
    """
    Initiate OAuth2 flow and save credentials.

    Opens browser for user to grant Gmail send permissions.
    Saves refresh token to token_path for future use.

    Returns:
        Credentials object with access token
    """
    token_path = Path(token_path).expanduser()
    token_path.parent.mkdir(parents=True, exist_ok=True)

    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)

    with open(token_path, "w") as f:
        f.write(creds.to_json())

    token_path.chmod(0o600)

    return creds


def load_gmail_credentials(token_path: Path) -> Credentials:
    """
    Load saved credentials and refresh if expired.

    Args:
        token_path: Path to saved credentials JSON

    Returns:
        Valid Credentials object
    """
    token_path = Path(token_path).expanduser()

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return creds
