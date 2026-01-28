from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


def is_colab() -> bool:
    """Check if running in Google Colab."""
    try:
        import google.colab  # noqa: F401

        return True
    except ImportError:
        return False


def create_drive_service(token_path: Optional[Path] = None):
    """Create a Google Drive service, handling both Colab and local environments.

    Args:
        token_path: Path to token file. Required for non-Colab environments.
                   Ignored in Colab (uses native auth).

    Returns:
        Google Drive service object, or None if auth fails.
    """
    from googleapiclient.discovery import build

    if is_colab():
        from google.colab import auth as colab_auth
        import google.auth

        colab_auth.authenticate_user()
        creds, _ = google.auth.default()
        return build("drive", "v3", credentials=creds)
    else:
        if not token_path or not Path(token_path).exists():
            return None

        from google.oauth2.credentials import Credentials as GoogleCredentials

        credentials = GoogleCredentials.from_authorized_user_file(
            str(token_path), DRIVE_SCOPES
        )
        return build("drive", "v3", credentials=credentials)


class NotificationSender(ABC):
    @abstractmethod
    def send_notification(self, to: str, subject: str, body: str) -> bool:
        pass


class AuthProvider(ABC):
    @abstractmethod
    def setup_auth(self, credentials_path: Path) -> Any:
        pass

    @abstractmethod
    def load_credentials(self, token_path: Path) -> Any:
        pass


class StateManager(ABC):
    @abstractmethod
    def was_notified(self, entity_id: str, event_type: str) -> bool:
        pass

    @abstractmethod
    def mark_notified(self, entity_id: str, event_type: str) -> None:
        pass

    @abstractmethod
    def get_data(self, key: str, default: Optional[Any] = None) -> Any:
        pass

    @abstractmethod
    def set_data(self, key: str, value: Any) -> None:
        pass
