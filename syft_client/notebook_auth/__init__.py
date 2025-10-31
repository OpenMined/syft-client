"""
Standalone Google Workspace authentication for notebooks.

This is a complete, self-contained authentication system for setting up
Google Workspace APIs (Gmail, Drive, Sheets, Forms) in Colab and Jupyter notebooks.

Features:
- One-line authentication: authenticate(email="user@example.com")
- Automatic environment detection (Colab vs Jupyter)
- Persistent credential storage (Google Drive for Colab, local for Jupyter)
- Interactive setup wizard with step-by-step guidance
- Automatic API enabling and testing
- Complete OAuth 2.0 flow with manual redirect handling

Usage:
    >>> from syft_client.notebook_auth import authenticate
    >>>
    >>> # One-liner that does everything!
    >>> credentials = authenticate(email="user@example.com")
    >>>
    >>> # Use with Google API clients
    >>> from googleapiclient.discovery import build
    >>> gmail = build('gmail', 'v1', credentials=credentials)
    >>> drive = build('drive', 'v3', credentials=credentials)
    >>> sheets = build('sheets', 'v4', credentials=credentials)
    >>> forms = build('forms', 'v1', credentials=credentials)

What it does:
1. Mounts Google Drive (Colab only) for credential persistence
2. Checks for cached credentials and reuses them if valid
3. If no cache, guides through complete setup:
   - GCP project creation or selection
   - OAuth consent screen configuration
   - OAuth client ID creation
   - OAuth authentication flow
   - Enables all 4 Workspace APIs (Gmail, Drive, Sheets, Forms)
   - Tests all APIs to confirm they work
4. Saves credentials for future use
5. Returns ready-to-use OAuth2 credentials

The entire flow is interactive with clear UI guidance at each step.
"""

from typing import Optional

from google.oauth2.credentials import Credentials

from .google_workspace import GoogleWorkspaceAuth


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


# Export the main function and types
__all__ = [
    "authenticate",
    "GoogleWorkspaceAuth",  # For advanced users who want more control
    "Credentials",  # Type hint convenience
]
