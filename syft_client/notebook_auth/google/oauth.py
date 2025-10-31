"""OAuth 2.0 flow logic - pure functions with no UI dependencies."""

import os
from typing import Optional
from urllib.parse import parse_qs, urlparse

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Workspace API scopes
DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/forms.responses.readonly",
]


class OAuthFlow:
    """Handles OAuth 2.0 flow for Google - pure functions, no UI."""

    @staticmethod
    def get_scopes(scope_names: Optional[list[str]] = None) -> list[str]:
        """
        Convert scope names to full scope URLs.

        Args:
            scope_names: List of scope names like ["gmail", "drive"]

        Returns:
            List of full scope URLs
        """
        if not scope_names:
            return DEFAULT_SCOPES

        scope_map = {
            "gmail": [
                "https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.modify",
            ],
            "drive": ["https://www.googleapis.com/auth/drive"],
            "sheets": ["https://www.googleapis.com/auth/spreadsheets"],
            "forms": [
                "https://www.googleapis.com/auth/forms.body",
                "https://www.googleapis.com/auth/forms.responses.readonly",
            ],
        }

        scopes = []
        for name in scope_names:
            if name in scope_map:
                scopes.extend(scope_map[name])
        return scopes or DEFAULT_SCOPES

    @staticmethod
    def create_flow(
        client_secret: dict,
        scopes: list[str],
        redirect_uri: str = "http://localhost:8080",
    ) -> InstalledAppFlow:
        """
        Create OAuth flow from client secret.

        Args:
            client_secret: OAuth client configuration dict
            scopes: List of OAuth scope URLs
            redirect_uri: OAuth redirect URI

        Returns:
            Configured InstalledAppFlow
        """
        # Allow HTTP for localhost (safe for OAuth redirect)
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

        flow = InstalledAppFlow.from_client_config(
            client_secret, scopes, redirect_uri=redirect_uri
        )
        return flow

    @staticmethod
    def get_auth_url(flow: InstalledAppFlow) -> tuple[str, str]:
        """
        Get authorization URL and state.

        Args:
            flow: Configured OAuth flow

        Returns:
            Tuple of (authorization_url, state)
        """
        auth_url, state = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )
        return auth_url, state

    @staticmethod
    def exchange_code(
        flow: InstalledAppFlow, authorization_response: str
    ) -> Credentials:
        """
        Exchange authorization code for credentials.

        Args:
            flow: Configured OAuth flow
            authorization_response: Full redirect URL with code

        Returns:
            OAuth2 Credentials

        Raises:
            ValueError: If URL is invalid or missing code
        """
        # Parse the URL to validate it
        if not authorization_response.startswith("http://localhost"):
            raise ValueError("Invalid redirect URL - must start with http://localhost")

        if "code=" not in authorization_response:
            raise ValueError("No authorization code found in URL")

        # Disable scope validation - Google may grant additional permissions
        os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

        # Extract the code manually
        parsed = urlparse(authorization_response)
        params = parse_qs(parsed.query)

        if "code" not in params:
            raise ValueError("No code parameter found in URL")

        auth_code = params["code"][0]

        # Exchange code for tokens
        flow.fetch_token(code=auth_code)
        return flow.credentials

    @staticmethod
    def refresh(credentials: Credentials) -> Credentials:
        """
        Refresh expired credentials.

        Args:
            credentials: Expired credentials with refresh token

        Returns:
            Refreshed credentials

        Raises:
            Exception if refresh fails
        """
        from google.auth.transport.requests import Request

        if not credentials.refresh_token:
            raise ValueError("No refresh token available")

        credentials.refresh(Request())
        return credentials

    @staticmethod
    def validate_client_secret(client_secret: dict) -> bool:
        """
        Validate client secret structure.

        Args:
            client_secret: OAuth client configuration

        Returns:
            True if valid structure
        """
        # Must have either 'installed' or 'web' key
        if "installed" not in client_secret and "web" not in client_secret:
            return False

        # Get the config section
        config = client_secret.get("installed") or client_secret.get("web")

        # Check required fields
        required_fields = ["client_id", "client_secret", "auth_uri", "token_uri"]
        return all(field in config for field in required_fields)
