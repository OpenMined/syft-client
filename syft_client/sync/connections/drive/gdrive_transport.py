"""Google Drive Files transport layer implementation"""

import logging
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
from syft_client.sync.connections.drive.gdrive_retry import (
    execute_with_retries,
    next_chunk_with_retries,
    batch_execute_with_retries,
)

from syft_client.sync.connections.base_connection import (
    FileCollection,
    SyftboxPlatformConnection,
)
from syft_datasets.dataset_manager import (
    DATASET_COLLECTION_PREFIX,
    PRIVATE_DATASET_COLLECTION_PREFIX,
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
from syft_client.sync.checkpoints.checkpoint import (
    Checkpoint,
    IncrementalCheckpoint,
    CHECKPOINT_FILENAME_PREFIX,
    INCREMENTAL_CHECKPOINT_PREFIX,
)
from syft_client.sync.checkpoints.rolling_state import (
    RollingState,
    ROLLING_STATE_FILENAME_PREFIX,
)

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

logging.getLogger("google_auth_httplib2").setLevel(logging.ERROR)


def build_drive_service(
    credentials: GoogleCredentials,
    timeout: int = GOOGLE_API_TIMEOUT,
    environment: Environment | None = None,
):
    """Build a Google Drive service with timeout-enabled authorized HTTP."""
    http = httplib2.Http(timeout=timeout)
    if environment == Environment.COLAB:
        from google.colab import auth as colab_auth
        import google.auth

        colab_auth.authenticate_user()
        creds, _ = google.auth.default()
        authed_http = AuthorizedHttp(creds, http=http)
        # Build service without explicit credentials in Colab
        return build("drive", "v3", http=authed_http)
    else:
        authorized_http = AuthorizedHttp(credentials, http=http)
        return build("drive", "v3", http=authorized_http)


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


class PrivateDatasetCollectionFolder(BaseModel):
    """Represents a private dataset collection folder with format: {prefix}_{tag}_{hash}"""

    tag: str
    content_hash: str

    def as_string(self) -> str:
        return f"{PRIVATE_DATASET_COLLECTION_PREFIX}_{self.tag}_{self.content_hash}"

    @classmethod
    def from_name(cls, name: str) -> "PrivateDatasetCollectionFolder":
        """Parse folder name like 'syft_privatecollection_mytag_abc123'"""
        parts = name.split("_")
        if len(parts) < 3:
            raise ValueError(f"Invalid private collection folder name: {name}")
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

    # Rolling state caches for single-API-call optimization
    _rolling_state_folder_id: str | None = None
    _rolling_state_file_id: str | None = None

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

    @classmethod
    def from_service(cls, email: str, mock_service: Any) -> "GDriveConnection":
        """Create a GDriveConnection using a mock drive service for testing.

        Args:
            email: Email of the user
            mock_service: MockDriveService instance to use instead of real API

        Returns:
            GDriveConnection configured with the mock service
        """
        from syft_client.sync.connections.drive.mock_drive_service import (
            MockDriveService,
        )

        res = cls(email=email, token_path=None)
        if isinstance(mock_service, MockDriveService):
            mock_service = MockDriveService(mock_service._backing_store, email)
        res.setup(drive_service=mock_service)
        return res

    def setup(
        self,
        credentials: GoogleCredentials | None = None,
        drive_service: Any | None = None,
    ):
        """Setup Drive transport with OAuth2 credentials, Colab auth, or mock service.

        Args:
            credentials: OAuth2 credentials for real API access
            drive_service: Drive service instance (e.g., mock for testing)
        """
        self.credentials = credentials
        if drive_service is not None:
            self.drive_service = drive_service
        else:
            self.drive_service = build_drive_service(
                self.credentials, environment=self.environment
            )

        self.get_personal_syftbox_folder_id()
        self._is_setup = True

    def copy(self) -> "GDriveConnection":
        # if is mock
        from syft_client.sync.connections.drive.mock_drive_service import (
            MockDriveService,
        )

        if isinstance(self.drive_service, MockDriveService):
            return GDriveConnection.from_service(self.email, self.drive_service)
        else:
            return GDriveConnection.from_token_path(self.email, self.token_path)

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
        results = execute_with_retries(
            self.drive_service.files().list(
                q=f"name contains '{GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX}' and 'me' in owners and trashed=false"
                f"and mimeType = '{GOOGLE_FOLDER_MIME_TYPE}'"
            )
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
        results = execute_with_retries(
            self.drive_service.files().list(q=query, fields="files(id)")
        )
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
            result = execute_with_retries(
                self.drive_service.files().create(
                    body=file_metadata, media_body=file_payload, fields="id"
                )
            )
            return result.get("id")
        else:
            # Update existing file
            execute_with_retries(
                self.drive_service.files().update(
                    fileId=file_id, media_body=file_payload
                )
            )
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
        results = execute_with_retries(
            self.drive_service.files().list(
                q=f"name contains '{GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX}' and trashed=false "
                f"and mimeType = '{GOOGLE_FOLDER_MIME_TYPE}'"
            )
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

        res = execute_with_retries(
            self.drive_service.files().create(
                body=file_metadata, media_body=file_payload, fields="id"
            )
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

        execute_with_retries(
            self.drive_service.files().create(
                body=file_metadata, media_body=file_payload, fields="id"
            )
        )

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
        file_info = execute_with_retries(
            self.drive_service.files().get(fileId=gdrive_id, fields="parents")
        )
        previous_parents = ",".join(file_info.get("parents", []))
        archive_folder_id = self.get_archive_folder_id_as_do(sender_email)
        execute_with_retries(
            self.drive_service.files().update(
                fileId=gdrive_id,
                addParents=archive_folder_id,
                removeParents=previous_parents,
                fields="id, parents",
                supportsAllDrives=True,
            )
        )

    def add_permission(self, file_id: str, recipient: str, write=False):
        """Add permission to the file"""
        role = "writer" if write else "reader"
        permission = {
            "type": "user",
            "role": role,
            "emailAddress": recipient,
        }
        execute_with_retries(
            self.drive_service.permissions().create(
                fileId=file_id, body=permission, sendNotificationEmail=True
            )
        )

    def create_peer_inbox_folder_as_ds(self, peer_email: str) -> str:
        parent_id = self.get_syftbox_folder_id()
        peer_inbox_folder = GdriveInboxOutBoxFolder(
            sender_email=peer_email, recipient_email=self.email
        )
        folder_name = peer_inbox_folder.as_string()
        print(f"Creating inbox folder for {peer_email} to {self.email} in {parent_id}")
        _id = self.create_folder(folder_name, parent_id)
        return _id

    def create_peer_outbox_folder_as_ds(self, peer_email: str) -> str:
        parent_id = self.get_syftbox_folder_id()
        peer_inbox_folder = GdriveInboxOutBoxFolder(
            sender_email=self.email, recipient_email=peer_email
        )
        folder_name = peer_inbox_folder.as_string()
        print(f"Creating outbox folder for {peer_email} in {parent_id}")
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
        results = execute_with_retries(
            self.drive_service.files().list(q=query, fields="files(id)")
        )
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
            results = execute_with_retries(
                self.drive_service.files().list(
                    q=query,
                    fields="files(id, name, size, mimeType, modifiedTime), nextPageToken",
                    pageSize=page_size,
                    pageToken=page_token,
                    orderBy="name desc",
                )
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

        execute_with_retries(
            self.drive_service.files().create(
                body=file_metadata, media_body=payload, fields="id"
            )
        )

    def reset_caches(self):
        self._syftbox_folder_id = None
        self._personal_syftbox_folder_id = None
        self.do_inbox_folder_id_cache.clear()
        self.do_outbox_folder_id_cache.clear()
        self.ds_inbox_folder_id_cache.clear()
        self.ds_outbox_folder_id_cache.clear()
        self.archive_folder_id_cache.clear()
        self.personal_syftbox_event_id_cache.clear()
        self.dataset_collection_folder_id_cache.clear()
        self._rolling_state_folder_id = None
        self._rolling_state_file_id = None

    def gather_all_file_and_folder_ids(self) -> List[str]:
        syftbox_folder_id = self.get_syftbox_folder_id()
        return gather_all_file_and_folder_ids_recursive(
            self.drive_service, syftbox_folder_id
        )

    def delete_multiple_files_by_ids(
        self,
        file_ids: List[str],
        ignore_permissions_errors: bool = True,
        ignore_file_not_found: bool = True,
    ):
        def callback(request_id, response, exception):
            if exception:
                exception_str = str(exception)
                # insufficientFilePermissions is a common error when deleting files that may already be removed
                if (
                    ignore_permissions_errors
                    and "insufficientFilePermissions" in exception_str
                ):
                    return
                # 404 errors occur when files are already deleted
                if ignore_file_not_found and (
                    "404" in exception_str or "notFound" in exception_str
                ):
                    return
                raise exception
            if (
                not isinstance(response, str)
                and response.get("status")
                and int(response.get("status")) >= 400
            ):
                raise Exception(
                    f"Failed to delete {request_id}: error status {response.get('status')}"
                )

        # Google Drive batch API has a limit of 100 requests per batch
        BATCH_SIZE = 100
        for i in range(0, len(file_ids), BATCH_SIZE):
            chunk = file_ids[i : i + BATCH_SIZE]
            batch = BatchHttpRequest(
                callback=callback, batch_uri="https://www.googleapis.com/batch/drive/v3"
            )
            for file_id in chunk:
                batch.add(self.drive_service.files().delete(fileId=file_id))
            batch_execute_with_retries(batch)

    def delete_file_by_id(
        self, file_id: str, verbose: bool = False, raise_on_error: bool = False
    ):
        try:
            execute_with_retries(self.drive_service.files().delete(fileId=file_id))
        except Exception as e:
            if raise_on_error:
                raise e
            else:
                if verbose:
                    print(f"Error deleting file: {file_id}")

    def find_orphaned_message_files(self) -> list[str]:
        """
        Find syft files by name pattern owned by user, regardless of parent folder.

        Due to Google Drive's eventual consistency, files can become orphaned when
        their parent folder is deleted before they're fully registered. This method
        finds such files by searching for name patterns regardless of parent.

        Returns list of file IDs.
        """
        patterns = [
            "syfteventsmessagev3_",  # event messages
            "msgv2_",  # proposed file change messages
            CHECKPOINT_FILENAME_PREFIX,  # checkpoint and incremental checkpoint files
            ROLLING_STATE_FILENAME_PREFIX,  # rolling state files
        ]
        file_ids = []

        for pattern in patterns:
            query = f"name contains '{pattern}' and 'me' in owners and trashed=false"
            page_token = None

            while True:
                results = execute_with_retries(
                    self.drive_service.files().list(
                        q=query,
                        fields="files(id), nextPageToken",
                        pageToken=page_token,
                    )
                )

                for item in results.get("files", []):
                    file_ids.append(item["id"])

                page_token = results.get("nextPageToken")
                if not page_token:
                    break

        return file_ids

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

        results = execute_with_retries(
            self.drive_service.files().list(q=query, fields="files(id)", pageSize=1)
        )
        items = results.get("files", [])
        return items[0]["id"] if items else None

    def download_file(self, file_id: str) -> bytes:
        request = self.drive_service.files().get_media(fileId=file_id)

        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(
            file_buffer, request, chunksize=1024 * 1024 * 10
        )

        done = False
        while not done:
            status, done = next_chunk_with_retries(downloader)

        message_data = file_buffer.getvalue()
        return message_data

    def create_folder(self, folder_name: str, parent_id: str) -> str:
        file_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            file_metadata["parents"] = [parent_id]
        folder = execute_with_retries(
            self.drive_service.files().create(body=file_metadata, fields="id")
        )
        return folder.get("id")

    def get_syftbox_folder_id_from_drive(self) -> str | None:
        query = f"name='{SYFTBOX_FOLDER}' and mimeType='application/vnd.google-apps.folder' and 'me' in owners and trashed=false"
        results = execute_with_retries(
            self.drive_service.files().list(q=query, fields="files(id, name)")
        )
        items = results.get("files", [])
        return items[0]["id"] if items else None

    def get_inbox_proposed_event_id_from_name(
        self, sender_email: str, name: str
    ) -> str | None:
        inbox_folder_id = self._get_inbox_folder_id_as_do(sender_email)
        query = f"name='{name}' and '{inbox_folder_id}' in parents and trashed=false"
        results = execute_with_retries(
            self.drive_service.files().list(q=query, fields="files(id, name)")
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

    def tag_dataset_collection_as_any(self, tag: str, content_hash: str) -> None:
        """Mark dataset collection as shared with 'any' via appProperties."""
        folder_id = self._get_dataset_collection_folder_id(tag, content_hash)
        execute_with_retries(
            self.drive_service.files().update(
                fileId=folder_id,
                body={"appProperties": {"syft_shared_with_any": "true"}},
            )
        )

    def share_dataset_collection(
        self, tag: str, content_hash: str, users: list[str]
    ) -> None:
        """Share dataset collection folder with specific users via batch API."""
        if not users:
            return
        folder_id = self._get_dataset_collection_folder_id(tag, content_hash)
        self._batch_add_permissions(folder_id, users)

    def _batch_add_permissions(self, file_id: str, users: list[str]) -> None:
        """Add reader permissions for multiple users in a single batch request."""

        def callback(request_id, response, exception):
            if exception:
                # Ignore "already shared" errors
                if "alreadyShared" not in str(exception):
                    raise exception

        BATCH_SIZE = 100
        for i in range(0, len(users), BATCH_SIZE):
            chunk = users[i : i + BATCH_SIZE]
            batch = self.drive_service.new_batch_http_request(callback=callback)
            for user_email in chunk:
                permission = {
                    "type": "user",
                    "role": "reader",
                    "emailAddress": user_email,
                }
                batch.add(
                    self.drive_service.permissions().create(
                        fileId=file_id,
                        body=permission,
                        sendNotificationEmail=True,
                    )
                )
            batch_execute_with_retries(batch)

    def upload_dataset_files(
        self, tag: str, content_hash: str, files: dict[str, bytes]
    ) -> None:
        """Upload dataset files to collection folder."""
        folder_id = self._get_dataset_collection_folder_id(tag, content_hash)

        for file_path, content in files.items():
            file_payload, _ = self.create_file_payload(content)
            file_name = Path(file_path).name

            file_metadata = {"name": file_name, "parents": [folder_id]}
            execute_with_retries(
                self.drive_service.files().create(
                    body=file_metadata, media_body=file_payload, fields="id"
                )
            )

    def list_dataset_collections_as_do(self) -> list[str]:
        """List collections created by DO (owned by me)."""
        syftbox_folder_id = self.get_syftbox_folder_id()
        query = (
            f"name contains '{DATASET_COLLECTION_PREFIX}_' and '{syftbox_folder_id}' in parents "
            f"and 'me' in owners and trashed=false and mimeType='{GOOGLE_FOLDER_MIME_TYPE}'"
        )
        results = execute_with_retries(
            self.drive_service.files().list(q=query, fields="files(name)")
        )

        folders = results.get("files", [])
        result = []
        for folder in folders:
            try:
                folder_obj = DatasetCollectionFolder.from_name(folder["name"])
                result.append(folder_obj.tag)
            except ValueError:
                continue
        return result

    def list_all_dataset_collections_as_do_with_permissions(
        self,
    ) -> list[FileCollection]:
        """List all DO's dataset collections with permissions info."""
        syftbox_folder_id = self.get_syftbox_folder_id()
        query = (
            f"name contains '{DATASET_COLLECTION_PREFIX}_' and '{syftbox_folder_id}' in parents "
            f"and 'me' in owners and trashed=false and mimeType='{GOOGLE_FOLDER_MIME_TYPE}'"
        )
        results = execute_with_retries(
            self.drive_service.files().list(
                q=query, fields="files(id,name,appProperties)"
            )
        )

        collections = []
        for folder in results.get("files", []):
            folder_id = folder["id"]
            try:
                folder_obj = DatasetCollectionFolder.from_name(folder["name"])
                has_anyone = (
                    folder.get("appProperties", {}).get("syft_shared_with_any")
                    == "true"
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
        results = execute_with_retries(
            self.drive_service.files().list(q=query, fields="files(name, owners)")
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

    # =========================================================================
    # PRIVATE DATASET COLLECTION METHODS
    # =========================================================================

    def create_private_dataset_collection_folder(
        self, tag: str, content_hash: str, owner_email: str
    ) -> str:
        """Create /SyftBox/{PRIVATE_DATASET_COLLECTION_PREFIX}_{tag}_{hash} folder.

        No sharing is applied — only the owner can access this folder.
        """
        folder_obj = PrivateDatasetCollectionFolder(tag=tag, content_hash=content_hash)
        folder_name = folder_obj.as_string()
        cache_key = f"private_{tag}_{content_hash}"

        if cache_key in self.dataset_collection_folder_id_cache:
            return self.dataset_collection_folder_id_cache[cache_key]

        syftbox_folder_id = self.get_syftbox_folder_id()
        folder_id = self._find_folder_by_name(folder_name, parent_id=syftbox_folder_id)
        if folder_id:
            self.dataset_collection_folder_id_cache[cache_key] = folder_id
            return folder_id

        folder_id = self.create_folder(folder_name, syftbox_folder_id)
        self.dataset_collection_folder_id_cache[cache_key] = folder_id
        return folder_id

    def upload_private_dataset_files(
        self, tag: str, content_hash: str, files: dict[str, bytes]
    ) -> None:
        """Upload files to a private dataset collection folder."""
        folder_id = self._get_private_collection_folder_id(tag, content_hash)
        for file_path, content in files.items():
            file_payload, _ = self.create_file_payload(content)
            file_name = Path(file_path).name
            file_metadata = {"name": file_name, "parents": [folder_id]}
            execute_with_retries(
                self.drive_service.files().create(
                    body=file_metadata, media_body=file_payload, fields="id"
                )
            )

    def list_private_dataset_collections_as_do(self) -> list[FileCollection]:
        """List private collections owned by DO."""
        syftbox_folder_id = self.get_syftbox_folder_id()
        query = (
            f"name contains '{PRIVATE_DATASET_COLLECTION_PREFIX}_' "
            f"and '{syftbox_folder_id}' in parents "
            f"and 'me' in owners and trashed=false "
            f"and mimeType='{GOOGLE_FOLDER_MIME_TYPE}'"
        )
        results = execute_with_retries(
            self.drive_service.files().list(q=query, fields="files(id,name)")
        )

        collections = []
        for folder in results.get("files", []):
            try:
                folder_obj = PrivateDatasetCollectionFolder.from_name(folder["name"])
                collections.append(
                    FileCollection(
                        folder_id=folder["id"],
                        tag=folder_obj.tag,
                        content_hash=folder_obj.content_hash,
                    )
                )
            except ValueError:
                continue
        return collections

    def get_private_collection_file_metadatas(
        self, tag: str, content_hash: str, owner_email: str
    ) -> List[Dict]:
        """Get file metadata from a private dataset collection without downloading."""
        folder_obj = PrivateDatasetCollectionFolder(tag=tag, content_hash=content_hash)
        folder_name = folder_obj.as_string()
        folder_id = self._find_folder_by_name(folder_name, owner_email=owner_email)

        if not folder_id:
            raise ValueError(
                f"Private collection {tag} with hash {content_hash} not found"
            )

        file_metadatas = self.get_file_metadatas_from_folder(folder_id)
        return [{"file_id": f["id"], "file_name": f["name"]} for f in file_metadatas]

    def _get_private_collection_folder_id(self, tag: str, content_hash: str) -> str:
        """Get folder ID for private dataset collection, with caching."""
        cache_key = f"private_{tag}_{content_hash}"
        if cache_key in self.dataset_collection_folder_id_cache:
            return self.dataset_collection_folder_id_cache[cache_key]

        folder_obj = PrivateDatasetCollectionFolder(tag=tag, content_hash=content_hash)
        folder_name = folder_obj.as_string()
        syftbox_folder_id = self.get_syftbox_folder_id()
        folder_id = self._find_folder_by_name(folder_name, parent_id=syftbox_folder_id)

        if not folder_id:
            raise ValueError(
                f"Private collection folder {tag} with hash {content_hash} not found"
            )

        self.dataset_collection_folder_id_cache[cache_key] = folder_id
        return folder_id

    def _get_version_file_id(self) -> Optional[str]:
        """Find SYFT_version.json file in /SyftBox folder"""
        syftbox_folder_id = self.get_syftbox_folder_id()
        query = f"name='{SYFT_VERSION_FILE}' and '{syftbox_folder_id}' in parents and trashed=false"
        results = execute_with_retries(
            self.drive_service.files().list(q=query, fields="files(id)")
        )
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
            execute_with_retries(
                self.drive_service.files().create(
                    body=file_metadata, media_body=file_payload, fields="id"
                )
            )
        else:
            # Update existing file
            execute_with_retries(
                self.drive_service.files().update(
                    fileId=file_id, media_body=file_payload
                )
            )

    def _get_peer_version_file_id(self, peer_email: str) -> Optional[str]:
        """Find SYFT_version.json file in a peer's /SyftBox folder"""
        # Find the peer's SyftBox folder
        query = (
            f"name='{SYFT_VERSION_FILE}' and trashed=false and '{peer_email}' in owners"
        )
        results = execute_with_retries(
            self.drive_service.files().list(q=query, fields="files(id)")
        )
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

    # =========================================================================
    # CHECKPOINT METHODS
    # =========================================================================

    def _get_checkpoints_folder_name(self) -> str:
        """Get the checkpoints folder name: {email}-checkpoints"""
        return f"{self.email}-checkpoints"

    def _get_checkpoints_folder_id(self) -> str | None:
        """Find the checkpoints folder ID from Google Drive."""
        folder_name = self._get_checkpoints_folder_name()
        syftbox_folder_id = self.get_syftbox_folder_id()
        query = (
            f"name='{folder_name}' and mimeType='{GOOGLE_FOLDER_MIME_TYPE}' "
            f"and '{syftbox_folder_id}' in parents and trashed=false"
        )
        results = self.drive_service.files().list(q=query, fields="files(id)").execute()
        items = results.get("files", [])
        return items[0]["id"] if items else None

    def _get_or_create_checkpoints_folder_id(self) -> str:
        """Get or create the checkpoints folder."""
        folder_id = self._get_checkpoints_folder_id()
        if folder_id is not None:
            return folder_id
        # Create the folder
        folder_name = self._get_checkpoints_folder_name()
        syftbox_folder_id = self.get_syftbox_folder_id()
        return self.create_folder(folder_name, syftbox_folder_id)

    def upload_checkpoint(self, checkpoint: Checkpoint) -> str:
        """
        Upload a checkpoint to Google Drive.

        Uploads the new checkpoint first, then deletes old ones.
        This ensures we never lose checkpoint data if the upload fails.

        Returns:
            The Google Drive file ID of the uploaded checkpoint.
        """
        # Get or create checkpoints folder
        folder_id = self._get_or_create_checkpoints_folder_id()

        # Compress and upload new checkpoint first
        compressed_data = checkpoint.as_compressed_data()
        payload, _ = self.create_file_payload(compressed_data)

        file_metadata = {
            "name": checkpoint.filename,
            "parents": [folder_id],
        }

        result = (
            self.drive_service.files()
            .create(body=file_metadata, media_body=payload, fields="id")
            .execute()
        )

        # Only delete old checkpoints after successful upload
        self.delete_all_checkpoints(exclude_file_id=result.get("id"))

        return result.get("id")

    def get_latest_checkpoint(self) -> Checkpoint | None:
        """
        Download the latest checkpoint from Google Drive.

        Returns:
            The Checkpoint object, or None if no checkpoint exists.
        """
        folder_id = self._get_checkpoints_folder_id()
        if folder_id is None:
            return None

        # List checkpoint files
        query = (
            f"'{folder_id}' in parents and trashed=false "
            f"and name contains '{CHECKPOINT_FILENAME_PREFIX}'"
        )
        results = (
            self.drive_service.files().list(q=query, fields="files(id, name)").execute()
        )
        items = results.get("files", [])

        if not items:
            return None

        # Find the latest checkpoint by timestamp in filename
        latest_file = None
        latest_timestamp = -1.0

        for item in items:
            timestamp = Checkpoint.filename_to_timestamp(item["name"])
            if timestamp is not None and timestamp > latest_timestamp:
                latest_timestamp = timestamp
                latest_file = item

        if latest_file is None:
            return None

        # Download the checkpoint
        try:
            file_data = self.download_file(latest_file["id"])
            return Checkpoint.from_compressed_data(file_data)
        except Exception as e:
            print(f"Warning: Failed to load checkpoint: {e}")
            return None

    def delete_all_checkpoints(self, exclude_file_id: str | None = None):
        """Delete all existing full checkpoints (not incremental ones).

        Args:
            exclude_file_id: If provided, skip deleting this file ID
                (used to preserve a newly uploaded checkpoint).
        """
        folder_id = self._get_checkpoints_folder_id()
        if folder_id is None:
            return

        # List only full checkpoint files (start with "checkpoint_" not "incremental_checkpoint_")
        query = (
            f"'{folder_id}' in parents and trashed=false "
            f"and name contains '{CHECKPOINT_FILENAME_PREFIX}'"
        )
        results = (
            self.drive_service.files().list(q=query, fields="files(id, name)").execute()
        )
        items = results.get("files", [])

        # Delete only full checkpoints (not incremental ones)
        for item in items:
            if item["name"].startswith(INCREMENTAL_CHECKPOINT_PREFIX):
                continue  # Skip incremental checkpoints
            if item["id"] == exclude_file_id:
                continue  # Skip the newly uploaded checkpoint
            try:
                self.drive_service.files().delete(fileId=item["id"]).execute()
            except Exception as e:
                print(f"Warning: Failed to delete checkpoint {item['name']}: {e}")

    # =========================================================================
    # INCREMENTAL CHECKPOINT METHODS
    # =========================================================================

    def upload_incremental_checkpoint(self, checkpoint: IncrementalCheckpoint) -> str:
        """
        Upload an incremental checkpoint to Google Drive.

        Does NOT delete existing incremental checkpoints - they accumulate
        until compacting is triggered.

        Returns:
            The Google Drive file ID of the uploaded checkpoint.
        """
        folder_id = self._get_or_create_checkpoints_folder_id()

        compressed_data = checkpoint.as_compressed_data()
        payload, _ = self.create_file_payload(compressed_data)

        file_metadata = {
            "name": checkpoint.filename,
            "parents": [folder_id],
        }

        result = (
            self.drive_service.files()
            .create(body=file_metadata, media_body=payload, fields="id")
            .execute()
        )
        return result.get("id")

    def get_all_incremental_checkpoints(self) -> List[IncrementalCheckpoint]:
        """
        Download all incremental checkpoints from Google Drive.

        Returns:
            List of IncrementalCheckpoint objects, sorted by sequence number.
        """
        folder_id = self._get_checkpoints_folder_id()
        if folder_id is None:
            return []

        # List only incremental checkpoint files
        query = (
            f"'{folder_id}' in parents and trashed=false "
            f"and name contains '{INCREMENTAL_CHECKPOINT_PREFIX}'"
        )
        results = (
            self.drive_service.files().list(q=query, fields="files(id, name)").execute()
        )
        items = results.get("files", [])

        if not items:
            return []

        checkpoints = []
        for item in items:
            try:
                file_data = self.download_file(item["id"])
                cp = IncrementalCheckpoint.from_compressed_data(file_data)
                checkpoints.append(cp)
            except Exception as e:
                print(
                    f"Warning: Failed to load incremental checkpoint {item['name']}: {e}"
                )
                continue

        # Sort by sequence number
        return sorted(checkpoints, key=lambda c: c.sequence_number)

    def get_incremental_checkpoint_count(self) -> int:
        """Get the number of incremental checkpoints on Google Drive."""
        folder_id = self._get_checkpoints_folder_id()
        if folder_id is None:
            return 0

        query = (
            f"'{folder_id}' in parents and trashed=false "
            f"and name contains '{INCREMENTAL_CHECKPOINT_PREFIX}'"
        )
        results = self.drive_service.files().list(q=query, fields="files(id)").execute()
        return len(results.get("files", []))

    def get_next_incremental_sequence_number(self) -> int:
        """Get the next sequence number for incremental checkpoints."""
        folder_id = self._get_checkpoints_folder_id()
        if folder_id is None:
            return 1

        query = (
            f"'{folder_id}' in parents and trashed=false "
            f"and name contains '{INCREMENTAL_CHECKPOINT_PREFIX}'"
        )
        results = (
            self.drive_service.files().list(q=query, fields="files(name)").execute()
        )
        items = results.get("files", [])

        if not items:
            return 1

        # Find highest sequence number
        max_seq = 0
        for item in items:
            seq = IncrementalCheckpoint.filename_to_sequence_number(item["name"])
            if seq is not None and seq > max_seq:
                max_seq = seq

        return max_seq + 1

    def delete_all_incremental_checkpoints(self) -> None:
        """Delete all incremental checkpoints (called after compacting)."""
        folder_id = self._get_checkpoints_folder_id()
        if folder_id is None:
            return

        query = (
            f"'{folder_id}' in parents and trashed=false "
            f"and name contains '{INCREMENTAL_CHECKPOINT_PREFIX}'"
        )
        results = (
            self.drive_service.files().list(q=query, fields="files(id, name)").execute()
        )
        items = results.get("files", [])

        for item in items:
            try:
                self.drive_service.files().delete(fileId=item["id"]).execute()
            except Exception as e:
                print(
                    f"Warning: Failed to delete incremental checkpoint {item['name']}: {e}"
                )

    def get_events_count_since_checkpoint(
        self, checkpoint_timestamp: float | None
    ) -> int:
        """
        Count events created after the checkpoint timestamp.

        Args:
            checkpoint_timestamp: The timestamp of the checkpoint, or None for all events.

        Returns:
            Number of events since the checkpoint.
        """
        personal_folder_id = self.get_personal_syftbox_folder_id()
        file_metadatas = self.get_file_metadatas_from_folder(personal_folder_id)

        if checkpoint_timestamp is None:
            # Count all events
            return len(
                [
                    f
                    for f in file_metadatas
                    if f["name"].startswith("syfteventsmessagev3_")
                ]
            )

        # Count events after checkpoint
        count = 0
        for f in file_metadatas:
            if not f["name"].startswith("syfteventsmessagev3_"):
                continue
            event_timestamp = self._extract_timestamp_from_filename(f["name"])
            if event_timestamp is not None and event_timestamp > checkpoint_timestamp:
                count += 1
        return count

    def get_events_messages_since_timestamp(
        self, since_timestamp: float
    ) -> List[FileChangeEventsMessage]:
        """
        Get events created after a specific timestamp.

        Used to get events created after a checkpoint.

        Args:
            since_timestamp: Only return events with timestamp > this value.

        Returns:
            List of FileChangeEventsMessage created after the timestamp.
        """
        personal_folder_id = self.get_personal_syftbox_folder_id()
        file_metadatas = self.get_file_metadatas_from_folder(
            personal_folder_id, since_timestamp=since_timestamp
        )

        # Filter to valid event files
        valid_fname_objs = self._get_valid_events_from_file_metadatas(file_metadatas)

        result = []
        for fname_obj in valid_fname_objs:
            # Only include events after the timestamp
            if fname_obj.timestamp <= since_timestamp:
                continue

            gdrive_id = [
                f for f in file_metadatas if f["name"] == fname_obj.as_string()
            ][0]["id"]

            try:
                file_data = self.download_file(gdrive_id)
                event = FileChangeEventsMessage.from_compressed_data(file_data)
                result.append(event)
            except Exception as e:
                print(f"Warning: Failed to download event: {e}")
                continue

        return result

    # =========================================================================
    # ROLLING STATE METHODS
    # =========================================================================

    def _get_rolling_state_folder_name(self) -> str:
        """Get the rolling state folder name: {email}-rolling-state"""
        return f"{self.email}-rolling-state"

    def _get_rolling_state_folder_id(self, use_cache: bool = True) -> str | None:
        """
        Find the rolling state folder ID from Google Drive.

        Args:
            use_cache: If True, return cached value if available.
        """
        if use_cache and self._rolling_state_folder_id is not None:
            return self._rolling_state_folder_id

        folder_name = self._get_rolling_state_folder_name()
        syftbox_folder_id = self.get_syftbox_folder_id()
        query = (
            f"name='{folder_name}' and mimeType='{GOOGLE_FOLDER_MIME_TYPE}' "
            f"and '{syftbox_folder_id}' in parents and trashed=false"
        )
        results = self.drive_service.files().list(q=query, fields="files(id)").execute()
        items = results.get("files", [])
        if items:
            self._rolling_state_folder_id = items[0]["id"]
            return self._rolling_state_folder_id
        return None

    def _get_or_create_rolling_state_folder_id(self) -> str:
        """Get or create the rolling state folder."""
        folder_id = self._get_rolling_state_folder_id()
        if folder_id is not None:
            return folder_id
        # Create the folder
        folder_name = self._get_rolling_state_folder_name()
        syftbox_folder_id = self.get_syftbox_folder_id()
        folder_id = self.create_folder(folder_name, syftbox_folder_id)
        self._rolling_state_folder_id = folder_id
        return folder_id

    def upload_rolling_state(self, rolling_state: RollingState) -> str:
        """
        Upload rolling state to Google Drive.

        Optimized to use a single API call when possible:
        - If file ID is cached, uses update() (1 API call)
        - If file ID not cached, uses create() (1-2 API calls)
        - Falls back to create() if update() fails

        Args:
            rolling_state: The RollingState object to upload.

        Returns:
            The Google Drive file ID of the uploaded rolling state.
        """
        compressed_data = rolling_state.as_compressed_data()
        payload, _ = self.create_file_payload(compressed_data)

        # Try to update existing file if we have a cached ID
        if self._rolling_state_file_id is not None:
            try:
                # Update existing file (1 API call)
                self.drive_service.files().update(
                    fileId=self._rolling_state_file_id,
                    media_body=payload,
                ).execute()
                return self._rolling_state_file_id
            except Exception:
                # File was deleted externally, fall back to create
                self._rolling_state_file_id = None

        # Get or create rolling state folder
        folder_id = self._get_or_create_rolling_state_folder_id()

        # Create new file
        file_metadata = {
            "name": rolling_state.filename,
            "parents": [folder_id],
        }

        result = (
            self.drive_service.files()
            .create(body=file_metadata, media_body=payload, fields="id")
            .execute()
        )
        file_id = result.get("id")
        self._rolling_state_file_id = file_id
        return file_id

    def get_rolling_state(self) -> RollingState | None:
        """
        Download the rolling state from Google Drive.

        Also populates the folder and file ID caches for subsequent uploads.

        Returns:
            The RollingState object, or None if no rolling state exists.
        """
        folder_id = self._get_rolling_state_folder_id()
        if folder_id is None:
            return None

        # List rolling state files
        query = (
            f"'{folder_id}' in parents and trashed=false "
            f"and name contains '{ROLLING_STATE_FILENAME_PREFIX}'"
        )
        results = (
            self.drive_service.files().list(q=query, fields="files(id, name)").execute()
        )
        items = results.get("files", [])

        if not items:
            return None

        # Find the latest rolling state by timestamp in filename
        latest_file = None
        latest_timestamp = -1.0

        for item in items:
            timestamp = RollingState.filename_to_timestamp(item["name"])
            if timestamp is not None and timestamp > latest_timestamp:
                latest_timestamp = timestamp
                latest_file = item

        if latest_file is None:
            return None

        # Cache the file ID for subsequent uploads
        self._rolling_state_file_id = latest_file["id"]

        # Download the rolling state
        try:
            file_data = self.download_file(latest_file["id"])
            return RollingState.from_compressed_data(file_data)
        except Exception as e:
            print(f"Warning: Failed to load rolling state: {e}")
            self._rolling_state_file_id = None
            return None

    def delete_rolling_state(self) -> None:
        """Delete all existing rolling state files and clear cache."""
        # Clear the file ID cache
        self._rolling_state_file_id = None

        folder_id = self._get_rolling_state_folder_id()
        if folder_id is None:
            return

        # List all rolling state files
        query = (
            f"'{folder_id}' in parents and trashed=false "
            f"and name contains '{ROLLING_STATE_FILENAME_PREFIX}'"
        )
        results = (
            self.drive_service.files().list(q=query, fields="files(id, name)").execute()
        )
        items = results.get("files", [])

        # Delete each rolling state file
        for item in items:
            try:
                self.drive_service.files().delete(fileId=item["id"]).execute()
            except Exception as e:
                print(f"Warning: Failed to delete rolling state {item['name']}: {e}")
