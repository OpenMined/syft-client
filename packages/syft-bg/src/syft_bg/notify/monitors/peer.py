"""Peer monitor for detecting new peer requests."""

from pathlib import Path
from typing import Optional

from syft_bg.common.drive import create_drive_service
from syft_bg.common.monitor import Monitor
from syft_bg.common.state import JsonStateManager
from syft_bg.notify.handlers.peer import PeerHandler

GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX = "syft_outbox_inbox"
GOOGLE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


class PeerMonitor(Monitor):
    """Monitors for new peer requests via Google Drive."""

    def __init__(
        self,
        do_email: str,
        drive_token_path: Optional[Path],
        handler: PeerHandler,
        state: JsonStateManager,
    ):
        super().__init__()
        self.do_email = do_email
        self.drive_token_path = Path(drive_token_path) if drive_token_path else None
        self.handler = handler
        self.state = state
        self._drive_service = create_drive_service(self.drive_token_path)

    def _check_all_entities(self):
        current_peer_emails = self._load_peers_from_drive()
        previous_peer_emails = set(self.state.get_data("peer_snapshot", []))
        new_peer_emails = current_peer_emails - previous_peer_emails

        if new_peer_emails:
            print(f"[PeerMonitor] Detected {len(new_peer_emails)} new peer(s)")

        for peer_email in new_peer_emails:
            self._handle_new_peer(peer_email)

        self.state.set_data("peer_snapshot", list(current_peer_emails))

    def _load_peers_from_drive(self) -> set[str]:
        if not self._drive_service:
            return set()

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
            print(f"[PeerMonitor] Error loading peers: {e}")
            return set()

    def _handle_new_peer(self, ds_email: str):
        success = self.handler.on_new_peer_request_to_do(self.do_email, ds_email)
        if success:
            print(f"[PeerMonitor] Sent new peer request notification to DO: {ds_email}")

        success = self.handler.on_peer_request_sent(ds_email, self.do_email)
        if success:
            print(
                f"[PeerMonitor] Sent peer request sent notification to DS: {ds_email}"
            )

    def notify_peer_granted(self, ds_email: str) -> bool:
        """Notify DS that their peer request was granted."""
        success = self.handler.on_peer_granted(ds_email, self.do_email)
        if success:
            print(f"[PeerMonitor] Sent peer granted notification to DS: {ds_email}")
        return success
