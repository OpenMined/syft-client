from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any
import time


class NotificationSender(ABC):
    """Abstract base for notification senders (Gmail, Slack, Discord, etc.)"""

    @abstractmethod
    def send_notification(self, to: str, subject: str, body: str) -> bool:
        """
        Send a notification.

        Args:
            to: Recipient identifier (email, slack channel, etc.)
            subject: Notification subject/title
            body: Notification content

        Returns:
            True if sent successfully, False otherwise
        """
        pass


class AuthProvider(ABC):
    """Abstract base for authentication providers (OAuth, API keys, etc.)"""

    @abstractmethod
    def setup_auth(self, credentials_path: Path) -> Any:
        """
        One-time authentication setup.

        Args:
            credentials_path: Path to credentials file

        Returns:
            Credentials object
        """
        pass

    @abstractmethod
    def load_credentials(self, token_path: Path) -> Any:
        """
        Load and refresh credentials.

        Args:
            token_path: Path to saved credentials/token

        Returns:
            Valid credentials object
        """
        pass


class StateManager(ABC):
    """Abstract base for state tracking (JSON, SQLite, Redis, etc.)"""

    @abstractmethod
    def was_notified(self, entity_id: str, event_type: str) -> bool:
        """
        Check if entity was notified for specific event type.

        Args:
            entity_id: Unique identifier (job name, peer id, etc.)
            event_type: Event type ("new", "approved", "executed", etc.)

        Returns:
            True if already notified, False otherwise
        """
        pass

    @abstractmethod
    def mark_notified(self, entity_id: str, event_type: str):
        """
        Mark entity as notified for specific event type.

        Args:
            entity_id: Unique identifier
            event_type: Event type
        """
        pass


class Monitor(ABC):
    """Abstract base for monitors (JobMonitor, PeerMonitor, etc.)"""

    def __init__(
        self, sender: NotificationSender, state: StateManager, config: Dict[str, Any]
    ):
        """
        Initialize monitor with dependencies.

        Args:
            sender: Notification sender implementation
            state: State manager implementation
            config: Configuration dictionary
        """
        self.sender = sender
        self.state = state
        self.config = config

    @abstractmethod
    def _check_all_entities(self):
        """
        Check all entities for events (implemented by subclasses).

        This is where monitor-specific logic goes (e.g., checking jobs, peers).
        """
        pass

    def check(self, interval: Optional[int] = None, duration: Optional[int] = None):
        """
        Run monitoring checks.

        Args:
            interval: If None, runs once. If set, runs continuously every N seconds.
            duration: How long to run (seconds). None = infinite until Ctrl+C.

        Examples:
            monitor.check()                         # Single check
            monitor.check(interval=10)              # Every 10s forever
            monitor.check(interval=10, duration=3600)  # Run for 1 hour
        """
        if interval is None:
            self._check_all_entities()
            return

        start_time = time.time()

        print(f"🔔 {self.__class__.__name__} started (interval: {interval}s)")
        if duration:
            print(f"   Will run for {duration}s ({duration / 60:.1f} minutes)")
        else:
            print("   Running until stopped (Ctrl+C)")

        try:
            while True:
                self._check_all_entities()

                if duration is not None:
                    elapsed = time.time() - start_time
                    if elapsed >= duration:
                        print(f"✅ Monitoring completed ({elapsed:.0f}s)")
                        break

                time.sleep(interval)

        except KeyboardInterrupt:
            elapsed = time.time() - start_time
            print(f"\n⏹️  Monitoring stopped ({elapsed:.0f}s elapsed)")
