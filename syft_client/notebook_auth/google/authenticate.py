from typing import Optional
from google.oauth2.credentials import Credentials
from syft_client.notebook_auth.google.authenticator import GoogleWorkspaceAuth


def authenticate(
    email: str,
    scopes: Optional[list[str]] = None,
    force_new: bool = False,
    verbose: bool = True,
) -> Credentials:
    """
    Authenticate with Google Workspace and enable all APIs.

    This is the ONE-LINE authentication function that handles everything:
    - Environment detection (Colab vs Jupyter)
    - Credential caching and reuse
    - Complete OAuth setup if needed
    - Enabling all 4 Workspace APIs
    - Testing all APIs
    - Saving credentials for future use

    Args:
        email: Your Google Workspace email address
        scopes: List of scope names to request (default: ['gmail', 'drive', 'sheets', 'forms'])
        force_new: Force new setup even if cached credentials exist (default: False)
        verbose: Show progress messages (default: True)

    Returns:
        Google OAuth2 Credentials object ready to use with Google API clients

    Raises:
        RuntimeError: If authentication fails at any step

    Examples:
        Basic usage (enables all 4 APIs):
        >>> credentials = authenticate(email="user@example.com")

        Force new setup:
        >>> credentials = authenticate(email="user@example.com", force_new=True)

        Custom scopes:
        >>> credentials = authenticate(
        ...     email="user@example.com",
        ...     scopes=["gmail", "drive"]  # Only Gmail and Drive
        ... )

        Use with Google APIs:
        >>> from googleapiclient.discovery import build
        >>>
        >>> # Gmail
        >>> gmail = build('gmail', 'v1', credentials=credentials)
        >>> profile = gmail.users().getProfile(userId='me').execute()
        >>>
        >>> # Drive
        >>> drive = build('drive', 'v3', credentials=credentials)
        >>> files = drive.files().list(pageSize=10).execute()
        >>>
        >>> # Sheets
        >>> sheets = build('sheets', 'v4', credentials=credentials)
        >>> spreadsheet = sheets.spreadsheets().create(
        ...     body={'properties': {'title': 'My Sheet'}}
        ... ).execute()
        >>>
        >>> # Forms
        >>> forms = build('forms', 'v1', credentials=credentials)
        >>> form = forms.forms().create(
        ...     body={'info': {'title': 'My Form'}}
        ... ).execute()
    """
    auth = GoogleWorkspaceAuth(email=email, scopes=scopes, verbose=verbose)
    return auth.run(force_new=force_new)
