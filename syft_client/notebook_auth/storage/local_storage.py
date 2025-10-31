"""Store credentials locally for Jupyter notebooks."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from google.oauth2.credentials import Credentials


class LocalStorage:
    """
    Stores OAuth credentials and configuration in local filesystem.

    Structure:
    ~/.syft_credentials/
        ├── {email}/
        │   ├── client_secret.json      # OAuth client configuration
        │   ├── credentials.json         # User OAuth credentials
        │   └── project_info.json        # GCP project metadata
    """

    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize local storage.

        Args:
            base_path: Base path for credentials (defaults to ~/.syft_credentials)
        """
        if base_path:
            self.base_path = Path(base_path)
        else:
            self.base_path = Path.home() / ".syft_credentials"

    def _ensure_email_dir(self, email: str) -> Path:
        """
        Ensure email-specific directory exists.

        Args:
            email: User email

        Returns:
            Path to email directory
        """
        email_dir = self.base_path / self._sanitize_email(email)
        email_dir.mkdir(parents=True, exist_ok=True)
        return email_dir

    @staticmethod
    def _sanitize_email(email: str) -> str:
        """Sanitize email for use in directory names."""
        return email.replace("@", "_at_").replace(".", "_")

    def save_client_secret(self, email: str, client_secret: dict):
        """
        Save OAuth client configuration.

        Args:
            email: User email
            client_secret: OAuth client secret dict
        """
        email_dir = self._ensure_email_dir(email)
        path = email_dir / "client_secret.json"

        with open(path, "w") as f:
            json.dump(client_secret, f, indent=2)

        # Secure permissions
        path.chmod(0o600)

    def load_client_secret(self, email: str) -> Optional[dict]:
        """
        Load OAuth client configuration.

        Args:
            email: User email

        Returns:
            OAuth client secret dict or None if not found
        """
        email_dir = self.base_path / self._sanitize_email(email)
        path = email_dir / "client_secret.json"

        if not path.exists():
            return None

        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    def save_credentials(self, email: str, credentials: Credentials):
        """
        Save user OAuth credentials.

        Args:
            email: User email
            credentials: Google OAuth2 credentials
        """
        from ..core.credentials import CredentialHandler

        email_dir = self._ensure_email_dir(email)
        path = email_dir / "credentials.json"

        creds_dict = CredentialHandler.to_dict(credentials)

        with open(path, "w") as f:
            json.dump(creds_dict, f, indent=2)

        # Secure permissions
        path.chmod(0o600)

    def load_credentials(self, email: str, scopes: list[str]) -> Optional[Credentials]:
        """
        Load user OAuth credentials.

        Args:
            email: User email
            scopes: OAuth scopes for credential validation

        Returns:
            Google OAuth2 credentials or None if not found
        """
        from ..core.credentials import CredentialHandler

        email_dir = self.base_path / self._sanitize_email(email)
        path = email_dir / "credentials.json"

        if not path.exists():
            return None

        try:
            with open(path, "r") as f:
                creds_dict = json.load(f)

            return CredentialHandler.from_dict(creds_dict, scopes)
        except Exception:
            return None

    def save_project_info(self, email: str, project_info: dict):
        """
        Save GCP project metadata.

        Args:
            email: User email
            project_info: Project information dict
        """
        email_dir = self._ensure_email_dir(email)
        path = email_dir / "project_info.json"

        # Add metadata
        project_info["saved_at"] = datetime.now().isoformat()
        project_info["email"] = email

        with open(path, "w") as f:
            json.dump(project_info, f, indent=2)

        # Secure permissions
        path.chmod(0o600)

    def load_project_info(self, email: str) -> Optional[dict]:
        """
        Load GCP project metadata.

        Args:
            email: User email

        Returns:
            Project info dict or None if not found
        """
        email_dir = self.base_path / self._sanitize_email(email)
        path = email_dir / "project_info.json"

        if not path.exists():
            return None

        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    def has_saved_setup(self, email: str) -> bool:
        """
        Check if user has complete saved setup.

        Args:
            email: User email

        Returns:
            True if both client_secret and project_info exist
        """
        email_dir = self.base_path / self._sanitize_email(email)

        client_secret_exists = (email_dir / "client_secret.json").exists()
        project_info_exists = (email_dir / "project_info.json").exists()

        return client_secret_exists and project_info_exists

    def clear(self, email: str):
        """
        Clear all saved data for an email.

        Args:
            email: User email
        """
        import shutil

        email_dir = self.base_path / self._sanitize_email(email)

        if email_dir.exists():
            shutil.rmtree(email_dir)
