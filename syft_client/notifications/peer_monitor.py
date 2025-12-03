"""
Peer Monitor: Detects and notifies about peer events in SyftBox.

Uses its own Google Drive connection to avoid thread-safety issues
with the main client.
"""

from pathlib import Path
from typing import Dict, Any, Optional, TYPE_CHECKING

try:
    from .base import Monitor, NotificationSender, StateManager
except ImportError:
    from base import Monitor, NotificationSender, StateManager

if TYPE_CHECKING:
    from syft_client.sync.syftbox_manager import SyftboxManager


class PeerMonitor(Monitor):
    """
    Monitor peers in SyftBox for notification events.

    Creates its own Drive service to poll for peer changes,
    avoiding thread-safety issues with the main client.
    """

    def __init__(
        self,
        do_email: str,
        drive_token_path: Path,
        sender: NotificationSender,
        state: StateManager,
        config: Dict[str, Any],
    ):
        """
        Initialize Peer Monitor.

        Args:
            do_email: Data Owner email address
            drive_token_path: Path to Google Drive OAuth token
            sender: Notification sender implementation
            state: State manager implementation
            config: Configuration dictionary with notification toggles
        """
        super().__init__(sender, state, config)
        self.do_email = do_email
        self.drive_token_path = Path(drive_token_path)

        # Initialize Drive service on main thread to avoid threading issues
        # googleapiclient's build() is not thread-safe
        self._drive_service = self._create_drive_service()

    def _create_drive_service(self):
        """Create Google Drive service (must be called from main thread)."""
        from google.oauth2.credentials import Credentials as GoogleCredentials
        from googleapiclient.discovery import build

        SCOPES = ["https://www.googleapis.com/auth/drive"]

        credentials = GoogleCredentials.from_authorized_user_file(
            str(self.drive_token_path), SCOPES
        )
        return build("drive", "v3", credentials=credentials)

    def _load_peers_from_drive(self) -> set:
        """Load peer emails by querying Drive API directly."""
        GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX = "syft_outbox_inbox"
        GOOGLE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

        try:
            results = (
                self._drive_service.files()
                .list(
                    q=f"name contains '{GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX}' and trashed=false "
                    f"and mimeType = '{GOOGLE_FOLDER_MIME_TYPE}'"
                )
                .execute()
            )

            peers = set()
            inbox_folders = results.get("files", [])

            for folder in inbox_folders:
                name = folder["name"]
                # Parse: syft_outbox_inbox_<sender>_to_<recipient>
                parts = name.split("_")
                if len(parts) >= 6:
                    sender_email = parts[3]
                    recipient_email = parts[5] if len(parts) > 5 else None
                    # Only include peers where someone else sent TO us
                    if (
                        sender_email != self.do_email
                        and recipient_email == self.do_email
                    ):
                        peers.add(sender_email)

            return peers

        except Exception as e:
            # Log but don't crash on transient errors
            print(f"⚠️  PeerMonitor: Error loading peers: {e}")
            return set()

    def _check_all_entities(self):
        """Check peers for notification events."""
        # Detect new peer requests (DS added DO)
        current_peer_emails = self._load_peers_from_drive()
        previous_peer_emails = set(self.state.get_data("peer_snapshot", []))
        new_peer_emails = current_peer_emails - previous_peer_emails

        if new_peer_emails:
            print(
                f"🔍 PeerMonitor: Detected {len(new_peer_emails)} new peer request(s): {new_peer_emails}"
            )

        for peer_email in new_peer_emails:
            self._handle_new_peer(peer_email)

        self.state.set_data("peer_snapshot", list(current_peer_emails))

        # NOTE: Peer grant detection cannot be done via folder polling because:
        # - When DS adds DO, DS creates BOTH folders (DS_to_DO and DO_to_DS)
        # - DO's add_peer_as_do() is a no-op and doesn't create any folders
        # - So we can't tell from folders alone when DO accepted the request
        #
        # Peer grant notifications must be triggered manually via:
        #   monitor.notify_peer_granted(ds_email)
        # This should be called from the notebook when DO runs add_peer()

    def _handle_new_peer(self, ds_email: str):
        """
        Handle new peer notification.

        When DS adds DO as peer, DO's monitor detects it and notifies both parties.

        Args:
            ds_email: Data Scientist email who added DO
        """
        # Notify DO about new peer request
        self._notify_new_peer_to_do(ds_email)

        # Notify DS that their request was received
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

        print(
            f"📧 Notifying DO ({self.do_email}) about new peer request from {ds_email}"
        )

        if hasattr(self.sender, "notify_new_peer_request_to_do"):
            success = self.sender.notify_new_peer_request_to_do(self.do_email, ds_email)
        else:
            success = self.sender.send_email(
                to_email=self.do_email,
                subject=f"New Peer Request from {ds_email}",
                body_text=f"You have a new peer request from {ds_email}",
            )

        if success:
            self.state.mark_notified(state_key, "new_peer_request")

    def _notify_new_peer_to_ds(self, ds_email: str):
        """
        Notify DS that their peer request was received by DO.

        Args:
            ds_email: Data Scientist email
        """
        if not self.config.get("notify_on_new_peer", True):
            return

        state_key = f"peer_new_{ds_email}_to_ds"
        if self.state.was_notified(state_key, "peer_request_sent"):
            return

        print(
            f"📧 Notifying DS ({ds_email}) that peer request was received by {self.do_email}"
        )

        if hasattr(self.sender, "notify_peer_request_sent"):
            success = self.sender.notify_peer_request_sent(ds_email, self.do_email)
        else:
            success = self.sender.send_email(
                to_email=ds_email,
                subject=f"Peer Request Sent to {self.do_email}",
                body_text=f"Your peer request to {self.do_email} has been received.",
            )

        if success:
            self.state.mark_notified(state_key, "peer_request_sent")

    def notify_peer_granted(self, ds_email: str):
        """
        Notify DS that DO accepted their peer request.

        This should be called when DO runs add_peer(ds_email).

        Args:
            ds_email: Data Scientist email
        """
        if not self.config.get("notify_on_peer_granted", True):
            return

        state_key = f"peer_granted_{ds_email}"
        if self.state.was_notified(state_key, "peer_granted"):
            print(f"⏭️  Already notified DS ({ds_email}) about peer grant - skipping")
            return

        print(f"📧 Sending peer grant notification to DS ({ds_email})...")

        if hasattr(self.sender, "notify_peer_request_granted"):
            success = self.sender.notify_peer_request_granted(ds_email, self.do_email)
        else:
            success = self.sender.send_email(
                to_email=ds_email,
                subject=f"Peer Request Accepted by {self.do_email}",
                body_text=f"{self.do_email} has accepted your peer request. You now have mutual peering.",
            )

        if success:
            self.state.mark_notified(state_key, "peer_granted")
            print(f"✅ Peer grant notification sent to {ds_email}")
        else:
            print(f"❌ Failed to send peer grant notification to {ds_email}")

    @classmethod
    def from_client(
        cls,
        client: "SyftboxManager",
        gmail_token_path: Optional[str] = None,
        notifications: bool = True,
    ):
        """
        Factory method: create monitor from syft-client.

        Args:
            client: SyftboxManager from sc.login_do()
            gmail_token_path: Path to Gmail token (default: ~/.syft-notifications/gmail_token.json)
            notifications: Enable/disable notifications (default True)

        Returns:
            Configured PeerMonitor instance
        """
        if not client.is_do:
            raise ValueError("PeerMonitor should only run on Data Owner (DO) side.")

        # Get Drive token path from client's connection
        drive_token_path = cls._get_drive_token_path(client)

        # Default paths for Gmail
        DEFAULT_NOTIFICATION_DIR = Path.home() / ".syft-notifications"
        DEFAULT_GMAIL_TOKEN = DEFAULT_NOTIFICATION_DIR / "gmail_token.json"
        DEFAULT_STATE_FILE = DEFAULT_NOTIFICATION_DIR / "state.json"

        gmail_path = (
            Path(gmail_token_path).expanduser()
            if gmail_token_path
            else DEFAULT_GMAIL_TOKEN
        )

        if not gmail_path.exists():
            raise FileNotFoundError(
                f"Gmail token not found at: {gmail_path}\n\n"
                "Run OAuth setup first:\n"
                "  from syft_client.notifications import GmailAuth\n"
                "  auth = GmailAuth()\n"
                "  creds = auth.setup_auth('path/to/credentials.json')\n"
                "  # Save token to ~/.syft-notifications/gmail_token.json"
            )

        from .gmail_auth import GmailAuth
        from .gmail_sender import GmailSender
        from .json_state_manager import JsonStateManager

        auth = GmailAuth()
        credentials = auth.load_credentials(gmail_path)
        sender = GmailSender(credentials, use_html=True)
        state = JsonStateManager(DEFAULT_STATE_FILE)

        config = {
            "notify_on_new_peer": notifications,
            "notify_on_peer_granted": notifications,
        }

        return cls(
            do_email=client.email,
            drive_token_path=drive_token_path,
            sender=sender,
            state=state,
            config=config,
        )

    @staticmethod
    def _get_drive_token_path(client: "SyftboxManager") -> Path:
        """Extract Drive token path from client's connection."""
        # The client's connection router has the GDriveConnection
        # which was created with a token_path
        try:
            connection = client.connection_router.connections[0]
            if hasattr(connection, "credentials") and connection.credentials:
                # Try to get the token path from credentials
                # This is a bit hacky but necessary
                pass
        except (AttributeError, IndexError):
            pass

        # Fallback: use standard credentials directory
        from syft_client import CREDENTIALS_DIR

        # Try common token names
        for token_name in ["token_do.json", "token.json"]:
            token_path = CREDENTIALS_DIR / token_name
            if token_path.exists():
                return token_path

        raise FileNotFoundError(
            f"Could not find Drive token in {CREDENTIALS_DIR}. "
            "Please ensure you have a valid Google Drive token."
        )
