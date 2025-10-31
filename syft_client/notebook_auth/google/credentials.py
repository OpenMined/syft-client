"""Credential handling - validation, refresh, and conversion."""

from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


class CredentialHandler:
    """Handles credential validation and conversion - pure functions, no UI."""

    @staticmethod
    def validate(credentials: Credentials) -> bool:
        """
        Test if credentials work by making a simple API call.

        Args:
            credentials: Google OAuth2 credentials

        Returns:
            True if credentials are valid and working
        """
        if not credentials:
            return False

        try:
            from googleapiclient.discovery import build

            # Try a simple API call to validate
            service = build("gmail", "v1", credentials=credentials)
            service.users().getProfile(userId="me").execute()
            return True
        except Exception:
            return False

    @staticmethod
    def to_dict(credentials: Credentials) -> dict:
        """
        Convert credentials to JSON-serializable dict.

        Args:
            credentials: Google OAuth2 credentials

        Returns:
            Dict representation of credentials
        """
        return {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        }

    @staticmethod
    def from_dict(data: dict, scopes: list[str]) -> Credentials:
        """
        Convert dict to Credentials object.

        Args:
            data: Dict representation of credentials
            scopes: List of OAuth scopes

        Returns:
            Google OAuth2 Credentials object
        """
        return Credentials.from_authorized_user_info(data, scopes)

    @staticmethod
    def is_expired(credentials: Credentials) -> bool:
        """
        Check if credentials are expired.

        Args:
            credentials: Google OAuth2 credentials

        Returns:
            True if expired
        """
        if not credentials or not credentials.expiry:
            return False
        return credentials.expired

    @staticmethod
    def refresh(credentials: Credentials) -> Credentials:
        """
        Refresh expired credentials.

        Args:
            credentials: Google OAuth2 credentials to refresh

        Returns:
            Refreshed credentials

        Raises:
            Exception if refresh fails
        """
        if not credentials.refresh_token:
            raise ValueError("No refresh token available")

        credentials.refresh(Request())
        return credentials

    @staticmethod
    def needs_refresh(credentials: Credentials) -> bool:
        """
        Check if credentials need to be refreshed.

        Args:
            credentials: Google OAuth2 credentials

        Returns:
            True if credentials exist but are expired or will expire soon
        """
        if not credentials:
            return False

        # If expired, definitely needs refresh
        if CredentialHandler.is_expired(credentials):
            return True

        # If expiry is soon (within 5 minutes), proactively refresh
        if credentials.expiry:
            time_until_expiry = credentials.expiry - datetime.utcnow()
            return time_until_expiry.total_seconds() < 300  # 5 minutes

        return False
