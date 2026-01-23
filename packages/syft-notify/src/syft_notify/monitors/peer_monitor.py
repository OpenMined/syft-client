from pathlib import Path

from syft_notify.handlers import PeerHandler
from syft_notify.monitors.base import Monitor
from syft_notify.state import JsonStateManager

GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX = "syft_outbox_inbox"
GOOGLE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


class PeerMonitor(Monitor):
    def __init__(
        self,
        do_email: str,
        drive_token_path: Path,
        handler: PeerHandler,
        state: JsonStateManager,
    ):
        self.do_email = do_email
        self.drive_token_path = Path(drive_token_path)
        self.handler = handler
        self.state = state
        self._drive_service = self._create_drive_service()

    def _create_drive_service(self):
        from google.oauth2.credentials import Credentials as GoogleCredentials
        from googleapiclient.discovery import build

        credentials = GoogleCredentials.from_authorized_user_file(
            str(self.drive_token_path), DRIVE_SCOPES
        )
        return build("drive", "v3", credentials=credentials)

    def _check_all_entities(self):
        current_peer_emails = self._load_peers_from_drive()
        previous_peer_emails = set(self.state.get_data("peer_snapshot", []))
        new_peer_emails = current_peer_emails - previous_peer_emails

        if new_peer_emails:
            print(f"🔍 PeerMonitor: Detected {len(new_peer_emails)} new peer(s)")

        for peer_email in new_peer_emails:
            self._handle_new_peer(peer_email)

        self.state.set_data("peer_snapshot", list(current_peer_emails))

    def _load_peers_from_drive(self) -> set[str]:
        try:
            results = (
                self._drive_service.files()
                .list(
                    q=f"name contains '{GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX}' and trashed=false "
                    f"and mimeType = '{GOOGLE_FOLDER_MIME_TYPE}'"
                )
                .execute()
            )

            peers: set[str] = set()
            inbox_folders = results.get("files", [])

            for folder in inbox_folders:
                name = folder["name"]
                parts = name.split("_")
                if len(parts) >= 6:
                    sender_email = parts[3]
                    recipient_email = parts[5] if len(parts) > 5 else None
                    if (
                        sender_email != self.do_email
                        and recipient_email == self.do_email
                    ):
                        peers.add(sender_email)

            return peers

        except Exception as e:
            print(f"⚠️  PeerMonitor: Error loading peers: {e}")
            return set()

    def _handle_new_peer(self, ds_email: str):
        success = self.handler.on_new_peer_request_to_do(self.do_email, ds_email)
        if success:
            print(f"📧 Sent new peer request notification to DO: {ds_email}")

        success = self.handler.on_peer_request_sent(ds_email, self.do_email)
        if success:
            print(f"📧 Sent peer request sent notification to DS: {ds_email}")

    def notify_peer_granted(self, ds_email: str) -> bool:
        success = self.handler.on_peer_granted(ds_email, self.do_email)
        if success:
            print(f"📧 Sent peer granted notification to DS: {ds_email}")
        return success
