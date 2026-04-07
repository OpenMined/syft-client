"""Scans Google Drive for inbox folders, messages, and peer data."""

import json
from typing import Any, Optional

from syft_bg.sync.snapshot import InboxMessage

GDRIVE_P2P_FOLDER_PREFIX = "syft_datasite"
GOOGLE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
SYFT_PEERS_FILE = "SYFT_peers.json"


class DriveInboxScanner:
    def __init__(self, drive_service, do_email: str):
        self._drive = drive_service
        self._do_email = do_email

    def scan_inbox_messages(self) -> list[InboxMessage]:
        try:
            messages = []
            for _, folder_id in self._find_inbox_folders():
                for msg_file in self._get_pending_messages(folder_id):
                    parsed = self._parse_job_from_message(msg_file["id"])
                    if parsed:
                        messages.append(parsed)
            return messages
        except Exception as e:
            print(f"[DriveInboxScanner] Error scanning inbox messages: {e}")
            return []

    def scan_peer_emails(self) -> list[str]:
        """Detect peer emails from inbox folder names.

        Looks for folders: syft_datasite#<do_email>#inbox#<peer_email>
        """
        try:
            query = (
                f"name contains '{GDRIVE_P2P_FOLDER_PREFIX}#' and "
                f"name contains '#inbox#' and "
                f"mimeType = '{GOOGLE_FOLDER_MIME_TYPE}' and "
                "trashed=false"
            )
            results = self._drive.files().list(q=query).execute()

            peers: set[str] = set()
            for folder in results.get("files", []):
                parsed = self._parse_p2p_folder_name(folder["name"])
                if parsed and parsed["folder_type"] == "inbox":
                    if (
                        parsed["datasite_email"] == self._do_email
                        and parsed["peer_email"] != self._do_email
                    ):
                        peers.add(parsed["peer_email"])

            return list(peers)

        except Exception as e:
            print(f"[DriveInboxScanner] Error scanning peer emails: {e}")
            return []

    def scan_approved_peers(self) -> list[str]:
        try:
            query = f"name = '{SYFT_PEERS_FILE}' and trashed = false"
            results = self._drive.files().list(q=query, fields="files(id)").execute()
            files = results.get("files", [])
            if not files:
                return []

            file_id = files[0]["id"]
            request = self._drive.files().get_media(fileId=file_id)
            content = request.execute()
            peers_data = json.loads(content.decode("utf-8"))

            return [
                email
                for email, data in peers_data.items()
                if data.get("state") == "accepted"
            ]

        except Exception as e:
            print(f"[DriveInboxScanner] Error scanning approved peers: {e}")
            return []

    def _find_inbox_folders(self) -> list[tuple[str, str]]:
        """Find inbox folders: syft_datasite#<do_email>#inbox#<peer_email>."""
        query = (
            f"name contains '{GDRIVE_P2P_FOLDER_PREFIX}#{self._do_email}#inbox#' and "
            f"mimeType = '{GOOGLE_FOLDER_MIME_TYPE}' and "
            "trashed=false"
        )
        results = self._drive.files().list(q=query).execute()

        folders = []
        for folder in results.get("files", []):
            parsed = self._parse_p2p_folder_name(folder["name"])
            if (
                parsed
                and parsed["folder_type"] == "inbox"
                and parsed["datasite_email"] == self._do_email
                and parsed["peer_email"] != self._do_email
            ):
                folders.append((parsed["peer_email"], folder["id"]))
        return folders

    @staticmethod
    def _parse_p2p_folder_name(name: str) -> Optional[dict[str, str]]:
        """Parse syft_datasite#email#type#peer into components."""
        parts = name.split("#")
        if len(parts) != 4 or parts[0] != GDRIVE_P2P_FOLDER_PREFIX:
            return None
        return {
            "datasite_email": parts[1],
            "folder_type": parts[2],
            "peer_email": parts[3],
        }

    def _get_pending_messages(self, folder_id: str) -> list[dict[str, Any]]:
        query = f"'{folder_id}' in parents and name contains 'msgv2_' and trashed=false"
        results = (
            self._drive.files()
            .list(q=query, fields="files(id, name)", orderBy="name")
            .execute()
        )
        return results.get("files", [])

    def _parse_job_from_message(self, file_id: str) -> Optional[InboxMessage]:
        try:
            from syft_client.sync.messages.proposed_filechange import (
                ProposedFileChangesMessage,
            )

            request = self._drive.files().get_media(fileId=file_id)
            content = request.execute()
            msg = ProposedFileChangesMessage.from_compressed_data(content)

            for change in msg.proposed_file_changes:
                path = str(change.path_in_datasite)
                if "app_data/job/" in path and path.endswith("config.yaml"):
                    parts = path.split("/")
                    try:
                        job_idx = parts.index("job")
                        job_name = parts[job_idx + 1]
                        return InboxMessage(
                            job_name=job_name,
                            submitter=msg.sender_email,
                            message_id=file_id,
                        )
                    except (ValueError, IndexError):
                        continue

            return None

        except Exception as e:
            print(f"[DriveInboxScanner] Error parsing message {file_id}: {e}")
            return None
