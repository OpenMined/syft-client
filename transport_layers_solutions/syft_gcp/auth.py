"""
OAuth authentication and token management
"""

from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .constants import SCOPES
from . import storage


def authenticate(credentials_path: str = "credentials.json") -> Credentials:
    """
    Authenticate and return credentials

    Args:
        credentials_path: Path to OAuth credentials.json file

    Returns:
        Authorized credentials

    Raises:
        FileNotFoundError: If credentials.json not found
    """
    creds = None

    # Load existing token if available
    token_dict = storage.load_token()
    if token_dict:
        creds = Credentials.from_authorized_user_info(token_dict, SCOPES)

    # Refresh expired token or run OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh expired token
            print("🔄 Refreshing expired token...")
            creds.refresh(Request())
        else:
            # Run OAuth flow
            if not Path(credentials_path).exists():
                raise FileNotFoundError(
                    f"credentials.json not found at: {credentials_path}\n\n"
                    f"Download OAuth credentials:\n"
                    f"1. Go to: https://console.cloud.google.com/apis/credentials\n"
                    f"2. Create Credentials → OAuth client ID → Desktop app\n"
                    f"3. Download JSON as 'credentials.json'\n"
                )

            print("🔐 Running OAuth flow...")
            print("🌐 Opening browser for authentication...")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for next time
        import json

        token_dict = json.loads(creds.to_json())
        method = storage.save_token(token_dict)
        if method == "keyring":
            print("✅ Token saved securely in OS keyring")
        else:
            print(
                f"✅ Token saved to {storage.get_config_dir()}/{storage.TOKEN_FILE_NAME}"
            )

    return creds
