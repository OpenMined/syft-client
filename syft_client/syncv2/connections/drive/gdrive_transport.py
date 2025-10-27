"""Google Drive Files transport layer implementation"""

import io
import json
from pathlib import Path
import pickle
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials as GoogleCredentials

from syft_client.syncv2.connections.drive.gdrive_utils import listify
from syft_client.syncv2.connections.base_connection import (
    ConnectionConfig,
    SyftboxPlatformConnection,
)
from syft_client.syncv2.events.file_change_event import FileChangeEvent
from syft_client.syncv2.messages.proposed_filechange import (
    MessageFileName,
    FileNameParseError,
    ProposedFileChangesMessage,
    ProposedFileChange,
)

from syft_client.environment import Environment


SYFT_FOLDER = "SyftClient"
GOOGLE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
SCOPES = ["https://www.googleapis.com/auth/drive"]


class GdriveInboxOutBoxFolder(BaseModel):
    sender_email: str
    recipient_email: str

    def as_string(self) -> str:
        return f"syft_{self.sender_email}_to_{self.recipient_email}_outbox_inbox"


class GDriveConnection(SyftboxPlatformConnection):
    """Google Drive Files API transport layer"""

    class Config:
        arbitrary_types_allowed = True

    drive_service: Any = None
    credentials: GoogleCredentials | None = None
    verbose: bool = True
    email: str
    _is_setup: bool = False
    _syftbox_folder_id: str | None = None

    # email -> inbox folder id
    inbox_folder_id_cache: Dict[str, str] = {}
    outbox_folder_id_cache: Dict[str, str] = {}

    @classmethod
    def from_config(cls, config: "GdriveConnectionConfig") -> "GDriveConnection":
        return cls.from_token_path(config.email, config.token_path)

    @classmethod
    def from_token_path(cls, email: str, token_path: Path) -> "GDriveConnection":
        res = cls(email=email)
        credentials = GoogleCredentials.from_authorized_user_file(token_path, SCOPES)
        res.setup(credentials=credentials)
        return res

    def get_events_for_datasite_watcher(
        self, since_timestamp: float | None
    ) -> List[FileChangeEvent]:
        # TODO: implement
        return []

    @property
    def environment(self) -> Environment:
        return Environment.REPL

    def setup(self, credentials: GoogleCredentials | None = None):
        """Setup Drive transport with OAuth2 credentials or Colab auth"""
        # Check if we're in Colab and can use automatic auth
        self.credentials = credentials
        if self.environment == Environment.COLAB:
            from google.colab import auth as colab_auth

            colab_auth.authenticate_user()
            # Build service without explicit credentials in Colab
            self.drive_service = build("drive", "v3")

        self.drive_service = build("drive", "v3", credentials=self.credentials)

        self.get_syftbox_folder_id()
        self._is_setup = True

    def add_permission(self, file_id: str, recipient: str):
        """Add permission to the file"""
        permission = {
            "type": "user",
            "role": "reader",
            "emailAddress": recipient,
        }
        self.drive_service.permissions().create(
            fileId=file_id, body=permission, sendNotificationEmail=True
        ).execute()

    @property
    def transport_name(self) -> str:
        """Get the name of this transport"""
        return "gdrive_files"

    def create_syftbox_folder(self) -> str:
        file_metadata = {
            "name": SYFT_FOLDER,
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder = (
            self.drive_service.files().create(body=file_metadata, fields="id").execute()
        )
        self._syftbox_folder_id = folder.get("id")
        return self._syftbox_folder_id

    def get_syftbox_folder_id_from_drive(self) -> str | None:
        query = f"name='{SYFT_FOLDER}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = (
            self.drive_service.files().list(q=query, fields="files(id, name)").execute()
        )
        items = results.get("files", [])
        return items[0]["id"] if items else None

    def get_syftbox_folder_id(self) -> str:
        # cached
        if self._syftbox_folder_id:
            return self._syftbox_folder_id
        else:
            syftbox_folder_id = self.get_syftbox_folder_id_from_drive()
            if syftbox_folder_id:
                self._syftbox_folder_id = syftbox_folder_id
                return self._syftbox_folder_id
            else:
                return self.create_syftbox_folder()

    def get_file_metadatas_from_folder(self, folder_id: str) -> List[Dict]:
        query = f"'{folder_id}' in parents and trashed=false"
        results = (
            self.drive_service.files()
            .list(
                q=query,
                fields="files(id, name, size, mimeType, modifiedTime)",
                pageSize=100,
            )
            .execute()
        )
        return results.get("files", [])

    @staticmethod
    def is_message_file(file_metadata: Dict) -> bool:
        file_name = file_metadata["name"]
        try:
            MessageFileName.from_string(file_name)
            return True
        except FileNameParseError:
            return False

    @staticmethod
    def _get_valid_files_from_file_metadatas(
        file_metadatas: List[Dict],
    ) -> List[MessageFileName]:
        res = []
        for file_metadata in file_metadatas:
            try:
                message_filename = MessageFileName.from_string(file_metadata["name"])
                res.append(message_filename)
            except FileNameParseError:
                continue
        return res

    def get_next_proposed_filechange_message(
        self, sender_email: str
    ) -> ProposedFileChangesMessage | None:
        inbox_folder_id = self._get_my_inbox_folder_id(sender_email)
        file_metadatas = self.get_file_metadatas_from_folder(inbox_folder_id)
        valid_file_names = self._get_valid_files_from_file_metadatas(file_metadatas)
        if len(valid_file_names) == 0:
            return None
        else:
            first_file_name = sorted(
                valid_file_names, key=lambda x: x.submitted_timestamp
            )[0]
            first_file_id = [
                x for x in file_metadatas if x["name"] == first_file_name.as_string()
            ][0]["id"]
            file_data = self.download_file(first_file_id)
            return ProposedFileChangesMessage.from_compressed_data(file_data)

    def _get_owner_inbox_messages(
        self, sender_email: str, verbose: bool = True
    ) -> List[ProposedFileChangesMessage]:
        messages = []

        # Determine the inbox folder name pattern
        inbox_folder_id = self._get_my_inbox_folder_id(sender_email)
        file_metadatas = self.get_file_metadatas_from_folder(inbox_folder_id)

        for file_metadata in file_metadatas:
            try:
                if self.is_message_file(file_metadata):
                    file_id = file_metadata["id"]
                    message_data = self.download_file(file_id)
                    message = ProposedFileChangesMessage.from_compressed_data(
                        message_data
                    )
                    messages.append(message)

            except Exception as e:
                if verbose:
                    print(f"❌ Error downloading {file_metadata['name']}: {e}")

        return messages

    def _get_my_inbox_folder_id(self, sender_email: str) -> str | None:
        if sender_email in self.inbox_folder_id_cache:
            return self.inbox_folder_id_cache[sender_email]

        recipient_email = self.email
        inbox_folder = GdriveInboxOutBoxFolder(
            sender_email=sender_email, recipient_email=recipient_email
        )
        # TODO: this should include the parent id but it doesnt
        inbox_folder_id = self._find_folder_by_name(inbox_folder.as_string())
        if inbox_folder_id is not None:
            self.inbox_folder_id_cache[sender_email] = inbox_folder_id
        return inbox_folder_id

    def _get_sender_outbox_folder_id(self, recipient: str) -> str | None:
        if recipient in self.outbox_folder_id_cache:
            return self.outbox_folder_id_cache[recipient]

        outbox_folder = GdriveInboxOutBoxFolder(
            sender_email=self.email, recipient_email=recipient
        )

        # TODO: this search only in syftbox folder but that doesnt work
        outbox_folder_id = self._find_folder_by_name(outbox_folder.as_string())
        if outbox_folder_id is not None:
            self.outbox_folder_id_cache[recipient] = outbox_folder_id
        return outbox_folder_id

    def send_proposed_file_changes_message(
        self,
        recipient: str,
        proposed_file_changes_message: ProposedFileChangesMessage,
    ):
        print("sending")
        data_compressed = proposed_file_changes_message.as_compressed_data()
        self.send_archive_via_transport(
            data_compressed,
            proposed_file_changes_message.message_filename.as_string(),
            recipient,
        )

    def _find_folder_by_name(
        self, folder_name: str, parent_id: str = None
    ) -> Optional[str]:
        """Find a folder by name, optionally within a specific parent"""
        # parent_id = "1AQ3WLnVlLd6Zjo7p9Z_qGA1Djjf6-KIh"
        if parent_id:
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
        else:
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"

        results = (
            self.drive_service.files()
            .list(q=query, fields="files(id)", pageSize=1)
            .execute()
        )
        items = results.get("files", [])
        return items[0]["id"] if items else None

    def send_archive_via_transport(
        self,
        archive_data: bytes,
        filename: str,
        recipient: str,
    ) -> bool:
        watcher_outbox_id = self._get_sender_outbox_folder_id(recipient)
        if watcher_outbox_id is None:
            raise Exception(f"Outbox folder to send messages to {recipient} not found")

        payload, _ = self.create_file_payload(archive_data)
        file_metadata = {
            "name": filename,
            "parents": [watcher_outbox_id],
        }

        self.drive_service.files().create(
            body=file_metadata, media_body=payload, fields="id"
        ).execute()

    def create_file_payload(self, data: Any) -> Tuple[MediaIoBaseUpload, str]:
        """Create a file payload for the GDrive"""
        if isinstance(data, str):
            file_data = data.encode("utf-8")
            mime_type = "text/plain"
            extension = ".txt"
        elif isinstance(data, dict):
            file_data = json.dumps(data, indent=2).encode("utf-8")
            mime_type = "application/json"
            extension = ".json"
        elif isinstance(data, bytes):
            file_data = data
            mime_type = "application/octet-stream"
            extension = ".bin"
        else:
            # Pickle for other data types
            file_data = pickle.dumps(data)
            mime_type = "application/octet-stream"
            extension = ".pkl"

        media = MediaIoBaseUpload(
            io.BytesIO(file_data), mimetype=mime_type, resumable=True
        )

        return media, extension

    def download_file(self, file_id: str) -> bytes:
        # This is likely a message archive
        request = self.drive_service.files().get_media(fileId=file_id)

        # Download to memory
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        message_data = file_buffer.getvalue()
        return message_data


class GdriveConnectionConfig(ConnectionConfig):
    connection_type: ClassVar[Type["GDriveConnection"]] = GDriveConnection
    email: str
    token_path: Path

    @classmethod
    def from_token_path(cls, email: str, token_path: Path) -> "GdriveConnectionConfig":
        return cls(email=email, token_path=token_path)
