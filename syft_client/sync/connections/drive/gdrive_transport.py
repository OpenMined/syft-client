"""Google Drive Files transport layer implementation"""

import io
import json
from pathlib import Path
import pickle
from syft_client.sync.utils.syftbox_utils import check_env
from typing import Any, Dict, List, Optional, Tuple
from typing import TYPE_CHECKING

from pydantic import BaseModel
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from google.oauth2.credentials import Credentials as GoogleCredentials

from syft_client.sync.connections.drive.gdrive_utils import delete_folder_recursive

from syft_client.sync.connections.base_connection import (
    SyftboxPlatformConnection,
)
from syft_client.sync.events.file_change_event import (
    FileChangeEventsMessageFileName,
    FileChangeEventsMessage,
)
from syft_client.sync.messages.proposed_filechange import (
    MessageFileName,
    FileNameParseError,
    ProposedFileChangesMessage,
)
from syft_client.sync.environments.environment import Environment

if TYPE_CHECKING:
    from syft_client.sync.connections.drive.grdrive_config import (
        GdriveConnectionConfig,
    )

SYFTBOX_FOLDER = "SyftBox"
GOOGLE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
SCOPES = ["https://www.googleapis.com/auth/drive"]
GDRIVE_TRANSPORT_NAME = "gdrive_files"
GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX = "syft_outbox_inbox"


class GdriveArchiveFolder(BaseModel):
    sender_email: str
    recipient_email: str

    def as_string(self) -> str:
        return f"syft_{self.sender_email}_to_{self.recipient_email}_archive"


class GdriveInboxOutBoxFolder(BaseModel):
    sender_email: str
    recipient_email: str

    def as_string(self) -> str:
        return f"{GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX}_{self.sender_email}_to_{self.recipient_email}"

    @classmethod
    def from_name(cls, name: str) -> "GdriveInboxOutBoxFolder":
        return cls(
            sender_email=name.split("_")[3],
            recipient_email=name.split("_")[5],
        )


class GDriveConnection(SyftboxPlatformConnection):
    """Google Drive Files API transport layer"""

    class Config:
        arbitrary_types_allowed = True

    drive_service: Any = None
    credentials: GoogleCredentials | None = None
    verbose: bool = True
    email: str
    _is_setup: bool = False

    # /SyftBox
    # this is the toplevel folder with inboxes, outboxes and personal syftbox
    _syftbox_folder_id: str | None = None

    # /SyftBox/myemail
    # this is where we store the personal data
    _personal_syftbox_folder_id: str | None = None

    # email -> inbox folder id
    do_inbox_folder_id_cache: Dict[str, str] = {}
    do_outbox_folder_id_cache: Dict[str, str] = {}

    # email -> inbox folder id
    ds_inbox_folder_id_cache: Dict[str, str] = {}
    ds_outbox_folder_id_cache: Dict[str, str] = {}

    # sender email -> archive folder id
    archive_folder_id_cache: Dict[str, str] = {}

    # fname -> gdrive id
    personal_syftbox_event_id_cache: Dict[str, str] = {}

    @classmethod
    def from_config(cls, config: "GdriveConnectionConfig") -> "GDriveConnection":
        return cls.from_token_path(config.email, config.token_path)

    @classmethod
    def from_token_path(cls, email: str, token_path: Path | None) -> "GDriveConnection":
        res = cls(email=email)
        if token_path:
            credentials = GoogleCredentials.from_authorized_user_file(
                token_path, SCOPES
            )
        else:
            credentials = None
        res.setup(credentials=credentials)
        return res

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

        self.get_personal_syftbox_folder_id()
        self._is_setup = True

    @property
    def transport_name(self) -> str:
        """Get the name of this transport"""
        return GDRIVE_TRANSPORT_NAME

    @property
    def environment(self) -> Environment:
        return check_env()

    def create_personal_syftbox_folder(self) -> str:
        """Creates /SyftBox/myemail"""
        syftbox_folder_id = self.get_syftbox_folder_id()
        return self.create_folder(self.email, syftbox_folder_id)

    def create_syftbox_folder(self) -> str:
        """Creates /SyftBox"""
        return self.create_folder(SYFTBOX_FOLDER, None)

    def create_archive_folder(self, sender_email: str) -> str:
        archive_folder = GdriveArchiveFolder(
            sender_email=sender_email, recipient_email=self.email
        )
        archive_folder_name = archive_folder.as_string()
        syftbox_folder_id = self.get_syftbox_folder_id()
        return self.create_folder(archive_folder_name, syftbox_folder_id)

    def add_peer_as_do(self, peer_email: str):
        """Add peer knowing that self is do"""
        pass

    def add_peer_as_ds(self, peer_email: str):
        """Add peer knowing that self is ds"""
        # create the DS outbox (DO inbox)
        peer_folder_id = self._get_ds_outbox_folder_id(peer_email)
        if peer_folder_id is None:
            peer_folder_id = self.create_peer_outbox_folder_as_ds(peer_email)
        self.add_permission(peer_folder_id, peer_email, write=True)

        # create the DS inbox (DO outbox)
        peer_folder_id = self._get_ds_inbox_folder_id(peer_email)
        if peer_folder_id is None:
            peer_folder_id = self.create_peer_inbox_folder_as_ds(peer_email)
        self.add_permission(peer_folder_id, peer_email, write=True)

    def get_peers_as_do(self) -> List[str]:
        results = (
            self.drive_service.files()
            .list(
                q=f"name contains '{GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX}' and trashed=false"
                f"and mimeType = '{GOOGLE_FOLDER_MIME_TYPE}'"
            )
            .execute()
        )
        peers = set()
        inbox_folders = results.get("files", [])
        inbox_folder_names = [x["name"] for x in inbox_folders]
        for name in inbox_folder_names:
            outbox_folder = GdriveInboxOutBoxFolder.from_name(name)
            if outbox_folder.sender_email != self.email:
                peers.add(outbox_folder.sender_email)
        return list(peers)

    def get_peers_as_ds(self) -> List[str]:
        results = (
            self.drive_service.files()
            .list(
                q=f"name contains '{GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX}' and 'me' in owners and trashed=false"
                f"and mimeType = '{GOOGLE_FOLDER_MIME_TYPE}'"
            )
            .execute()
        )
        peers = set()
        # we want to know who it is shared with and gather those email addresses
        outbox_folders = results.get("files", [])
        outbox_folder_names = [x["name"] for x in outbox_folders]
        for name in outbox_folder_names:
            try:
                outbox_folder = GdriveInboxOutBoxFolder.from_name(name)
                if outbox_folder.recipient_email != self.email:
                    peers.add(outbox_folder.recipient_email)
            except Exception:
                continue
        return list(peers)

    def get_events_messages_for_datasite_watcher(
        self, peer_email: str, since_timestamp: float | None
    ) -> List[FileChangeEventsMessage]:
        folder_id = self._get_ds_inbox_folder_id(peer_email)
        # folder_id = self._find_folder_by_name(peer_email, owner_email=peer_email)
        if folder_id is None:
            raise ValueError(f"Folder for peer {peer_email} not found")

        file_metadatas = self.get_file_metadatas_from_folder(folder_id)
        valid_fname_objs = self._get_valid_events_from_file_metadatas(file_metadatas)
        valid_file_names_sorted = [
            x.as_string()
            for x in sorted(valid_fname_objs, key=lambda x: x.timestamp)
            if since_timestamp is None or x.timestamp > since_timestamp
        ]
        if len(valid_fname_objs) == 0:
            return []
        else:
            relevant_drive_ids = [
                f["id"] for f in file_metadatas if f["name"] in valid_file_names_sorted
            ]
            res = []
            for _id in relevant_drive_ids:
                file_data = self.download_file(_id)
                res.append(FileChangeEventsMessage.from_compressed_data(file_data))
            return res

    def write_events_message_to_syftbox(self, event_message: FileChangeEventsMessage):
        """Writes to /SyftBox/myemail"""
        personal_syftbox_folder_id = self.get_personal_syftbox_folder_id()
        filename = event_message.message_filepath.as_string()
        message_data = event_message.as_compressed_data()
        file_metadata = {
            "name": filename,
            "parents": [personal_syftbox_folder_id],
        }
        file_payload, _ = self.create_file_payload(message_data)

        res = (
            self.drive_service.files()
            .create(body=file_metadata, media_body=file_payload, fields="id")
            .execute()
        )
        gdrive_id = res.get("id")
        self.personal_syftbox_event_id_cache[filename] = gdrive_id
        return gdrive_id

    def get_all_events_messages_do(self) -> List[FileChangeEventsMessage]:
        """Reads from /SyftBox/myemail"""
        personal_syftbox_folder_id = self.get_personal_syftbox_folder_id()
        file_metadatas = self.get_file_metadatas_from_folder(personal_syftbox_folder_id)
        valid_fname_objs = self._get_valid_events_from_file_metadatas(file_metadatas)

        result = []
        for fname_obj in valid_fname_objs:
            gdrive_id = [
                f for f in file_metadatas if f["name"] == fname_obj.as_string()
            ][0]["id"]
            try:
                file_data = self.download_file(gdrive_id)
            except Exception as e:
                print(e)
                continue
            event = FileChangeEventsMessage.from_compressed_data(file_data)
            result.append(event)
        return result

    def write_event_messages_to_outbox_do(
        self, recipient: str, events_message: FileChangeEventsMessage
    ):
        fname = events_message.message_filepath.as_string()
        message_data = events_message.as_compressed_data()

        outbox_folder_id = self._get_do_outbox_folder_id(recipient)

        if outbox_folder_id is None:
            raise ValueError(f"Outbox folder for {recipient} not found")

        file_payload, _ = self.create_file_payload(message_data)

        file_metadata = {
            "name": fname,
            "parents": [outbox_folder_id],
        }

        self.drive_service.files().create(
            body=file_metadata, media_body=file_payload, fields="id"
        ).execute()

    def remove_proposed_filechange_message_from_inbox(
        self, proposed_filechange_message: ProposedFileChangesMessage
    ):
        fname = proposed_filechange_message.message_filename.as_string()
        sender_email = proposed_filechange_message.sender_email
        gdrive_id = self.get_inbox_proposed_event_id_from_name(sender_email, fname)
        if gdrive_id is None:
            raise ValueError(
                f"Event {fname} not found in outbox, event should already be created for this type of connection"
            )
        file_info = (
            self.drive_service.files().get(fileId=gdrive_id, fields="parents").execute()
        )
        previous_parents = ",".join(file_info.get("parents", []))
        archive_folder_id = self.get_archive_folder_id_as_do(sender_email)
        self.drive_service.files().update(
            fileId=gdrive_id,
            addParents=archive_folder_id,
            removeParents=previous_parents,
            fields="id, parents",
            supportsAllDrives=True,
        ).execute()

    def add_permission(self, file_id: str, recipient: str, write=False):
        """Add permission to the file"""
        role = "writer" if write else "reader"
        permission = {
            "type": "user",
            "role": role,
            "emailAddress": recipient,
        }
        self.drive_service.permissions().create(
            fileId=file_id, body=permission, sendNotificationEmail=True
        ).execute()

    def create_peer_inbox_folder_as_ds(self, peer_email: str) -> str:
        parent_id = self.get_syftbox_folder_id()
        peer_inbox_folder = GdriveInboxOutBoxFolder(
            sender_email=peer_email, recipient_email=self.email
        )
        folder_name = peer_inbox_folder.as_string()
        print(f"Creating inbox folder for {peer_email} in {parent_id}")
        _id = self.create_folder(folder_name, parent_id)
        return _id

    def create_peer_outbox_folder_as_ds(self, peer_email: str) -> str:
        parent_id = self.get_syftbox_folder_id()
        peer_inbox_folder = GdriveInboxOutBoxFolder(
            sender_email=self.email, recipient_email=peer_email
        )
        folder_name = peer_inbox_folder.as_string()
        print(f"Creating inbox folder for {peer_email} in {parent_id}")
        return self.create_folder(folder_name, parent_id)

    def get_personal_syftbox_folder_id(self) -> str:
        """/SyftBox/myemail"""
        if self._personal_syftbox_folder_id:
            return self._personal_syftbox_folder_id
        else:
            personal_syftbox_folder_id = self._find_folder_by_name(
                self.email, owner_email=self.email
            )
            if personal_syftbox_folder_id:
                self._personal_syftbox_folder_id = personal_syftbox_folder_id
                return self._personal_syftbox_folder_id
            else:
                return self.create_personal_syftbox_folder()

    def get_syftbox_folder_id(self) -> str:
        """/SyftBox"""
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

    def get_archive_folder_id_from_drive(self, sender_email: str) -> str | None:
        archive_folder = GdriveArchiveFolder(
            sender_email=sender_email, recipient_email=self.email
        )
        archive_folder_name = archive_folder.as_string()
        query = f"name='{archive_folder_name}' and mimeType='application/vnd.google-apps.folder' and 'me' in owners and trashed=false"
        results = self.drive_service.files().list(q=query, fields="files(id)").execute()
        items = results.get("files", [])
        return items[0]["id"] if items else None

    def get_archive_folder_id_as_do(self, sender_email: str) -> str:
        if sender_email in self.archive_folder_id_cache:
            return self.archive_folder_id_cache[sender_email]
        else:
            archive_folder_id = self.get_archive_folder_id_from_drive(sender_email)
            if archive_folder_id:
                self.archive_folder_id_cache[sender_email] = archive_folder_id
                return archive_folder_id
            else:
                return self.create_archive_folder(sender_email)

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
    def _get_valid_events_from_file_metadatas(
        file_metadatas: List[Dict],
    ) -> List[FileChangeEventsMessageFileName]:
        res = []
        for file_metadata in file_metadatas:
            fname = file_metadata["name"]
            try:
                message_filename = FileChangeEventsMessageFileName.from_string(fname)
                res.append(message_filename)
            except Exception:
                print("Warning, invalid file name: ", fname)
                continue
        return res

    @staticmethod
    def _get_valid_messages_from_file_metadatas(
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
        inbox_folder_id = self._get_do_inbox_folder_id(sender_email)
        if inbox_folder_id is None:
            raise ValueError(f"Inbox folder for {sender_email} not found")
        file_metadatas = self.get_file_metadatas_from_folder(inbox_folder_id)
        valid_file_names = self._get_valid_messages_from_file_metadatas(file_metadatas)
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
            res = ProposedFileChangesMessage.from_compressed_data(file_data)
            return res

    def _get_do_inbox_folder_id(self, sender_email: str) -> str | None:
        if sender_email in self.do_inbox_folder_id_cache:
            return self.do_inbox_folder_id_cache[sender_email]

        recipient_email = self.email
        inbox_folder = GdriveInboxOutBoxFolder(
            sender_email=sender_email, recipient_email=recipient_email
        )
        # TODO: this should include the parent id but it doesnt
        do_inbox_folder_id = self._find_folder_by_name(
            inbox_folder.as_string(), owner_email=sender_email
        )
        if do_inbox_folder_id is not None:
            self.do_inbox_folder_id_cache[sender_email] = do_inbox_folder_id
        return do_inbox_folder_id

    def _get_ds_inbox_folder_id(self, sender_email: str) -> str | None:
        if sender_email in self.ds_inbox_folder_id_cache:
            return self.ds_inbox_folder_id_cache[sender_email]

        inbox_folder = GdriveInboxOutBoxFolder(
            sender_email=sender_email, recipient_email=self.email
        )
        inbox_folder_id = self._find_folder_by_name(
            inbox_folder.as_string(), owner_email=self.email
        )
        if inbox_folder_id is not None:
            self.ds_inbox_folder_id_cache[sender_email] = inbox_folder_id
        return inbox_folder_id

    def _get_do_outbox_folder_id(self, recipient: str) -> str | None:
        if recipient in self.do_outbox_folder_id_cache:
            return self.do_outbox_folder_id_cache[recipient]

        outbox_folder = GdriveInboxOutBoxFolder(
            sender_email=self.email, recipient_email=recipient
        )

        outbox_folder_id = self._find_folder_by_name(
            outbox_folder.as_string(), owner_email=recipient
        )
        if outbox_folder_id is not None:
            self.do_outbox_folder_id_cache[recipient] = outbox_folder_id
        return outbox_folder_id

    def _get_ds_outbox_folder_id(self, recipient: str) -> str | None:
        if recipient in self.ds_outbox_folder_id_cache:
            return self.ds_outbox_folder_id_cache[recipient]

        outbox_folder = GdriveInboxOutBoxFolder(
            sender_email=self.email, recipient_email=recipient
        )

        # TODO: this search only in syftbox folder but that doesnt work
        outbox_folder_id = self._find_folder_by_name(
            outbox_folder.as_string(), owner_email=self.email
        )
        if outbox_folder_id is not None:
            self.ds_outbox_folder_id_cache[recipient] = outbox_folder_id
        return outbox_folder_id

    def send_proposed_file_changes_message(
        self,
        recipient: str,
        proposed_file_changes_message: ProposedFileChangesMessage,
    ):
        data_compressed = proposed_file_changes_message.as_compressed_data()

        filename = proposed_file_changes_message.message_filename.as_string()

        inbox_outbox_id = self._get_ds_outbox_folder_id(recipient)
        if inbox_outbox_id is None:
            raise Exception(f"Outbox folder to send messages to {recipient} not found")

        payload, _ = self.create_file_payload(data_compressed)
        file_metadata = {
            "name": filename,
            "parents": [inbox_outbox_id],
        }

        self.drive_service.files().create(
            body=file_metadata, media_body=payload, fields="id"
        ).execute()

    def delete_syftbox(self):
        syftbox_folder_id = self.get_syftbox_folder_id()
        if syftbox_folder_id is not None:
            delete_folder_recursive(self.drive_service, syftbox_folder_id, verbose=True)

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

    def _find_folder_by_name(
        self, folder_name: str, parent_id: str = None, owner_email: str = None
    ) -> Optional[str]:
        """Find a folder by name, optionally within a specific parent"""
        # parent_id = "1AQ3WLnVlLd6Zjo7p9Z_qGA1Djjf6-KIh"
        owner_email_clause = f"and '{owner_email}' in owners" if owner_email else ""
        parent_id_clause = f"and '{parent_id}' in parents" if parent_id else ""
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false {owner_email_clause} {parent_id_clause}"

        results = (
            self.drive_service.files()
            .list(q=query, fields="files(id)", pageSize=1)
            .execute()
        )
        items = results.get("files", [])
        return items[0]["id"] if items else None

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

    def create_folder(self, folder_name: str, parent_id: str) -> str:
        file_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            file_metadata["parents"] = [parent_id]
        folder = (
            self.drive_service.files().create(body=file_metadata, fields="id").execute()
        )
        return folder.get("id")

    def get_syftbox_folder_id_from_drive(self) -> str | None:
        query = f"name='{SYFTBOX_FOLDER}' and mimeType='application/vnd.google-apps.folder' and 'me' in owners and trashed=false"
        results = (
            self.drive_service.files().list(q=query, fields="files(id, name)").execute()
        )
        items = results.get("files", [])
        return items[0]["id"] if items else None

    def get_inbox_proposed_event_id_from_name(
        self, sender_email: str, name: str
    ) -> str | None:
        inbox_folder_id = self._get_do_inbox_folder_id(sender_email)
        query = f"name='{name}' and '{inbox_folder_id}' in parents and trashed=false"
        results = (
            self.drive_service.files().list(q=query, fields="files(id, name)").execute()
        )
        items = results.get("files", [])
        return items[0]["id"] if items else None
