"""
Peer Monitor: Detects and notifies about peer events in SyftBox.
"""

from typing import Dict, Any, TYPE_CHECKING

try:
    from .base import Monitor, NotificationSender, StateManager
except ImportError:
    from notifications_base import Monitor, NotificationSender, StateManager

if TYPE_CHECKING:
    from syft_client.sync.syftbox_manager import SyftboxManager


class PeerMonitor(Monitor):
    """Monitor peers in SyftBox for notification events"""

    def __init__(
        self,
        manager: "SyftboxManager",
        sender: NotificationSender,
        state: StateManager,
        config: Dict[str, Any],
    ):
        """
        Initialize Peer Monitor.

        Args:
            manager: SyftboxManager instance (for loading peers)
            sender: Notification sender implementation
            state: State manager implementation
            config: Configuration dictionary with notification toggles
        """
        super().__init__(sender, state, config)
        self.manager = manager
        self.do_email = manager.email
        self.is_do = manager.is_do

        if not self.is_do:
            raise ValueError(
                "PeerMonitor should only run on Data Owner (DO) side. "
                "DS perspective monitoring is not supported."
            )

    def _check_all_entities(self):
        """Check peers for notification events"""
        # Load current peers from Drive API
        self.manager.load_peers()
        current_peer_emails = set(p.email for p in self.manager.peers)

        # Get previous peers from state
        previous_peer_emails = set(self.state.get_data("peer_snapshot", []))

        # Detect new peers
        new_peer_emails = current_peer_emails - previous_peer_emails

        # Handle new peers
        for peer_email in new_peer_emails:
            self._handle_new_peer(peer_email)

        # Check for mutual peering (peer request granted)
        self._check_mutual_peering_grants(current_peer_emails, previous_peer_emails)

        # Save current peer snapshot
        self.state.set_data("peer_snapshot", list(current_peer_emails))

    def _handle_new_peer(self, ds_email: str):
        """
        Handle new peer notification.

        When DS adds DO as peer, DO's monitor detects it and notifies both parties.

        Args:
            ds_email: Data Scientist email who added DO
        """
        # Notify DO about new peer request
        self._notify_new_peer_to_do(ds_email)

        # Notify DS that they successfully added DO
        self._notify_new_peer_to_ds(ds_email)

    def _notify_new_peer_to_do(self, ds_email: str):
        """
        Notify DO about new peer request from DS.

        Args:
            ds_email: Data Scientist email
        """
        if not self.config.get("notify_on_new_peer", True):
            return

        state_key = f"peer_new_{ds_email}_to_do"
        if self.state.was_notified(state_key, "new_peer_request"):
            return

        if hasattr(self.sender, "notify_new_peer_request_to_do"):
            success = self.sender.notify_new_peer_request_to_do(self.do_email, ds_email)
        else:
            success = self.sender.send_notification(
                self.do_email,
                f"New Peer Request from {ds_email}",
                f"You have a new peer request from {ds_email}",
            )

        if success:
            self.state.mark_notified(state_key, "new_peer_request")

    def _notify_new_peer_to_ds(self, ds_email: str):
        """
        Notify DS that they successfully added DO as peer.

        Args:
            ds_email: Data Scientist email
        """
        if not self.config.get("notify_on_new_peer", True):
            return

        state_key = f"peer_new_{ds_email}_to_ds"
        if self.state.was_notified(state_key, "peer_added_confirmation"):
            return

        if hasattr(self.sender, "notify_peer_added_to_ds"):
            success = self.sender.notify_peer_added_to_ds(ds_email, self.do_email)
        else:
            success = self.sender.send_notification(
                ds_email,
                f"Peer Added: {self.do_email}",
                f"You successfully added {self.do_email} as a peer",
            )

        if success:
            self.state.mark_notified(state_key, "peer_added_confirmation")

    def _check_mutual_peering_grants(self, current_peers: set, previous_peers: set):
        """
        Check if DO granted any peer requests by adding DS back.

        When DO adds DS as peer, it means DO "granted" DS's peer request
        (establishing mutual peering).

        Args:
            current_peers: Current set of peer emails
            previous_peers: Previous set of peer emails
        """
        new_peers = current_peers - previous_peers

        for ds_email in new_peers:
            self._notify_peer_granted(ds_email)

    def _notify_peer_granted(self, ds_email: str):
        """
        Notify DS that DO accepted their peer request.

        Args:
            ds_email: Data Scientist email
        """
        if not self.config.get("notify_on_peer_granted", True):
            return

        state_key = f"peer_granted_{ds_email}"
        if self.state.was_notified(state_key, "peer_granted"):
            return

        if hasattr(self.sender, "notify_peer_request_granted"):
            success = self.sender.notify_peer_request_granted(ds_email, self.do_email)
        else:
            success = self.sender.send_notification(
                ds_email,
                f"Peer Request Accepted: {self.do_email}",
                f"{self.do_email} has accepted your peer request",
            )

        if success:
            self.state.mark_notified(state_key, "peer_granted")

    @classmethod
    def from_manager_and_config(cls, manager: "SyftboxManager", config_path: str):
        """
        Factory method: create monitor from SyftboxManager + config file.

        Args:
            manager: SyftboxManager instance
            config_path: Path to configuration YAML file

        Returns:
            Configured PeerMonitor instance

        Example:
            >>> manager = SyftboxManager(...)
            >>> monitor = PeerMonitor.from_manager_and_config(
            ...     manager, "notification_config.yaml"
            ... )
            >>> monitor.check(interval=10)
        """
        import yaml
        from pathlib import Path

        # Default paths for package-managed files
        DEFAULT_NOTIFICATION_DIR = Path.home() / ".syft-notifications"
        DEFAULT_TOKEN_FILE = DEFAULT_NOTIFICATION_DIR / "gmail_token.json"
        DEFAULT_STATE_FILE = DEFAULT_NOTIFICATION_DIR / "state.json"

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # token_file and state_file are optional, use defaults if not provided
        token_path = (
            Path(config["token_file"]).expanduser()
            if "token_file" in config
            else DEFAULT_TOKEN_FILE
        )
        state_path = (
            Path(config["state_file"]).expanduser()
            if "state_file" in config
            else DEFAULT_STATE_FILE
        )

        from .gmail_auth import GmailAuth

        auth = GmailAuth()
        credentials = auth.load_credentials(token_path)

        from .gmail_sender import GmailSender

        sender = GmailSender(credentials)

        from .json_state_manager import JsonStateManager

        state = JsonStateManager(state_path)

        return cls(
            manager=manager,
            sender=sender,
            state=state,
            config=config,
        )
