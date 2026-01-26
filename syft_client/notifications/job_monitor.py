"""
Job Monitor: Detects and notifies about job events in SyftBox.

Polls Google Drive directly for new job submissions (lightweight, no full sync needed).
Checks local filesystem for job status changes (approved, executed).
"""

import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, TYPE_CHECKING

from google.oauth2.credentials import Credentials as GoogleCredentials

from syft_client.sync.connections.drive.gdrive_transport import build_drive_service

try:
    from .base import Monitor, NotificationSender, StateManager
except ImportError:
    from notifications_base import Monitor, NotificationSender, StateManager

if TYPE_CHECKING:
    from syft_client.sync.syftbox_manager import SyftboxManager


# Google Drive constants
GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX = "syft_outbox_inbox"
GOOGLE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


class JobMonitor(Monitor):
    """
    Monitor jobs in SyftBox for notification events.

    Uses a hybrid approach:
    - Polls Google Drive directly for new job submissions (lightweight)
    - Checks local filesystem for job status changes (approved, executed)

    This allows running as a standalone daemon without requiring full client.sync().
    """

    def __init__(
        self,
        syftbox_root: Path,
        do_email: str,
        sender: NotificationSender,
        state: StateManager,
        config: Dict[str, Any],
        drive_token_path: Optional[Path] = None,
        client: Optional["SyftboxManager"] = None,
    ):
        """
        Initialize Job Monitor.

        Args:
            syftbox_root: Path to SyftBox root directory
            do_email: Data Owner email address
            sender: Notification sender implementation
            state: State manager implementation
            config: Configuration dictionary with notification toggles
            drive_token_path: Path to Google Drive OAuth token (for direct polling)
            client: Optional SyftboxManager (fallback if no drive_token_path)
        """
        super().__init__(sender, state, config)
        self.syftbox_root = Path(syftbox_root).expanduser()
        self.do_email = do_email
        self.job_dir = self.syftbox_root / do_email / "app_data" / "job"
        self.drive_token_path = Path(drive_token_path) if drive_token_path else None
        self._client = client

        # Initialize Drive service on main thread (googleapiclient.build not thread-safe)
        self._drive_service = None
        if self.drive_token_path and self.drive_token_path.exists():
            self._drive_service = self._create_drive_service()

    def _create_drive_service(self):
        """Create Google Drive service (must be called from main thread)."""
        credentials = GoogleCredentials.from_authorized_user_file(
            str(self.drive_token_path), DRIVE_SCOPES
        )
        return build_drive_service(credentials)

    def _find_inbox_folders(self) -> List[Tuple[str, str]]:
        """
        Find all DS->DO inbox folders in Google Drive.

        Returns:
            List of (ds_email, folder_id) tuples
        """
        if not self._drive_service:
            return []

        try:
            # Query for inbox folders where someone sent TO the DO
            query = (
                f"name contains '{GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX}' and "
                f"name contains '_to_{self.do_email}' and "
                f"mimeType = '{GOOGLE_FOLDER_MIME_TYPE}' and "
                "trashed=false"
            )
            results = self._drive_service.files().list(q=query).execute()

            folders = []
            for folder in results.get("files", []):
                # Parse: syft_outbox_inbox_{sender}_to_{recipient}
                name = folder["name"]
                parts = name.split("_")
                if len(parts) >= 6:
                    sender_email = parts[3]  # ds_email
                    if sender_email != self.do_email:
                        folders.append((sender_email, folder["id"]))
            return folders

        except Exception as e:
            print(f"⚠️  JobMonitor: Error finding inbox folders: {e}")
            return []

    def _get_pending_messages(self, folder_id: str) -> List[Dict[str, Any]]:
        """
        Get message files from an inbox folder.

        Args:
            folder_id: Google Drive folder ID

        Returns:
            List of file dicts with 'id' and 'name' keys
        """
        if not self._drive_service:
            return []

        try:
            query = (
                f"'{folder_id}' in parents and name contains 'msgv2_' and trashed=false"
            )
            results = (
                self._drive_service.files()
                .list(
                    q=query,
                    fields="files(id, name)",
                    orderBy="name",  # Oldest first (by timestamp in filename)
                )
                .execute()
            )
            return results.get("files", [])

        except Exception as e:
            print(f"⚠️  JobMonitor: Error getting messages: {e}")
            return []

    def _parse_job_from_message(
        self, file_id: str, ds_email: str
    ) -> Optional[Dict[str, Any]]:
        """
        Download and parse a message file to extract job info.

        Args:
            file_id: Google Drive file ID
            ds_email: Email of the sender (for fallback)

        Returns:
            Dict with job info or None if not a job message
        """
        if not self._drive_service:
            return None

        try:
            from syft_client.sync.messages.proposed_filechange import (
                ProposedFileChangesMessage,
            )

            # Download file content
            request = self._drive_service.files().get_media(fileId=file_id)
            content = request.execute()

            # Parse compressed message
            msg = ProposedFileChangesMessage.from_compressed_data(content)

            # Look for job config files in the proposed changes
            for change in msg.proposed_file_changes:
                path = str(change.path_in_datasite)
                if "app_data/job/" in path and path.endswith("config.yaml"):
                    # Extract job name from path: app_data/job/{job_name}/config.yaml
                    parts = path.split("/")
                    try:
                        job_idx = parts.index("job")
                        job_name = parts[job_idx + 1]

                        return {
                            "job_name": job_name,
                            "submitter": msg.sender_email,
                            "message_id": file_id,
                        }
                    except (ValueError, IndexError):
                        continue

            return None

        except Exception as e:
            # Skip messages that fail to parse (non-job messages or corrupted data)
            print(f"⚠️  JobMonitor: Error parsing message {file_id}: {e}")
            return None

    def _poll_drive_for_new_jobs(self):
        """Poll Google Drive directly for new job submissions."""
        if not self._drive_service:
            return

        for ds_email, folder_id in self._find_inbox_folders():
            messages = self._get_pending_messages(folder_id)

            for msg_file in messages:
                msg_id = msg_file["id"]

                # Skip if we've already processed this message
                if self.state.was_notified(f"msg_{msg_id}", "processed"):
                    continue

                job_info = self._parse_job_from_message(msg_id, ds_email)
                if job_info:
                    self._handle_new_job_from_drive(job_info)

                # Mark message as processed (even if not a job)
                self.state.mark_notified(f"msg_{msg_id}", "processed")

    def _handle_new_job_from_drive(self, job_info: Dict[str, Any]):
        """
        Handle new job detected from Drive polling.

        Args:
            job_info: Dict with job_name, submitter, message_id
        """
        job_name = job_info["job_name"]
        submitter = job_info["submitter"]

        if not self.config.get("notify_on_new_job", True):
            return

        if self.state.was_notified(job_name, "new"):
            return

        print(
            f"📧 Sending new job notification to DO ({self.do_email}): {job_name} from {submitter}"
        )

        if hasattr(self.sender, "notify_new_job"):
            success = self.sender.notify_new_job(self.do_email, job_name, submitter)
        else:
            success = self.sender.send_notification(
                self.do_email,
                f"New Job: {job_name}",
                f"New job from {submitter}",
            )

        if success:
            self.state.mark_notified(job_name, "new")
            print("   ✅ Sent and marked as notified")
        else:
            print("   ❌ Failed to send")

    def _sync_from_drive(self):
        """
        Sync from Google Drive using client (fallback method).

        Only used if drive_token_path is not available.
        """
        if self._client is None:
            return

        try:
            self._client.sync()
        except Exception as e:
            print(f"⚠️  JobMonitor: Sync error (continuing with local check): {e}")

    def _check_all_entities(self):
        """
        Check all jobs for notification events using hybrid approach.

        1. Poll Drive directly for NEW job submissions (lightweight)
        2. Check local filesystem for approved/executed status changes
        """
        # Poll Drive for new job submissions
        if self._drive_service:
            self._poll_drive_for_new_jobs()
        else:
            # Fallback to full sync if no direct Drive access
            self._sync_from_drive()

        # Check local filesystem for status changes (approved, executed)
        self._check_local_for_status_changes()

    def _check_local_for_status_changes(self):
        """Check local job directory for approved/done status markers."""
        if not self.job_dir.exists():
            return

        for job_path in self.job_dir.iterdir():
            if not job_path.is_dir():
                continue
            try:
                self._check_job_status(job_path)
            except Exception as e:
                print(f"⚠️  JobMonitor: Error checking job {job_path.name}: {e}")

    def _check_job_status(self, job_path: Path):
        """
        Check single job for status change events (approved, executed).

        NOTE: This method ONLY checks for approved/executed status.
        New job detection happens via Drive polling (_poll_drive_for_new_jobs).
        This prevents sending "new" notifications for old jobs that exist locally.
        """
        config = self._load_job_config(job_path)
        if not config:
            return

        job_name = config.get("name", job_path.name)
        ds_email = config.get("submitted_by")

        if not ds_email:
            return

        # NOTE: We do NOT check for "new" jobs here.
        # New job detection is handled by _poll_drive_for_new_jobs() via Drive API.
        # This prevents false notifications for old jobs that already exist locally.

        # Only send approved/executed notifications for jobs we've tracked as "new"
        # This prevents sending status emails for old jobs we never notified about
        if not self.state.was_notified(job_name, "new"):
            # Job wasn't detected via Drive polling, skip status notifications
            return

        # Check for approved
        if self.config.get("notify_on_approved", True):
            if (job_path / "approved").exists():
                if not self.state.was_notified(job_name, "approved"):
                    print(
                        f"📧 Sending job approved notification to DS ({ds_email}): {job_name}"
                    )
                    if hasattr(self.sender, "notify_job_approved"):
                        success = self.sender.notify_job_approved(ds_email, job_name)
                    else:
                        success = self.sender.send_notification(
                            ds_email,
                            f"Job Approved: {job_name}",
                            "Your job has been approved",
                        )
                    if success:
                        self.state.mark_notified(job_name, "approved")
                        print("   ✅ Sent and marked as notified")
                    else:
                        print("   ❌ Failed to send")

        # Check for executed (done)
        if self.config.get("notify_on_executed", True):
            if (job_path / "done").exists():
                if not self.state.was_notified(job_name, "executed"):
                    print(
                        f"📧 Sending job executed notification to DS ({ds_email}): {job_name}"
                    )
                    if hasattr(self.sender, "notify_job_executed"):
                        success = self.sender.notify_job_executed(ds_email, job_name)
                    else:
                        success = self.sender.send_notification(
                            ds_email,
                            f"Job Completed: {job_name}",
                            "Your job has finished",
                        )
                    if success:
                        self.state.mark_notified(job_name, "executed")
                        print("   ✅ Sent and marked as notified")
                    else:
                        print("   ❌ Failed to send")

    def _load_job_config(self, job_path: Path) -> Optional[Dict]:
        """Load job config.yaml"""
        config_file = job_path / "config.yaml"
        if not config_file.exists():
            return None

        try:
            with open(config_file, "r") as f:
                return yaml.safe_load(f)
        except (yaml.YAMLError, OSError, IOError) as e:
            print(f"⚠️  JobMonitor: Error reading job config {config_file}: {e}")
            return None

    @classmethod
    def from_config(cls, config_path: str):
        """
        Factory method: create monitor from YAML config file.

        Args:
            config_path: Path to configuration YAML file

        Config file format:
            syftbox_root: ~/SyftBox          # Required
            do_email: data_owner@email.com   # Required
            drive_token_path: ~/.syft-creds/token_do.json  # Optional (enables direct Drive polling)
            gmail_token_path: ~/.syft-creds/gmail_token.json  # Optional
            state_file: ~/.syft-creds/state.json  # Optional

        Returns:
            Configured JobMonitor instance
        """
        import yaml
        from pathlib import Path

        # Default paths for package-managed files
        DEFAULT_NOTIFICATION_DIR = Path.home() / ".syft-notifications"
        DEFAULT_GMAIL_TOKEN = DEFAULT_NOTIFICATION_DIR / "gmail_token.json"
        DEFAULT_STATE_FILE = DEFAULT_NOTIFICATION_DIR / "state.json"

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # Only business config is required from user
        required_keys = ["syftbox_root", "do_email"]
        missing = [k for k in required_keys if k not in config]
        if missing:
            raise ValueError(
                f"Configuration missing required keys: {missing}\n"
                f"Config file: {config_path}"
            )

        # Use defaults for token paths if not provided
        gmail_token_path = (
            Path(config["gmail_token_path"]).expanduser()
            if "gmail_token_path" in config
            else DEFAULT_GMAIL_TOKEN
        )
        state_path = (
            Path(config["state_file"]).expanduser()
            if "state_file" in config
            else DEFAULT_STATE_FILE
        )

        # Drive token is optional but enables direct polling
        drive_token_path = None
        if "drive_token_path" in config:
            drive_token_path = Path(config["drive_token_path"]).expanduser()

        from .gmail_auth import GmailAuth

        auth = GmailAuth()
        credentials = auth.load_credentials(gmail_token_path)

        from .gmail_sender import GmailSender

        # email_format: "html" (default), "text", or "both"
        email_format = config.get("email_format", "html")
        use_html = email_format in ["html", "both"]
        sender = GmailSender(credentials, use_html=use_html)

        from .json_state_manager import JsonStateManager

        state = JsonStateManager(state_path)

        return cls(
            syftbox_root=Path(config["syftbox_root"]),
            do_email=config["do_email"],
            sender=sender,
            state=state,
            config=config,
            drive_token_path=drive_token_path,
        )

    @classmethod
    def from_client(
        cls,
        client: "SyftboxManager",
        gmail_token_path: Optional[str] = None,
        drive_token_path: Optional[str] = None,
        notifications: bool = True,
    ):
        """
        Factory method: create monitor from syft-client.

        This is the recommended way to create a JobMonitor when working
        in a notebook with an existing client.

        Args:
            client: SyftboxManager from sc.login_do()
            gmail_token_path: Path to Gmail token (default: ~/.syft-notifications/gmail_token.json)
            drive_token_path: Path to Drive token (default: auto-detected from credentials dir)
            notifications: Enable/disable notifications (default True)

        Returns:
            Configured JobMonitor instance

        Example:
            client_do = sc.login_do(email=email_do, token_path=token_path_do)
            monitor = JobMonitor.from_client(client_do)
            monitor.start(interval=5)
        """
        if not client.is_do:
            raise ValueError(
                "JobMonitor should only run on Data Owner (DO) side. "
                "Use sc.login_do() instead of sc.login()."
            )

        # Default paths
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

        # Auto-detect drive token if not provided
        drive_path = None
        if drive_token_path:
            drive_path = Path(drive_token_path).expanduser()
        else:
            drive_path = cls._find_drive_token()

        from .gmail_auth import GmailAuth
        from .gmail_sender import GmailSender
        from .json_state_manager import JsonStateManager

        auth = GmailAuth()
        credentials = auth.load_credentials(gmail_path)
        sender = GmailSender(credentials, use_html=True)
        state = JsonStateManager(DEFAULT_STATE_FILE)

        config = {
            "notify_on_new_job": notifications,
            "notify_on_approved": notifications,
            "notify_on_executed": notifications,
        }

        return cls(
            syftbox_root=client.syftbox_folder,
            do_email=client.email,
            sender=sender,
            state=state,
            config=config,
            drive_token_path=drive_path,
            client=client,
        )

    @staticmethod
    def _find_drive_token() -> Optional[Path]:
        """Auto-detect Drive token from standard locations."""
        try:
            from syft_client import CREDENTIALS_DIR

            for token_name in ["token_do.json", "token.json"]:
                token_path = CREDENTIALS_DIR / token_name
                if token_path.exists():
                    return token_path
        except ImportError:
            # CREDENTIALS_DIR not available, skip token search in this location
            pass
        return None
