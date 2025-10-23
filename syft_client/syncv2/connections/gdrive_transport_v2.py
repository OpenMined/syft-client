"""Google Drive Files transport layer implementation"""

import io
import json
import io
import pickle
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from syft_client.syncv2.syftbox_utils import compress_data, uncompress_data
from syft_client.syncv2.messages.proposed_filechange import (
    ProposedFileChangesMessage,
    ProposedFileChange,
)

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload
from googleapiclient.http import MediaIoBaseDownload
import logging
from pydantic import BaseModel, Field
import uuid

from syft_client.environment import Environment
from syft_client.transports.base import BaseTransport
from syft_client.platforms.transport_base import BaseTransportLayer


GOOGLE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


class GdriveInboxOutBoxFolder(BaseModel):
    sender_email: str
    recipient_email: str

    def as_string(self) -> str:
        return f"syft_{self.sender_email}_to_{self.recipient_email}_outbox_inbox"


class GDriveFilesTransport(BaseTransportLayer, BaseTransport):
    """Google Drive Files API transport layer"""

    # STATIC Attributes
    is_keystore = True  # GDrive can store auth keys
    is_notification_layer = False  # Users don't regularly check Drive
    is_html_compatible = False  # File storage, not rendering
    is_reply_compatible = False  # No native reply mechanism
    guest_submit = False  # Requires Google account
    guest_read_file = True  # Can share files publicly
    guest_read_folder = True  # Can share folders publicly

    # Syft folder name
    SYFT_FOLDER = "SyftClient"

    def __init__(self, email: str):
        """Initialize Drive transport"""
        super().__init__(email)
        self.drive_service = None
        self.credentials = None
        self._folder_id = None
        self._setup_verified = False
        self._contacts_folder_id = None
        self._syftbox_folder_id = None
        self.verbose = True  # Default verbose mode
        self.outbox_folder_cache = {}
        self.inbox_folder_cache = {}

    def add_peer(self, email: str) -> bool:
        raise NotImplementedError(
            "add_peer is not implemented for GDriveFilesTransport"
        )

    def list_peers(self) -> List[str]:
        raise NotImplementedError(
            "list_peers is not implemented for GDriveFilesTransport"
        )

    def remove_peer(self, email: str) -> bool:
        raise NotImplementedError(
            "remove_peer is not implemented for GDriveFilesTransport"
        )

    def send(self, archive_path: str, recipient: str) -> bool:
        raise NotImplementedError("send_to is not implemented for GDriveFilesTransport")

    def receive(self) -> List[ProposedFileChangesMessage]:
        pass

    @staticmethod
    def check_api_enabled(platform_client: Any) -> bool:
        """
        Check if Google Drive API is enabled.

        Args:
            platform_client: The platform client with credentials

        Returns:
            bool: True if API is enabled, False otherwise
        """
        # Suppress googleapiclient warnings during API check
        googleapi_logger = logging.getLogger("googleapiclient.http")
        original_level = googleapi_logger.level
        googleapi_logger.setLevel(logging.ERROR)

        try:
            # Check if we're in Colab environment
            if hasattr(platform_client, "current_environment"):
                from syft_client.environment import Environment

                if platform_client.current_environment == Environment.COLAB:
                    # In Colab, try to use the API directly without credentials
                    try:
                        from googleapiclient.discovery import build

                        drive_service = build("drive", "v3")
                        drive_service.about().get(fields="user").execute()
                        return True
                    except Exception:
                        return False

            # Regular OAuth credential check
            if (
                not hasattr(platform_client, "credentials")
                or not platform_client.credentials
            ):
                return False

            # Try to build service and make a simple API call
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            # Refresh credentials if needed
            if (
                platform_client.credentials.expired
                and platform_client.credentials.refresh_token
            ):
                platform_client.credentials.refresh(Request())

            drive_service = build(
                "drive", "v3", credentials=platform_client.credentials
            )
            drive_service.about().get(fields="user").execute()
            return True
        except Exception:
            return False
        finally:
            googleapi_logger.setLevel(original_level)

    @staticmethod
    def enable_api_static(
        transport_name: str, email: str, project_id: Optional[str] = None
    ) -> None:
        """Show instructions for enabling Google Drive API"""
        print(f"\n🔧 To enable the Google Drive API:")
        print(f"\n1. Open this URL in your browser:")
        if project_id:
            print(
                f"   https://console.cloud.google.com/marketplace/product/google/drive.googleapis.com?authuser={email}&project={project_id}"
            )
        else:
            print(
                f"   https://console.cloud.google.com/marketplace/product/google/drive.googleapis.com?authuser={email}"
            )
        print(f"\n2. Click the 'Enable' button")
        print(f"\n3. Wait for the API to be enabled (may take 5-10 seconds)")
        print(
            f"\n📝 Note: API tends to flicker for 5-10 seconds before enabling/disabling"
        )

    @staticmethod
    def disable_api_static(
        transport_name: str, email: str, project_id: Optional[str] = None
    ) -> None:
        """Show instructions for disabling Google Drive API"""
        print(f"\n🔧 To disable the Google Drive API:")
        print(f"\n1. Open this URL in your browser:")
        if project_id:
            print(
                f"   https://console.cloud.google.com/apis/api/drive.googleapis.com/overview?authuser={email}&project={project_id}"
            )
        else:
            print(
                f"   https://console.cloud.google.com/apis/api/drive.googleapis.com/overview?authuser={email}"
            )
        print(f"\n2. Click 'Manage' or 'Disable API'")
        print(f"\n3. Confirm by clicking 'Disable'")
        print(
            f"\n📝 Note: API tends to flicker for 5-10 seconds before enabling/disabling"
        )

    @property
    def api_is_active_by_default(self) -> bool:
        """GDrive API active by default in Colab"""
        return self.environment == Environment.COLAB

    @property
    def login_complexity(self) -> int:
        """Additional GDrive setup complexity (after Google auth)"""
        # If already set up, no steps remaining
        if self.is_setup():
            return 0

        if self.api_is_active:
            return 0  # No additional setup

        # In Colab, Drive API is pre-enabled
        if self.environment == Environment.COLAB:
            return 0  # No additional setup needed
        else:
            # Need to enable Drive API in Console
            return 1  # One additional step

    def setup(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """Setup Drive transport with OAuth2 credentials or Colab auth"""
        try:
            # Check if we're in Colab and can use automatic auth
            if self.environment == Environment.COLAB:
                try:
                    from google.colab import auth as colab_auth

                    colab_auth.authenticate_user()
                    # Build service without explicit credentials in Colab
                    self.drive_service = build("drive", "v3")
                    self.credentials = None  # No explicit credentials in Colab
                except ImportError:
                    # Fallback to regular credentials if Colab auth not available
                    if credentials is None:
                        return False
                    if not credentials or "credentials" not in credentials:
                        return False
                    self.credentials = credentials["credentials"]
                    self.drive_service = build(
                        "drive", "v3", credentials=self.credentials
                    )
            else:
                # Regular OAuth2 flow
                if credentials is None:
                    return False
                if not credentials or "credentials" not in credentials:
                    return False
                self.credentials = credentials["credentials"]
                self.drive_service = build("drive", "v3", credentials=self.credentials)

            # Create Syft folder if needed
            self.get_syftbox_folder_id()

            # Mark as setup verified
            self._setup_verified = True

            return True
        except Exception as e:
            print(f"[DEBUG] GDrive setup error: {e}")
            import traceback

            traceback.print_exc()
            return False

    def is_setup(self) -> bool:
        """Check if Drive transport is ready"""
        # First check if we're cached as setup
        if self.is_cached_as_setup():
            return True

        # In Colab, we can always set up on demand
        if self.environment == Environment.COLAB:
            try:
                from google.colab import auth as colab_auth

                return True  # Can authenticate on demand
            except ImportError:
                pass
            except AttributeError:
                return True
        # Otherwise check normal setup
        return self.drive_service is not None

    def add_permission(self, file_id: str, recipient: str) -> bool:
        """Add permission to the file"""
        permission = {
            "type": "user",
            "role": "reader",
            "emailAddress": recipient,
        }
        self.drive_service.permissions().create(
            fileId=file_id, body=permission, sendNotificationEmail=True
        ).execute()
        return True

    @property
    def transport_name(self) -> str:
        """Get the name of this transport"""
        return "gdrive_files"

    def get_syftbox_folder_id(self) -> None:
        """Ensure the main SyftBox folder exists"""
        if self._syftbox_folder_id:
            return

        try:
            # Search for existing SyftBox folder
            query = f"name='{self.SYFT_FOLDER}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = (
                self.drive_service.files()
                .list(q=query, fields="files(id, name)")
                .execute()
            )
            items = results.get("files", [])

            if items:
                self._syftbox_folder_id = items[0]["id"]
            else:
                # Create SyftBox folder
                file_metadata = {
                    "name": self.SYFT_FOLDER,
                    "mimeType": "application/vnd.google-apps.folder",
                }
                folder = (
                    self.drive_service.files()
                    .create(body=file_metadata, fields="id")
                    .execute()
                )
                self._syftbox_folder_id = folder.get("id")
        except Exception as e:
            raise Exception(f"Error creating SyftBox folder: {e}") from e

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
        mime_type = file_metadata["mimeType"]
        return (
            file_name.startswith("msgv2_")
            and file_name.endswith(".tar.gz")
            and not mime_type == GOOGLE_FOLDER_MIME_TYPE
        )

    def _get_messages_from_transport(
        self, sender_email: str, verbose: bool = True
    ) -> List[ProposedFileChangesMessage]:
        messages = []

        # Determine the inbox folder name pattern
        inbox_folder_id = self._get_inbox_folder_id(sender_email)
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

    def _get_inbox_folder_id(self, sender_email: str) -> Optional[str]:
        """note that ones outbox can be someone elses inbox"""
        if sender_email in self.inbox_folder_cache:
            return self.inbox_folder_cache[sender_email]
        inbox_folder = GdriveInboxOutBoxFolder(
            sender_email=sender_email, recipient_email=self.email
        )
        # TODO: this should include the parent id but it doesnt
        # inbox_folder_id = self._find_folder_by_name(
        #     inbox_folder.as_string(), parent_id=self._syftbox_folder_id
        # )
        inbox_folder_id = self._find_folder_by_name(inbox_folder.as_string())
        self.inbox_folder_cache[sender_email] = inbox_folder_id
        return inbox_folder_id

    def _get_outbox_folder_id(self, recipient: str) -> Optional[str]:
        if recipient in self.outbox_folder_cache:
            return self.outbox_folder_cache[recipient]

        outbox_folder = GdriveInboxOutBoxFolder(
            sender_email=self.email, recipient_email=recipient
        )

        outbox_folder_id = self._find_folder_by_name(
            outbox_folder.as_string(), parent_id=self._syftbox_folder_id
        )
        self.outbox_folder_cache[recipient] = outbox_folder_id
        return outbox_folder_id

    def send_proposed_file_changes_message(
        self, recipient: str, messages: List[ProposedFileChange]
    ):
        message = ProposedFileChangesMessage(proposed_file_changes=messages)
        data = message.model_dump_json(indent=2).encode("utf-8")
        data_compressed = compress_data(data)
        self.send_archive_via_transport(
            data_compressed, message.message_filename, recipient
        )

    def _find_folder_by_name(
        self, folder_name: str, parent_id: str = None
    ) -> Optional[str]:
        """Find a folder by name, optionally within a specific parent"""
        try:
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
        except:
            return None

    def send_archive_via_transport(
        self,
        archive_data: bytes,
        filename: str,
        recipient: str,
    ) -> bool:
        try:
            file_metadata = {
                "name": filename,
                "parents": [self._get_outbox_folder_id(recipient)],
            }

            payload, _ = self.create_file_payload(archive_data)

            self.drive_service.files().create(
                body=file_metadata, media_body=payload, fields="id"
            ).execute()

        except Exception as e:
            raise Exception("Error sending archive via Google Drive") from e

    def is_available(self) -> bool:
        """Check if this transport is currently available and authenticated"""
        return self.is_setup()

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
