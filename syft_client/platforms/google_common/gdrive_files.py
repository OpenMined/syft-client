"""Google Drive Files transport layer implementation"""

import io
import json
import logging
import os
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload

from ...environment import Environment
from ...transports.base import BaseTransport
from ..transport_base import BaseTransportLayer


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
                from ...environment import Environment

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
            self._ensure_syft_folder()

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

    def _ensure_syft_folder(self) -> None:
        """Create SyftClient folder if it doesn't exist"""
        try:
            # Search for existing folder
            query = f"name='{self.SYFT_FOLDER}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = (
                self.drive_service.files()
                .list(q=query, fields="files(id, name)")
                .execute()
            )
            items = results.get("files", [])

            if items:
                self._folder_id = items[0]["id"]
            else:
                # Create folder
                file_metadata = {
                    "name": self.SYFT_FOLDER,
                    "mimeType": "application/vnd.google-apps.folder",
                }
                folder = (
                    self.drive_service.files()
                    .create(body=file_metadata, fields="id")
                    .execute()
                )
                self._folder_id = folder.get("id")
        except:
            pass

    def send(self, recipient: str, data: Any, subject: str = "Syft Data") -> bool:
        """Upload file to GDrive and share with recipient"""
        if not self.drive_service:
            return False

        try:
            # Prepare data
            if isinstance(data, str):
                file_data = data.encode("utf-8")
                mime_type = "text/plain"
                extension = ".txt"
            elif isinstance(data, dict):
                file_data = json.dumps(data, indent=2).encode("utf-8")
                mime_type = "application/json"
                extension = ".json"
            else:
                # Pickle for other data types
                file_data = pickle.dumps(data)
                mime_type = "application/octet-stream"
                extension = ".pkl"

            # Create filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"syft_{subject.replace(' ', '_')}_{timestamp}{extension}"

            # Upload file
            file_metadata = {
                "name": filename,
                "parents": [self._folder_id] if self._folder_id else [],
            }

            media = MediaIoBaseUpload(
                io.BytesIO(file_data), mimetype=mime_type, resumable=True
            )

            file = (
                self.drive_service.files()
                .create(body=file_metadata, media_body=media, fields="id")
                .execute()
            )

            file_id = file.get("id")

            # Share with recipient
            if recipient and "@" in recipient:
                permission = {
                    "type": "user",
                    "role": "reader",
                    "emailAddress": recipient,
                }

                self.drive_service.permissions().create(
                    fileId=file_id, body=permission, sendNotificationEmail=True
                ).execute()

            return True

        except Exception as e:
            print(f"Error uploading to Drive: {e}")
            return False

    def receive(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Check for new shared files in GDrive"""
        if not self.drive_service:
            return []

        messages = []

        try:
            # Query for files shared with me
            query = "sharedWithMe=true and trashed=false"

            results = (
                self.drive_service.files()
                .list(
                    q=query,
                    pageSize=limit,
                    fields="files(id, name, createdTime, owners, mimeType, size)",
                    orderBy="createdTime desc",
                )
                .execute()
            )

            files = results.get("files", [])

            for file in files:
                # Check if it's a Syft file
                is_syft = file["name"].startswith("syft_")

                message = {
                    "id": file["id"],
                    "filename": file["name"],
                    "from": file["owners"][0]["emailAddress"]
                    if file.get("owners")
                    else "Unknown",
                    "date": file["createdTime"],
                    "mime_type": file["mimeType"],
                    "size": file.get("size", 0),
                    "is_syft": is_syft,
                    "data": None,  # Will be loaded on demand
                }

                # For small files, load data directly
                if is_syft and int(file.get("size", 0)) < 10 * 1024 * 1024:  # 10MB
                    try:
                        message["data"] = self._download_file(
                            file["id"], file["mimeType"]
                        )
                    except:
                        pass

                messages.append(message)

        except Exception as e:
            print(f"Error retrieving from Drive: {e}")

        return messages

    def _download_file(self, file_id: str, mime_type: str) -> Any:
        """Download and decode file from Drive"""
        try:
            request = self.drive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()

            fh.seek(0)
            data = fh.read()

            # Decode based on mime type
            if mime_type == "text/plain":
                return data.decode("utf-8")
            elif mime_type == "application/json":
                return json.loads(data.decode("utf-8"))
            elif mime_type == "application/octet-stream":
                return pickle.loads(data)
            else:
                return data

        except:
            return None

    def create_public_folder(self, folder_name: str) -> Optional[str]:
        """Create a publicly accessible folder and return its URL"""
        if not self.drive_service:
            return None

        try:
            # Create folder
            file_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [self._folder_id] if self._folder_id else [],
            }

            folder = (
                self.drive_service.files()
                .create(body=file_metadata, fields="id, webViewLink")
                .execute()
            )

            folder_id = folder.get("id")

            # Make it public
            permission = {"type": "anyone", "role": "reader"}

            self.drive_service.permissions().create(
                fileId=folder_id, body=permission
            ).execute()

            return folder.get("webViewLink")

        except:
            return None

    def test(self, test_data: str = "test123", cleanup: bool = True) -> Dict[str, Any]:
        """Test Google Drive transport by creating a test file with test data

        Args:
            test_data: Data to include in the test file
            cleanup: If True, delete the test file after creation (default: True)

        Returns:
            Dictionary with 'success' (bool) and 'url' (str) if successful
        """
        if not self.drive_service:
            print("Drive service not initialized")
            return {"success": False, "error": "Drive service not initialized"}

        try:
            from datetime import datetime

            # Create test file content
            test_content = {
                "test_data": test_data,
                "timestamp": datetime.now().isoformat(),
                "transport": "Google Drive Files (Org)",
                "email": self.email,
            }

            # Create filename
            filename = (
                f"test_file_{test_data}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )

            # Create file metadata
            file_metadata = {
                "name": filename,
                "parents": [self._folder_id] if self._folder_id else [],
            }

            # Upload the file
            import io
            import json

            file_data = json.dumps(test_content, indent=2).encode("utf-8")
            media = MediaIoBaseUpload(
                io.BytesIO(file_data), mimetype="application/json", resumable=True
            )

            file = (
                self.drive_service.files()
                .create(body=file_metadata, media_body=media, fields="id, webViewLink")
                .execute()
            )

            file_id = file.get("id")
            web_link = file.get("webViewLink")

            # Delete the file if cleanup is requested
            if cleanup and file_id:
                try:
                    # Small delay to ensure file is accessible before deletion
                    import time

                    time.sleep(1)

                    self.drive_service.files().delete(fileId=file_id).execute()
                except Exception:
                    # If deletion fails, try moving to trash
                    try:
                        self.drive_service.files().update(
                            fileId=file_id, body={"trashed": True}
                        ).execute()
                    except Exception:
                        pass

            # Return the web view link
            print(
                f"✅ Google Drive test successful! File created in {self.SYFT_FOLDER if self._folder_id else 'root'}"
            )
            if cleanup:
                print("   File has been deleted as requested")

            return {"success": True, "url": web_link}

        except Exception as e:
            print(f"❌ Google Drive test failed: {e}")
            return {"success": False, "error": str(e)}

    # Peer Management Methods (implementing BaseTransport interface)

    @property
    def transport_name(self) -> str:
        """Get the name of this transport"""
        return "gdrive_files"

    def _send_archive_via_transport(
        self,
        archive_data: bytes,
        filename: str,
        recipient: str,
        message_id: Optional[str] = None,
    ) -> bool:
        """
        Send archive data via Google Drive by uploading to the outbox_inbox folder
        """
        try:
            # Ensure we have SyftBox folder
            self._ensure_syftbox_folder()
            if not self._syftbox_folder_id:
                return False

            # Find the outbox folder for this recipient
            outbox_name = f"syft_{self.email}_to_{recipient}_outbox_inbox"
            outbox_id = self._find_folder_by_name(
                outbox_name, parent_id=self._syftbox_folder_id
            )

            if not outbox_id:
                if self.verbose:
                    print(
                        f"❌ No outbox folder found for {recipient}. Add them as a peer first."
                    )
                return False

            # Upload file to outbox
            file_metadata = {"name": filename, "parents": [outbox_id]}

            media = MediaIoBaseUpload(
                io.BytesIO(archive_data),
                mimetype="application/octet-stream",
                resumable=True,
            )

            file = (
                self.drive_service.files()
                .create(body=file_metadata, media_body=media, fields="id")
                .execute()
            )

            if self.verbose:
                print(f"✅ Sent {filename} to {recipient}")

            return True

        except Exception as e:
            if self.verbose:
                print(f"Error sending via Google Drive: {e}")
            return False

    def add_peer(self, email: str, verbose: bool = True) -> bool:
        """
        Add a peer by setting up bidirectional communication folders in Google Drive

        This method:
        1. Creates your outgoing channel to them (pending and outbox_inbox folders)
        2. Creates your archive for their messages
        3. Sets up the folder structure for communication

        Args:
            email: Email address of the peer to add
            verbose: Whether to print status messages

        Returns:
            True if peer was successfully added, False otherwise
        """
        if not self.is_setup():
            if verbose:
                print("❌ Google Drive transport is not set up")
            return False

        if email.lower() == self.email.lower():
            if verbose:
                print("❌ Cannot add yourself as a contact")
            return False

        try:
            # Ensure we have the main SyftBox folder
            self._ensure_syftbox_folder()

            # 1. Set up outgoing channel (your folders)
            result = self._setup_communication_channel(email, verbose=verbose)
            if not result:
                if verbose:
                    print(f"❌ Failed to create channel to {email}")
                return False

            # 2. Set up incoming archive
            archive_id = self._setup_incoming_archive(email, verbose=verbose)
            if not archive_id:
                if verbose:
                    print(f"❌ Failed to create archive for {email}")
                return False

            if verbose:
                print(f"✅ Added {email} as a peer!")
                print(f"   📤 Your outgoing channel is ready")
                print(f"   📥 Your incoming archive is ready")
                print(f"\n💡 Ask {email} to run: client.add_peer('{self.email}')")

            return True

        except Exception as e:
            if verbose:
                print(f"❌ Error adding peer: {e}")
            return False

    def remove_peer(self, email: str, verbose: bool = True) -> bool:
        """
        Remove a peer by revoking their access to communication folders

        This revokes access to:
        1. The outbox_inbox folder (where you send messages)
        2. The archive folder (where they store processed messages)

        Note: This doesn't delete the folders, just removes their access

        Args:
            email: Email address of the peer to remove
            verbose: Whether to print status messages

        Returns:
            True if peer was successfully removed, False otherwise
        """
        if not self.is_setup():
            if verbose:
                print("❌ Google Drive transport is not set up")
            return False

        try:
            # Ensure we have SyftBox folder
            self._ensure_syftbox_folder()
            if not self._syftbox_folder_id:
                return False

            folders_processed = 0

            # 1. Remove access from outbox_inbox folder
            outbox_inbox_name = f"syft_{self.email}_to_{email}_outbox_inbox"
            outbox_id = self._find_folder_by_name(
                outbox_inbox_name, parent_id=self._syftbox_folder_id
            )

            if outbox_id:
                try:
                    permissions = (
                        self.drive_service.permissions()
                        .list(
                            fileId=outbox_id,
                            fields="permissions(id, emailAddress, role)",
                        )
                        .execute()
                    )

                    for perm in permissions.get("permissions", []):
                        if perm.get("emailAddress", "").lower() == email.lower():
                            self.drive_service.permissions().delete(
                                fileId=outbox_id, permissionId=perm["id"]
                            ).execute()
                            folders_processed += 1
                            if verbose:
                                print(f"✅ Revoked {email}'s access to outbox folder")
                            break
                except Exception as e:
                    if verbose:
                        print(f"⚠️  Could not revoke access to outbox: {e}")

            # 2. Remove access from archive folder
            archive_name = f"syft_{email}_to_{self.email}_archive"
            archive_id = self._find_folder_by_name(
                archive_name, parent_id=self._syftbox_folder_id
            )

            if archive_id:
                try:
                    permissions = (
                        self.drive_service.permissions()
                        .list(
                            fileId=archive_id,
                            fields="permissions(id, emailAddress, role)",
                        )
                        .execute()
                    )

                    for perm in permissions.get("permissions", []):
                        if perm.get("emailAddress", "").lower() == email.lower():
                            self.drive_service.permissions().delete(
                                fileId=archive_id, permissionId=perm["id"]
                            ).execute()
                            folders_processed += 1
                            if verbose:
                                print(f"✅ Revoked {email}'s access to archive folder")
                            break
                except Exception as e:
                    if verbose:
                        print(f"⚠️  Could not revoke access to archive: {e}")

            if folders_processed > 0:
                if verbose:
                    print(
                        f"✅ Removed {email} from contacts (revoked access to {folders_processed} folder(s))"
                    )
                return True
            else:
                if verbose:
                    print(f"⚠️  No folders found for {email}")
                return False

        except Exception as e:
            if verbose:
                print(f"❌ Error removing peer: {e}")
            return False

    def list_peers(self) -> List[str]:
        """
        List all peers by scanning for outbox folders in SyftBox

        Looks for folders with pattern: syft_{my_email}_to_{their_email}_outbox_inbox

        Returns:
            List of email addresses that are peers on this transport
        """
        if not self.is_setup():
            return []

        try:
            # Ensure we have SyftBox folder
            self._ensure_syftbox_folder()
            if not self._syftbox_folder_id:
                return []

            # Look for outbox folders with our email as sender
            # Pattern: syft_{my_email}_to_{their_email}_outbox_inbox
            prefix = f"syft_{self.email}_to_"
            suffix = "_outbox_inbox"

            # Query for folders matching our pattern
            query = f"name contains '{prefix}' and name contains '{suffix}' and '{self._syftbox_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = (
                self.drive_service.files()
                .list(q=query, fields="files(id, name)", pageSize=1000)
                .execute()
            )

            contacts = set()  # Use set to avoid duplicates

            for folder in results.get("files", []):
                folder_name = folder["name"]
                # Extract email from folder name
                # Format: syft_{sender}_to_{receiver}_outbox_inbox
                if folder_name.startswith(prefix) and folder_name.endswith(suffix):
                    # Remove prefix and suffix to get receiver email
                    middle_part = folder_name[len(prefix) : -len(suffix)]
                    if middle_part and "@" in middle_part:
                        contacts.add(middle_part)

            return list(contacts)

        except Exception as e:
            if self.verbose:
                print(f"Error listing peers: {e}")
            return []

    def is_available(self) -> bool:
        """Check if this transport is currently available and authenticated"""
        return self.is_setup()

    def get_peer_resource(self, email: str) -> Optional[Any]:
        """
        Get all folders associated with a peer

        This returns a PeerResource object containing all three folders:
        - Pending folder (private)
        - Outbox/Inbox folder (shared with peer)
        - Archive folder (for processed messages)

        Args:
            email: Email address of the peer

        Returns:
            PeerResource object or None if no folders found
        """
        from ...sync.peer_resource import PeerResource

        # Ensure we have SyftBox folder
        self._ensure_syftbox_folder()
        if not self._syftbox_folder_id:
            return None

        # Find all three folders
        folders_found = False

        # 1. Pending folder (private)
        pending_name = f"syft_{self.email}_to_{email}_pending"
        pending_folder = self._find_folder_details(
            pending_name, self._syftbox_folder_id
        )
        if pending_folder:
            folders_found = True

        # 2. Outbox/Inbox folder (shared)
        outbox_name = f"syft_{self.email}_to_{email}_outbox_inbox"
        outbox_folder = self._find_folder_details(outbox_name, self._syftbox_folder_id)
        if outbox_folder:
            folders_found = True

        # 3. Archive folder
        archive_name = f"syft_{email}_to_{self.email}_archive"
        archive_folder = self._find_folder_details(
            archive_name, self._syftbox_folder_id
        )
        if archive_folder:
            folders_found = True

        # Only return a resource if at least one folder exists
        if not folders_found:
            return None

        return PeerResource(
            peer_email=email,
            transport_name=self.transport_name,
            platform_name=getattr(self._platform_client, "platform", "google_org")
            if hasattr(self, "_platform_client")
            else "google_org",
            pending=pending_folder,
            outbox_inbox=outbox_folder,
            archive=archive_folder,
            resource_type="folders",
            available=True,
        )

    # Helper methods for peer management

    def _ensure_syftbox_folder(self) -> None:
        """Ensure the main SyftBox folder exists"""
        if self._syftbox_folder_id:
            return

        try:
            # Search for existing SyftBox folder
            query = "name='SyftBox' and mimeType='application/vnd.google-apps.folder' and trashed=false"
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
                    "name": "SyftBox",
                    "mimeType": "application/vnd.google-apps.folder",
                }
                folder = (
                    self.drive_service.files()
                    .create(body=file_metadata, fields="id")
                    .execute()
                )
                self._syftbox_folder_id = folder.get("id")
        except:
            pass

    def _setup_communication_channel(
        self, their_email: str, verbose: bool = True
    ) -> Optional[Dict[str, str]]:
        """
        Set up unidirectional communication channel from me to them

        Args:
            their_email: Receiver's email address
            verbose: Whether to print progress messages

        Returns:
            Dictionary with folder IDs if successful, None otherwise
        """
        try:
            # Ensure SyftBox exists
            self._ensure_syftbox_folder()
            if not self._syftbox_folder_id:
                return None

            # Create flat folder names with syft_ prefix
            pending_name = f"syft_{self.email}_to_{their_email}_pending"
            outbox_inbox_name = f"syft_{self.email}_to_{their_email}_outbox_inbox"

            folder_ids = {
                "sender": self.email,
                "receiver": their_email,
                "syftbox_id": self._syftbox_folder_id,
            }

            # Create/check pending folder (private to sender)
            pending_id = self._find_folder_by_name(
                pending_name, parent_id=self._syftbox_folder_id
            )

            if pending_id:
                folder_ids["pending"] = pending_id
                if verbose:
                    print(f"✅ Pending folder already exists: {pending_name}")
            else:
                pending_id = self._create_folder(
                    pending_name, parent_id=self._syftbox_folder_id
                )
                if pending_id:
                    folder_ids["pending"] = pending_id
                    if verbose:
                        print(f"📁 Created pending folder: {pending_name}")
                        print(f"   ⏳ For preparing messages (private)")

            # Create/check outbox_inbox folder (shared with receiver)
            outbox_id = self._find_folder_by_name(
                outbox_inbox_name, parent_id=self._syftbox_folder_id
            )

            if outbox_id:
                folder_ids["outbox_inbox"] = outbox_id
                if verbose:
                    print(f"✅ Outbox/Inbox folder already exists: {outbox_inbox_name}")
            else:
                outbox_id = self._create_folder(
                    outbox_inbox_name, parent_id=self._syftbox_folder_id
                )
                if outbox_id:
                    folder_ids["outbox_inbox"] = outbox_id
                    if verbose:
                        print(f"📁 Created outbox/inbox folder: {outbox_inbox_name}")
                        print(f"   📬 For active communication (shared)")

            # Grant receiver write access to outbox_inbox
            if outbox_id:
                try:
                    # Check existing permissions
                    permissions = (
                        self.drive_service.permissions()
                        .list(
                            fileId=outbox_id,
                            fields="permissions(id, emailAddress, role)",
                        )
                        .execute()
                    )

                    has_permission = any(
                        p.get("emailAddress", "").lower() == their_email.lower()
                        for p in permissions.get("permissions", [])
                    )

                    if not has_permission:
                        permission = {
                            "type": "user",
                            "role": "writer",
                            "emailAddress": their_email,
                        }

                        self.drive_service.permissions().create(
                            fileId=outbox_id,
                            body=permission,
                            sendNotificationEmail=False,
                        ).execute()

                        if verbose:
                            print(f"   ✅ Granted write access to {their_email}")
                    elif verbose:
                        print(f"   ℹ️  {their_email} already has access")
                except Exception as e:
                    if verbose:
                        print(f"   ⚠️  Could not set permissions: {e}")

            if verbose:
                print(f"✅ Communication channel ready: {self.email} → {their_email}")

            return folder_ids

        except Exception as e:
            if verbose:
                print(f"❌ Error setting up communication channel: {e}")
            return None

    def _setup_incoming_archive(
        self, their_email: str, verbose: bool = True
    ) -> Optional[str]:
        """
        Create archive folder for incoming messages from another person

        Args:
            their_email: Sender's email address
            verbose: Whether to print status messages

        Returns:
            Archive folder ID if successful
        """
        try:
            # Ensure SyftBox exists
            self._ensure_syftbox_folder()
            if not self._syftbox_folder_id:
                return None

            # Create archive folder name
            archive_name = f"syft_{their_email}_to_{self.email}_archive"

            # Check if archive already exists
            archive_id = self._find_folder_by_name(
                archive_name, parent_id=self._syftbox_folder_id
            )

            if archive_id:
                if verbose:
                    print(f"✅ Archive folder already exists: {archive_name}")
            else:
                # Create archive folder
                archive_id = self._create_folder(
                    archive_name, parent_id=self._syftbox_folder_id
                )
                if archive_id:
                    if verbose:
                        print(f"📁 Created archive folder: {archive_name}")
                        print(
                            f"   📚 For storing processed messages from {their_email}"
                        )

                    # Grant sender write access to archive
                    try:
                        permission = {
                            "type": "user",
                            "role": "writer",
                            "emailAddress": their_email,
                        }

                        self.drive_service.permissions().create(
                            fileId=archive_id,
                            body=permission,
                            sendNotificationEmail=False,
                        ).execute()

                        if verbose:
                            print(f"   ✅ Granted write access to {their_email}")
                    except Exception as e:
                        if verbose:
                            print(f"   ⚠️  Could not set permissions: {e}")
                else:
                    if verbose:
                        print(f"❌ Failed to create archive folder")
                    return None

            return archive_id

        except Exception as e:
            if verbose:
                print(f"❌ Error setting up archive: {e}")
            return None

    def _find_folder_by_name(
        self, folder_name: str, parent_id: str = None
    ) -> Optional[str]:
        """Find a folder by name, optionally within a specific parent"""
        try:
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

    def _find_folder_details(
        self, folder_name: str, parent_id: str = None
    ) -> Optional[Dict[str, Any]]:
        """Find a folder and return its details including permissions"""
        try:
            if parent_id:
                query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
            else:
                query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"

            results = (
                self.drive_service.files()
                .list(
                    q=query,
                    fields="files(id, name, webViewLink, permissions(emailAddress, role))",
                    pageSize=1,
                )
                .execute()
            )

            items = results.get("files", [])
            if items:
                folder = items[0]
                # Add URL for convenience
                folder["url"] = folder.get(
                    "webViewLink",
                    f"https://drive.google.com/drive/folders/{folder['id']}",
                )
                return folder
            return None
        except:
            return None

    def _create_folder(self, folder_name: str, parent_id: str = None) -> Optional[str]:
        """Create a folder and return its ID"""
        try:
            file_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            }

            if parent_id:
                file_metadata["parents"] = [parent_id]

            folder = (
                self.drive_service.files()
                .create(body=file_metadata, fields="id")
                .execute()
            )

            return folder.get("id")
        except:
            return None

    def _ensure_peers_folder(self) -> Optional[Dict[str, Any]]:
        """Ensure peers folder exists and return it"""
        try:
            self._ensure_syftbox_folder()
            parent_id = self._syftbox_folder_id or "root"

            # Search for existing peers folder
            query = f"name='peers' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
            results = (
                self.drive_service.files()
                .list(q=query, fields="files(id, name)")
                .execute()
            )
            items = results.get("files", [])

            if items:
                return items[0]
            else:
                # Create peers folder
                file_metadata = {
                    "name": "peers",
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_id],
                }
                folder = (
                    self.drive_service.files()
                    .create(body=file_metadata, fields="id, name")
                    .execute()
                )
                return folder
        except:
            return None

    def _find_peers_folder(self) -> Optional[Dict[str, Any]]:
        """Find the peers folder"""
        try:
            # Search in SyftBox folder first
            if self._syftbox_folder_id:
                query = f"name='peers' and mimeType='application/vnd.google-apps.folder' and '{self._syftbox_folder_id}' in parents and trashed=false"
            else:
                # Search anywhere
                query = "name='peers' and mimeType='application/vnd.google-apps.folder' and trashed=false"

            results = (
                self.drive_service.files()
                .list(q=query, fields="files(id, name)")
                .execute()
            )
            items = results.get("files", [])
            return items[0] if items else None
        except:
            return None

    def _find_peer_folder(self, peer_identifier: str) -> Optional[Dict[str, Any]]:
        """
        Find a peer's outbox folder in the new structure

        Args:
            peer_identifier: Email address of the peer

        Returns:
            Folder dict with 'id', 'name', 'url' or None if not found
        """
        try:
            # Ensure we have SyftBox folder
            self._ensure_syftbox_folder()
            if not self._syftbox_folder_id:
                return None

            # Look for outbox folder
            folder_name = f"syft_{self.email}_to_{peer_identifier}_outbox_inbox"

            # Search for the specific folder
            query = f"name='{folder_name}' and '{self._syftbox_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = (
                self.drive_service.files()
                .list(
                    q=query,
                    fields="files(id, name, webViewLink, permissions(emailAddress, role))",
                )
                .execute()
            )

            items = results.get("files", [])
            if items:
                folder = items[0]
                # Add URL for convenience
                folder["url"] = folder.get(
                    "webViewLink",
                    f"https://drive.google.com/drive/folders/{folder['id']}",
                )
                # Add type for display
                folder["type"] = "folder"
                return folder
            return None

        except Exception as e:
            if self.verbose:
                print(f"Error finding peer folder: {e}")
            return None

    def check_peer_requests(self) -> List[str]:
        """
        Check for incoming peer requests by looking for shared folders

        Returns:
            List of email addresses who have shared folders with us
        """
        if not self.is_setup():
            return []

        try:
            # Get our email
            my_email = self.email
            if not my_email:
                return []

            pending_requests = set()
            existing_contacts = set(self.list_peers())

            # Search for syft folders shared with us
            query = f"sharedWithMe=true and name contains 'syft_' and mimeType='application/vnd.google-apps.folder' and trashed=false"

            results = (
                self.drive_service.files()
                .list(q=query, fields="files(id, name, owners)", pageSize=1000)
                .execute()
            )

            shared_folders = results.get("files", [])

            # Check each shared folder
            for folder in shared_folders:
                name = folder["name"]

                # Check if it follows syft folder pattern
                if "_to_" in name and name.startswith("syft_"):
                    parts = name.split("_to_")
                    if len(parts) == 2:
                        sender = parts[0].replace("syft_", "")
                        recipient_with_suffix = parts[1]

                        # Remove suffixes to get clean email
                        recipient = recipient_with_suffix
                        for suffix in [
                            "_outbox_inbox",
                            "_outbox",
                            "_pending",
                            "_archive",
                        ]:
                            recipient = recipient.replace(suffix, "")

                        # If they're sharing with us and not already a contact
                        if recipient == my_email and sender not in existing_contacts:
                            # Verify it's from the owner
                            owners = folder.get("owners", [])
                            for owner in owners:
                                if (
                                    owner.get("emailAddress", "").lower()
                                    == sender.lower()
                                ):
                                    pending_requests.add(sender)
                                    break

            return sorted(list(pending_requests))

        except Exception as e:
            # Silently fail - peer request checking is optional
            return []

    def _get_messages_from_transport(
        self, sender_email: str, verbose: bool = True
    ) -> List[Dict]:
        """
        Google Drive specific implementation to retrieve messages
        """
        messages = []

        try:
            # Determine the inbox folder name pattern
            my_email = self.email
            folder_name = f"syft_{sender_email}_to_{my_email}_outbox_inbox"

            # Find the folder
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = (
                self.drive_service.files()
                .list(q=query, fields="files(id, name)", pageSize=10)
                .execute()
            )

            folders = results.get("files", [])
            if not folders:
                if verbose:
                    print(f"   No inbox folder found: {folder_name}")
                return []

            folder_id = folders[0]["id"]
            self._current_folder_id = folder_id  # Store for archiving

            # List files in the folder
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

            files = results.get("files", [])
            if not files:
                return []

            # Process each file
            for file in files:
                try:
                    file_name = file["name"]
                    file_id = file["id"]

                    # Skip if it's a folder
                    if file["mimeType"] == "application/vnd.google-apps.folder":
                        continue

                    # Download the file
                    if file_name.endswith(".tar.gz"):
                        # This is likely a message archive
                        request = self.drive_service.files().get_media(fileId=file_id)
                        import io

                        from googleapiclient.http import MediaIoBaseDownload

                        # Download to memory
                        file_buffer = io.BytesIO()
                        downloader = MediaIoBaseDownload(file_buffer, request)

                        done = False
                        while not done:
                            status, done = downloader.next_chunk()

                        message_data = file_buffer.getvalue()

                        # Store message info
                        message_id = file_name.replace(".tar.gz", "")
                        messages.append(
                            {
                                "message_id": message_id,
                                "data": message_data,
                                "file_id": file_id,
                                "file_name": file_name,
                                "size": str(file.get("size", 0)),
                            }
                        )

                except Exception as e:
                    if verbose:
                        print(f"   ❌ Error downloading {file['name']}: {e}")

            return messages

        except Exception as e:
            if verbose:
                print(f"   ❌ Error retrieving messages from drive: {e}")
            return []

    def _archive_messages(self, messages: List[Dict], verbose: bool = True):
        """
        Archive processed messages to the archive folder
        """
        if not hasattr(self, "_current_folder_id") or not self._current_folder_id:
            return

        try:
            for msg in messages:
                if "file_id" in msg:
                    self._archive_message(
                        msg["file_id"], self._current_folder_id, verbose
                    )
        except Exception as e:
            if verbose:
                print(f"   ⚠️  Error archiving messages: {e}")

    def _archive_message(
        self, file_id: str, inbox_folder_id: str, verbose: bool = True
    ):
        """Move a processed message to the archive folder"""
        try:
            # Get sender email from folder name
            folder_info = (
                self.drive_service.files()
                .get(fileId=inbox_folder_id, fields="name")
                .execute()
            )

            folder_name = folder_info["name"]
            # Extract emails from folder name: syft_{sender}_to_{receiver}_outbox_inbox
            parts = (
                folder_name.replace("syft_", "")
                .replace("_outbox_inbox", "")
                .split("_to_")
            )
            if len(parts) == 2:
                sender_email = parts[0]
                my_email = parts[1]

                # Find or create archive folder
                archive_folder_name = f"syft_{sender_email}_to_{my_email}_archive"

                # Check if archive folder exists
                query = f"name='{archive_folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
                results = (
                    self.drive_service.files()
                    .list(q=query, fields="files(id)", pageSize=1)
                    .execute()
                )

                archive_folders = results.get("files", [])

                if not archive_folders:
                    # Create archive folder in same parent as inbox
                    # Get inbox parent
                    inbox_info = (
                        self.drive_service.files()
                        .get(fileId=inbox_folder_id, fields="parents")
                        .execute()
                    )

                    parents = inbox_info.get("parents", [])

                    # Create archive folder
                    folder_metadata = {
                        "name": archive_folder_name,
                        "mimeType": "application/vnd.google-apps.folder",
                        "parents": parents,
                    }

                    archive_folder = (
                        self.drive_service.files()
                        .create(body=folder_metadata, fields="id")
                        .execute()
                    )

                    archive_folder_id = archive_folder["id"]
                else:
                    archive_folder_id = archive_folders[0]["id"]

                # Move file to archive
                file_metadata = {
                    "addParents": archive_folder_id,
                    "removeParents": inbox_folder_id,
                }

                self.drive_service.files().update(
                    fileId=file_id, body=file_metadata
                ).execute()

                if verbose:
                    print(f"   📦 Archived message")

        except Exception as e:
            if verbose:
                print(f"   ⚠️  Error archiving message: {e}")
