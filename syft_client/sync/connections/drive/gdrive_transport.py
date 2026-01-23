"""Google Drive Files transport layer implementation"""

import io
import json
from pathlib import Path
import pickle
from syft_client.sync.utils.syftbox_utils import check_env
from typing import Any, Dict, List, Optional, Tuple
from typing import TYPE_CHECKING
from googleapiclient.http import BatchHttpRequest
from pydantic import BaseModel
import httplib2
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from google.oauth2.credentials import Credentials as GoogleCredentials

from syft_client.sync.connections.drive.gdrive_utils import (
    gather_all_file_and_folder_ids_recursive,
)

from syft_client.sync.connections.base_connection import (
    FileCollection,
    SyftboxPlatformConnection,
)
from syft_datasets.dataset_manager import SHARE_WITH_ANY, DATASET_COLLECTION_PREFIX
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
    from syft_client.sync.version.version_info import VersionInfo

# Timeout for Google API requests (in seconds)
GOOGLE_API_TIMEOUT = 120  # 2 minutes

SYFTBOX_FOLDER = "SyftBox"
GOOGLE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
SCOPES = ["https://www.googleapis.com/auth/drive"]
GDRIVE_TRANSPORT_NAME = "gdrive_files"
GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX = "syft_outbox_inbox"
SYFT_PEERS_FILE = "SYFT_peers.json"
SYFT_VERSION_FILE = "SYFT_version.json"


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


class DatasetCollectionFolder(BaseModel):
    """Represents a dataset collection folder with format: {prefix}_{tag}_{hash}"""

    tag: str
    content_hash: str

    def as_string(self) -> str:
        return f"{DATASET_COLLECTION_PREFIX}_{self.tag}_{self.content_hash}"

    @classmethod
    def from_name(cls, name: str) -> "DatasetCollectionFolder":
        """Parse folder name like 'syft_datasetcollection_mytag_abc123'"""
        parts = name.split("_")
        if len(parts) < 3:
            raise ValueError(f"Invalid dataset collection folder name: {name}")
        # prefix is parts[0:2] joined = "syft_datasetcollection"
        # tag is parts[2:-1] joined (in case tag has underscores)
        # hash is parts[-1]
        tag = "_".join(parts[2:-1])
        content_hash = parts[-1]
        return cls(tag=tag, content_hash=content_hash)

    @staticmethod
    def compute_hash(files: dict[str, bytes]) -> str:
        """Compute a hash from file contents."""
        from syft_client.sync.file_utils import compute_file_hashes

        return compute_file_hashes(files)


class GDriveConnection(SyftboxPlatformConnection):
    """Google Drive Files API transport layer"""

    class Config:
        arbitrary_types_allowed = True

    drive_service: Any = None
    credentials: GoogleCredentials | None = None
    verbose: bool = True
    email: str
    token_path: Path | None = None
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

    # tag -> dataset collection folder id
    dataset_collection_folder_id_cache: Dict[str, str] = {}

    @classmethod
    def from_config(cls, config: "GdriveConnectionConfig") -> "GDriveConnection":
        return cls.from_token_path(config.email, config.token_path)

    @classmethod
    def from_token_path(cls, email: str, token_path: Path | None) -> "GDriveConnection":
        res = cls(email=email, token_path=token_path)
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

        # Create Http with timeout to prevent indefinite hangs
        http = httplib2.Http(timeout=GOOGLE_API_TIMEOUT)
        authorized_http = AuthorizedHttp(self.credentials, http=http)
        self.drive_service = build("drive", "v3", http=authorized_http)

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

    def add_peer_as_ds(self, peer_email: str):
        """Add peer knowing that self is ds"""
        # create the DS outbox (DO inbox)
        peer_folder_id = self._get_outbox_folder_id_as_ds(peer_email)
        if peer_folder_id is None:
            peer_folder_id = self.create_peer_outbox_folder_as_ds(peer_email)
        self.add_permission(peer_folder_id, peer_email, write=True)

        # create the DS inbox (DO outbox)
        peer_folder_id = self._get_inbox_folder_id_as_ds(peer_email)
        if peer_folder_id is None:
            peer_folder_id = self.create_peer_inbox_folder_as_ds(peer_email)
        self.add_permission(peer_folder_id, peer_email, write=True)

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

    def _get_peers_file_id(self) -> str | None:
        """Find SYFT_peers.json file in /SyftBox folder"""
        syftbox_folder_id = self.get_syftbox_folder_id()
        query = f"name='{SYFT_PEERS_FILE}' and '{syftbox_folder_id}' in parents and trashed=false"
        results = self.drive_service.files().list(q=query, fields="files(id)").execute()
        items = results.get("files", [])
        return items[0]["id"] if items else None

    def _read_peers_json(self) -> Dict[str, Dict[str, str]]:
        """Read peers JSON from GDrive. Returns empty dict if not found."""
        file_id = self._get_peers_file_id()
        if file_id is None:
            return {}

        try:
            file_data = self.download_file(file_id)
            return json.loads(file_data.decode("utf-8"))
        except Exception as e:
            print(f"Warning: Error reading peers file: {e}")
            return {}

    def _write_peers_json(self, peers_data: Dict[str, Dict[str, str]]):
        """Write peers JSON to GDrive. Creates or updates the file."""
        syftbox_folder_id = self.get_syftbox_folder_id()
        file_id = self._get_peers_file_id()

        # Convert to JSON bytes
        json_data = json.dumps(peers_data, indent=2)
        file_payload, _ = self.create_file_payload(json_data)

        if file_id is None:
            # Create new file
            file_metadata = {
                "name": SYFT_PEERS_FILE,
                "parents": [syftbox_folder_id],
            }
            result = (
                self.drive_service.files()
                .create(body=file_metadata, media_body=file_payload, fields="id")
                .execute()
            )
            return result.get("id")
        else:
            # Update existing file
            self.drive_service.files().update(
                fileId=file_id, media_body=file_payload
            ).execute()
            return file_id

    def _update_peer_state(self, peer_email: str, state: str):
        """Update a single peer's state in the JSON file"""
        peers_data = self._read_peers_json()
        peers_data[peer_email] = {"state": state}
        self._write_peers_json(peers_data)

    def get_approved_peers_as_do(self) -> List[str]:
        """Get list of approved peer emails from JSON file"""
        peers_data = self._read_peers_json()
        return [
            email
            for email, data in peers_data.items()
            if data.get("state") == "accepted"
        ]

    def get_peer_requests_as_do(self) -> List[str]:
        """
        Get list of pending peer requests.
        Returns folders shared with DO that are NOT in JSON with accepted/rejected state.
        """
        # Get all folders shared with DO (current get_peers_as_do logic)
        results = (
            self.drive_service.files()
            .list(
                q=f"name contains '{GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX}' and trashed=false "
                f"and mimeType = '{GOOGLE_FOLDER_MIME_TYPE}'"
            )
            .execute()
        )

        all_folder_peers = set()
        inbox_folders = results.get("files", [])
        inbox_folder_names = [x["name"] for x in inbox_folders]
        for name in inbox_folder_names:
            outbox_folder = GdriveInboxOutBoxFolder.from_name(name)
            if outbox_folder.sender_email != self.email:
                all_folder_peers.add(outbox_folder.sender_email)

        # Filter out peers already in JSON with accepted or rejected state
        peers_data = self._read_peers_json()
        pending_peers = []
        for peer_email in all_folder_peers:
            if peer_email not in peers_data:
                # Not in JSON at all = new pending request
                pending_peers.append(peer_email)
            elif peers_data[peer_email].get("state") not in ["accepted", "rejected"]:
                # In JSON but not accepted or rejected = pending
                pending_peers.append(peer_email)

        return pending_peers

    def get_events_messages_for_datasite_watcher(
        self, peer_email: str, since_timestamp: float | None
    ) -> List[FileChangeEventsMessage]:
        folder_id = self._get_inbox_folder_id_as_ds(peer_email)
        # folder_id = self._find_folder_by_name(peer_email, owner_email=peer_email)
        if folder_id is None:
            raise ValueError(f"Folder for peer {peer_email} not found")

        file_metadatas = self.get_file_metadatas_from_folder(
            folder_id, since_timestamp=since_timestamp
        )
        valid_fname_objs = self._get_valid_events_from_file_metadatas(file_metadatas)

        name_to_id = {f["name"]: f["id"] for f in file_metadatas}

        sorted_fname_objs = [
            x
            for x in sorted(valid_fname_objs, key=lambda x: x.timestamp)
            if since_timestamp is None or x.timestamp > since_timestamp
        ]

        if len(sorted_fname_objs) == 0:
            return []

        res = []
        for fname_obj in sorted_fname_objs:
            file_name = fname_obj.as_string()
            if file_name in name_to_id:
                file_id = name_to_id[file_name]
                file_data = self.download_file(file_id)
                res.append(FileChangeEventsMessage.from_compressed_data(file_data))

        return res

    def get_outbox_file_metadatas_for_ds(
        self, peer_email: str, since_timestamp: float | None
    ) -> List[Dict]:
        """Get file metadata from DS's inbox folder (DO's outbox) without downloading."""
        folder_id = self._get_inbox_folder_id_as_ds(peer_email)
        if folder_id is None:
            raise ValueError(f"Folder for peer {peer_email} not found")

        file_metadatas = self.get_file_metadatas_from_folder(
            folder_id, since_timestamp=since_timestamp
        )
        valid_fname_objs = self._get_valid_events_from_file_metadatas(file_metadatas)
        name_to_id = {f["name"]: f["id"] for f in file_metadatas}

        result = []
        for fname_obj in sorted(valid_fname_objs, key=lambda x: x.timestamp):
            if since_timestamp is None or fname_obj.timestamp > since_timestamp:
                file_name = fname_obj.as_string()
                if file_name in name_to_id:
                    result.append(
                        {
                            "file_id": name_to_id[file_name],
                            "file_name": file_name,
                            "timestamp": fname_obj.timestamp,
                        }
                    )
        return result

    def download_events_message_by_id_from_outbox(
        self, events_message_id: str
    ) -> FileChangeEventsMessage:
        """Download from outbox - same as download_events_message_by_id for GDrive."""
        return self.download_events_message_by_id(events_message_id)

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

    def download_events_message_by_id(
        self, events_message_id: str
    ) -> FileChangeEventsMessage:
        file_data = self.download_file(events_message_id)
        return FileChangeEventsMessage.from_compressed_data(file_data)

    def get_all_accepted_event_file_ids_do(
        self, since_timestamp: float | None = None
    ) -> List[str]:
        personal_syftbox_folder_id = self.get_personal_syftbox_folder_id()
        file_metadatas = self.get_file_metadatas_from_folder(
            personal_syftbox_folder_id, since_timestamp=since_timestamp
        )
        valid_fname_objs = self._filter_valid_file_metadatas(file_metadatas)
        return [f["id"] for f in valid_fname_objs]

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

        outbox_folder_id = self._get_outbox_folder_id_as_do(recipient)

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

        # Use cached platform_id if available, otherwise fall back to name-based lookup
        gdrive_id = proposed_filechange_message.platform_id
        if gdrive_id is None:
            gdrive_id = self.get_inbox_proposed_event_id_from_name(sender_email, fname)
        if gdrive_id is None:
            raise ValueError(
                f"Event {fname} not found in inbox, event should already be created for this type of connection"
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
            syftbox_folder_id = self.get_syftbox_folder_id()
            personal_syftbox_folder_id = self._find_folder_by_name(
                self.email,
                parent_id=syftbox_folder_id,
                owner_email=self.email,
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

    @staticmethod
    def _extract_timestamp_from_filename(filename: str) -> float | None:
        """
        Extract timestamp from filename.

        Supports multiple filename formats:
        - Event files: syfteventsmessagev3_<timestamp>_<uuid>.tar.gz
        - Job files: msgv2_<timestamp>_<uid>.tar.gz

        Args:
            filename: The filename to parse

        Returns:
            Timestamp as float, or None if can't parse
        """
        try:
            # Try event file format first
            if filename.startswith("syfteventsmessagev3_"):
                parts = filename.split("_")
                if len(parts) >= 2:
                    return float(parts[1])

            # Try job file format
            if filename.startswith("msgv2_"):
                parts = filename.split("_")
                if len(parts) >= 2:
                    return float(parts[1])

            return None
        except (ValueError, IndexError):
            return None

    def get_file_metadatas_from_folder(
        self,
        folder_id: str,
        since_timestamp: float | None = None,
        page_size: int = 100,
    ) -> List[Dict]:
        """
        Get file metadatas from folder with early termination.

        Args:
            folder_id: Google Drive folder ID
            since_timestamp: Optional timestamp. If provided, stops pagination
                           when encountering files with timestamp <= this value.
                           Enables early termination optimization.
            page_size: Number of files to fetch per API call. Default 100.

        Returns:
            List of file metadata dicts, sorted by name descending (newest first)
        """
        query = f"'{folder_id}' in parents and trashed=false"
        all_files = []
        page_token = None

        while True:
            results = (
                self.drive_service.files()
                .list(
                    q=query,
                    fields="files(id, name, size, mimeType, modifiedTime), nextPageToken",
                    pageSize=page_size,
                    pageToken=page_token,
                    orderBy="name desc",
                )
                .execute()
            )

            page_files = results.get("files", [])

            # Early termination: Check if this page contains old files
            if since_timestamp is not None and page_files:
                should_stop = False

                for file in page_files:
                    timestamp = self._extract_timestamp_from_filename(file["name"])

                    if timestamp is not None:
                        if timestamp > since_timestamp:
                            all_files.append(file)
                        else:
                            # Found a file we already have! Stop pagination
                            should_stop = True
                            break
                    else:
                        # No timestamp in filename, include the file
                        all_files.append(file)

                if should_stop:
                    # Don't fetch more pages
                    break
            else:
                # No early termination check, add all files
                all_files.extend(page_files)

            # Check for next page
            page_token = results.get("nextPageToken")
            if not page_token:
                break

        return all_files

    @staticmethod
    def is_message_file(file_metadata: Dict) -> bool:
        file_name = file_metadata["name"]
        try:
            MessageFileName.from_string(file_name)
            return True
        except FileNameParseError:
            return False

    @staticmethod
    def _filter_valid_file_metadatas(
        file_metadatas: List[Dict],
    ) -> List[Dict]:
        res = []
        for file_metadata in file_metadatas:
            fname = file_metadata["name"]
            try:
                _ = FileChangeEventsMessageFileName.from_string(fname)
                res.append(file_metadata)
            except Exception:
                continue
        return res

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
        inbox_folder_id = self._get_inbox_folder_id_as_do(sender_email)
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
            # Store the platform-specific file ID to avoid re-querying when removing
            res.platform_id = first_file_id
            return res

    def _get_inbox_folder_id_as_do(self, sender_email: str) -> str | None:
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

    def _get_inbox_folder_id_as_ds(self, sender_email: str) -> str | None:
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

    def _get_outbox_folder_id_as_do(self, recipient: str) -> str | None:
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

    def _get_outbox_folder_id_as_ds(self, recipient: str) -> str | None:
        """Get DS's outbox folder ID for sending messages to a DO.

        DS-only: Uses DS's own SyftBox folder as parent constraint.
        """
        if recipient in self.ds_outbox_folder_id_cache:
            return self.ds_outbox_folder_id_cache[recipient]

        outbox_folder = GdriveInboxOutBoxFolder(
            sender_email=self.email, recipient_email=recipient
        )

        syftbox_folder_id = self.get_syftbox_folder_id()
        outbox_folder_id = self._find_folder_by_name(
            outbox_folder.as_string(),
            parent_id=syftbox_folder_id,
            owner_email=self.email,
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

        inbox_outbox_id = self._get_outbox_folder_id_as_ds(recipient)
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

    def reset_caches(self):
        self._syftbox_folder_id = None
        self._personal_syftbox_folder_id = None
        self.do_inbox_folder_id_cache.clear()
        self.do_outbox_folder_id_cache.clear()
        self.ds_inbox_folder_id_cache.clear()
        self.ds_outbox_folder_id_cache.clear()
        self.archive_folder_id_cache.clear()
        self.personal_syftbox_event_id_cache.clear()

    def gather_all_file_and_folder_ids(self) -> List[str]:
        syftbox_folder_id = self.get_syftbox_folder_id()
        return gather_all_file_and_folder_ids_recursive(
            self.drive_service, syftbox_folder_id
        )

    def delete_multiple_files_by_ids(
        self, file_ids: List[str], ignore_permissions_errors: bool = True
    ):
        def callback(request_id, response, exception):
            if exception:
                # insufficientFilePermissions is a common error when deleting files that may already beed removed
                # I think (!)
                if ignore_permissions_errors and "insufficientFilePermissions" in str(
                    exception
                ):
                    return
                else:
                    raise exception
            if (
                not isinstance(response, str)
                and response.get("status")
                and int(response.get("status")) >= 400
            ):
                raise Exception(
                    f"Failed to delete {request_id}: error status {response.get('status')}"
                )

        batch = BatchHttpRequest(
            callback=callback, batch_uri="https://www.googleapis.com/batch/drive/v3"
        )

        for file_id in file_ids:
            batch.add(self.drive_service.files().delete(fileId=file_id))
        batch.execute()

    def delete_file_by_id(
        self, file_id: str, verbose: bool = False, raise_on_error: bool = False
    ):
        try:
            self.drive_service.files().delete(fileId=file_id).execute()
        except Exception as e:
            if raise_on_error:
                raise e
            else:
                if verbose:
                    print(f"Error deleting file: {file_id}")

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
        # Create Http with timeout to prevent indefinite hangs
        http = httplib2.Http(timeout=GOOGLE_API_TIMEOUT)
        authorized_http = AuthorizedHttp(self.credentials, http=http)
        drive_service = build("drive", "v3", http=authorized_http)
        request = drive_service.files().get_media(fileId=file_id)

        # Download to memory
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(
            file_buffer, request, chunksize=1024 * 1024 * 10
        )

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
        inbox_folder_id = self._get_inbox_folder_id_as_do(sender_email)
        query = f"name='{name}' and '{inbox_folder_id}' in parents and trashed=false"
        results = (
            self.drive_service.files().list(q=query, fields="files(id, name)").execute()
        )
        items = results.get("files", [])
        return items[0]["id"] if items else None

    def create_dataset_collection_folder(
        self, tag: str, content_hash: str, owner_email: str
    ) -> str:
        """Create /SyftBox/{DATASET_COLLECTION_PREFIX}_{tag}_{hash} folder."""
        folder_obj = DatasetCollectionFolder(tag=tag, content_hash=content_hash)
        folder_name = folder_obj.as_string()
        cache_key = f"{tag}_{content_hash}"

        # Check cache
        if cache_key in self.dataset_collection_folder_id_cache:
            return self.dataset_collection_folder_id_cache[cache_key]

        syftbox_folder_id = self.get_syftbox_folder_id()

        # Check if exists
        folder_id = self._find_folder_by_name(folder_name, parent_id=syftbox_folder_id)
        if folder_id:
            self.dataset_collection_folder_id_cache[cache_key] = folder_id
            return folder_id

        # Create new folder
        folder_id = self.create_folder(folder_name, syftbox_folder_id)
        self.dataset_collection_folder_id_cache[cache_key] = folder_id
        return folder_id

    def share_dataset_collection(
        self, tag: str, content_hash: str, users: list[str] | str
    ) -> None:
        """Share dataset collection folder with users."""
        folder_id = self._get_dataset_collection_folder_id(tag, content_hash)

        share_with_any = False
        if isinstance(users, str):
            if users == SHARE_WITH_ANY:
                share_with_any = True
            else:
                users_list = [users]
        else:
            users_list = users

        if share_with_any:
            # Public access - anyone with link can view
            permission = {"type": "anyone", "role": "reader"}
            self.drive_service.permissions().create(
                fileId=folder_id, body=permission, sendNotificationEmail=False
            ).execute()
        else:
            # Share with specific users (only if list is not empty)
            for user_email in users_list:
                self.add_permission(folder_id, user_email, write=False)
        # else: empty list means no sharing - do nothing

    def upload_dataset_files(
        self, tag: str, content_hash: str, files: dict[str, bytes]
    ) -> None:
        """Upload dataset files to collection folder."""
        folder_id = self._get_dataset_collection_folder_id(tag, content_hash)

        for file_path, content in files.items():
            file_payload, _ = self.create_file_payload(content)
            file_name = Path(file_path).name

            file_metadata = {"name": file_name, "parents": [folder_id]}
            self.drive_service.files().create(
                body=file_metadata, media_body=file_payload, fields="id"
            ).execute()

    def list_dataset_collections_as_do(self) -> list[str]:
        """List collections created by DO (owned by me)."""
        syftbox_folder_id = self.get_syftbox_folder_id()
        query = (
            f"name contains '{DATASET_COLLECTION_PREFIX}_' and '{syftbox_folder_id}' in parents "
            f"and 'me' in owners and trashed=false and mimeType='{GOOGLE_FOLDER_MIME_TYPE}'"
        )
        results = (
            self.drive_service.files().list(q=query, fields="files(name)").execute()
        )

        folders = results.get("files", [])
        return [f["name"].replace(f"{DATASET_COLLECTION_PREFIX}_", "") for f in folders]

    def list_all_dataset_collections_as_do_with_permissions(
        self,
    ) -> list[FileCollection]:
        """List all DO's dataset collections with permissions info."""
        syftbox_folder_id = self.get_syftbox_folder_id()
        query = (
            f"name contains '{DATASET_COLLECTION_PREFIX}_' and '{syftbox_folder_id}' in parents "
            f"and 'me' in owners and trashed=false and mimeType='{GOOGLE_FOLDER_MIME_TYPE}'"
        )
        results = (
            self.drive_service.files().list(q=query, fields="files(id,name)").execute()
        )

        collections = []
        for folder in results.get("files", []):
            folder_id = folder["id"]
            try:
                folder_obj = DatasetCollectionFolder.from_name(folder["name"])
                # Check if folder has "anyone" permission
                perms = (
                    self.drive_service.permissions()
                    .list(fileId=folder_id, fields="permissions(type)")
                    .execute()
                )
                has_anyone = any(
                    p.get("type") == "anyone" for p in perms.get("permissions", [])
                )
                collections.append(
                    FileCollection(
                        folder_id=folder_id,
                        tag=folder_obj.tag,
                        content_hash=folder_obj.content_hash,
                        has_any_permission=has_anyone,
                    )
                )
            except Exception:
                continue

        return collections

    def list_dataset_collections_as_ds(self) -> list[dict]:
        """List collections shared with DS (not owned by me).

        Returns list of dicts with keys: owner_email, tag, content_hash
        """
        query = (
            f"name contains '{DATASET_COLLECTION_PREFIX}_' and not 'me' in owners "
            f"and trashed=false and mimeType='{GOOGLE_FOLDER_MIME_TYPE}'"
        )
        results = (
            self.drive_service.files()
            .list(q=query, fields="files(name, owners)")
            .execute()
        )

        folders = results.get("files", [])
        result = []
        for folder in folders:
            try:
                folder_obj = DatasetCollectionFolder.from_name(folder["name"])
                owner_email = folder.get("owners", [{}])[0].get(
                    "emailAddress", "unknown"
                )
                result.append(
                    {
                        "owner_email": owner_email,
                        "tag": folder_obj.tag,
                        "content_hash": folder_obj.content_hash,
                    }
                )
            except ValueError:
                # Skip folders that don't match the expected format
                continue
        return result

    def download_dataset_collection(
        self, tag: str, content_hash: str, owner_email: str
    ) -> dict[str, bytes]:
        """Download all files from a dataset collection."""
        folder_obj = DatasetCollectionFolder(tag=tag, content_hash=content_hash)
        folder_name = folder_obj.as_string()
        # Try to find folder by name (could be owned by someone else)
        folder_id = self._find_folder_by_name(folder_name, owner_email=owner_email)

        if not folder_id:
            raise ValueError(f"Collection {tag} with hash {content_hash} not found")

        file_metadatas = self.get_file_metadatas_from_folder(folder_id)
        files = {}
        for file_meta in file_metadatas:
            file_id = file_meta["id"]
            file_name = file_meta["name"]
            files[file_name] = self.download_file(file_id)

        return files

    def get_dataset_collection_file_metadatas(
        self, tag: str, content_hash: str, owner_email: str
    ) -> List[Dict]:
        """Get file metadata from a dataset collection without downloading."""
        folder_obj = DatasetCollectionFolder(tag=tag, content_hash=content_hash)
        folder_name = folder_obj.as_string()
        folder_id = self._find_folder_by_name(folder_name, owner_email=owner_email)

        if not folder_id:
            raise ValueError(f"Collection {tag} with hash {content_hash} not found")

        file_metadatas = self.get_file_metadatas_from_folder(folder_id)
        return [{"file_id": f["id"], "file_name": f["name"]} for f in file_metadatas]

    def download_dataset_file(self, file_id: str) -> bytes:
        """Download a single file from a dataset collection."""
        return self.download_file(file_id)

    def _get_dataset_collection_folder_id(self, tag: str, content_hash: str) -> str:
        """Get folder ID for dataset collection, with caching."""
        cache_key = f"{tag}_{content_hash}"
        if cache_key in self.dataset_collection_folder_id_cache:
            return self.dataset_collection_folder_id_cache[cache_key]

        folder_obj = DatasetCollectionFolder(tag=tag, content_hash=content_hash)
        folder_name = folder_obj.as_string()
        syftbox_folder_id = self.get_syftbox_folder_id()
        folder_id = self._find_folder_by_name(folder_name, parent_id=syftbox_folder_id)

        if not folder_id:
            raise ValueError(
                f"Collection folder {tag} with hash {content_hash} not found"
            )

        self.dataset_collection_folder_id_cache[cache_key] = folder_id
        return folder_id

    def _get_version_file_id(self) -> Optional[str]:
        """Find SYFT_version.json file in /SyftBox folder"""
        syftbox_folder_id = self.get_syftbox_folder_id()
        query = f"name='{SYFT_VERSION_FILE}' and '{syftbox_folder_id}' in parents and trashed=false"
        results = self.drive_service.files().list(q=query, fields="files(id)").execute()
        items = results.get("files", [])
        return items[0]["id"] if items else None

    def write_version_file(self, version_info: "VersionInfo") -> None:
        """Write version file to /SyftBox folder. Creates or updates the file."""

        syftbox_folder_id = self.get_syftbox_folder_id()
        file_id = self._get_version_file_id()

        # Convert to JSON string
        json_data = version_info.to_json()
        file_payload, _ = self.create_file_payload(json_data)

        if file_id is None:
            # Create new file
            file_metadata = {
                "name": SYFT_VERSION_FILE,
                "parents": [syftbox_folder_id],
            }
            self.drive_service.files().create(
                body=file_metadata, media_body=file_payload, fields="id"
            ).execute()
        else:
            # Update existing file
            self.drive_service.files().update(
                fileId=file_id, media_body=file_payload
            ).execute()

    def _get_peer_version_file_id(self, peer_email: str) -> Optional[str]:
        """Find SYFT_version.json file in a peer's /SyftBox folder"""
        # Find the peer's SyftBox folder
        query = (
            f"name='{SYFT_VERSION_FILE}' and trashed=false and '{peer_email}' in owners"
        )
        results = self.drive_service.files().list(q=query, fields="files(id)").execute()
        items = results.get("files", [])
        return items[0]["id"] if items else None

    def read_peer_version_file(self, peer_email: str) -> Optional["VersionInfo"]:
        """Read version file from a peer's /SyftBox folder."""
        from syft_client.sync.version.version_info import VersionInfo

        file_id = self._get_peer_version_file_id(peer_email)
        if file_id is None:
            return None

        try:
            file_data = self.download_file(file_id)
            return VersionInfo.from_json(file_data.decode("utf-8"))
        except Exception:
            return None

    def share_version_file_with_peer(self, peer_email: str) -> None:
        """Share the version file with a peer so they can read it."""
        file_id = self._get_version_file_id()
        if file_id is None:
            # Version file doesn't exist yet, create it first
            from syft_client.sync.version.version_info import VersionInfo

            self.write_version_file(VersionInfo.current())
            file_id = self._get_version_file_id()

        if file_id:
            self.add_permission(file_id, peer_email, write=False)
