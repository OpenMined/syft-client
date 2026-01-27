from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional


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
