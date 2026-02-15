"""Job monitor for detecting new jobs and status changes."""

import time
from pathlib import Path
from typing import Any, Optional

import yaml

from syft_bg.common.drive import create_drive_service, is_colab
from syft_bg.common.monitor import Monitor
from syft_bg.common.state import JsonStateManager
from syft_bg.notify.handlers.job import JobHandler

GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX = "syft_outbox_inbox"
GOOGLE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


class JobMonitor(Monitor):
    """Monitors for new jobs and job status changes."""

    def __init__(
        self,
        syftbox_root: Path,
        do_email: str,
        handler: JobHandler,
        state: JsonStateManager,
        drive_token_path: Optional[Path] = None,
    ):
        super().__init__()
        self.syftbox_root = Path(syftbox_root).expanduser()
        self.do_email = do_email
        self.handler = handler
        self.state = state
        self.job_dir = self.syftbox_root / do_email / "app_data" / "job"
        self.drive_token_path = Path(drive_token_path) if drive_token_path else None
        self._drive_service = None
        self._startup_time = time.time()  # Track when monitor started
        self._is_fresh_state = self.state.is_empty()  # True if no prior state

        if is_colab() or (self.drive_token_path and self.drive_token_path.exists()):
            self._drive_service = create_drive_service(self.drive_token_path)

    def _check_all_entities(self):
        if self._drive_service:
            self._poll_drive_for_new_jobs()
        self._check_local_for_status_changes()

    def _poll_drive_for_new_jobs(self):
        if not self._drive_service:
            return

        for ds_email, folder_id in self._find_inbox_folders():
            messages = self._get_pending_messages(folder_id)

            for msg_file in messages:
                msg_id = msg_file["id"]

                if self.state.was_notified(f"msg_{msg_id}", "processed"):
                    continue

                job_info = self._parse_job_from_message(msg_id, ds_email)
                if job_info:
                    self._handle_new_job_from_drive(job_info)

                self.state.mark_notified(f"msg_{msg_id}", "processed")

    def _find_inbox_folders(self) -> list[tuple[str, str]]:
        if not self._drive_service:
            return []

        try:
            query = (
                f"name contains '{GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX}' and "
                f"name contains '_to_{self.do_email}' and "
                f"mimeType = '{GOOGLE_FOLDER_MIME_TYPE}' and "
                "trashed=false"
            )
            results = self._drive_service.files().list(q=query).execute()

            folders = []
            for folder in results.get("files", []):
                name = folder["name"]
                parts = name.split("_")
                if len(parts) >= 6:
                    sender_email = parts[3]
                    if sender_email != self.do_email:
                        folders.append((sender_email, folder["id"]))
            return folders

        except Exception as e:
            print(f"[JobMonitor] Error finding inbox folders: {e}")
            return []

    def _get_pending_messages(self, folder_id: str) -> list[dict[str, Any]]:
        if not self._drive_service:
            return []

        try:
            query = (
                f"'{folder_id}' in parents and name contains 'msgv2_' and trashed=false"
            )
            results = (
                self._drive_service.files()
                .list(q=query, fields="files(id, name)", orderBy="name")
                .execute()
            )
            return results.get("files", [])

        except Exception as e:
            print(f"[JobMonitor] Error getting messages: {e}")
            return []

    def _parse_job_from_message(
        self, file_id: str, ds_email: str
    ) -> Optional[dict[str, Any]]:
        if not self._drive_service:
            return None

        try:
            from syft_client.sync.messages.proposed_filechange import (
                ProposedFileChangesMessage,
            )

            request = self._drive_service.files().get_media(fileId=file_id)
            content = request.execute()
            msg = ProposedFileChangesMessage.from_compressed_data(content)

            for change in msg.proposed_file_changes:
                path = str(change.path_in_datasite)
                if "app_data/job/" in path and path.endswith("config.yaml"):
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
            print(f"[JobMonitor] Error parsing message {file_id}: {e}")
            return None

    def _handle_new_job_from_drive(self, job_info: dict[str, Any]):
        job_name = job_info["job_name"]
        submitter = job_info["submitter"]

        success = self.handler.on_new_job(self.do_email, job_name, submitter)
        if success:
            print(
                f"[JobMonitor] Sent new job notification: {job_name} from {submitter}"
            )

    def _check_local_for_status_changes(self):
        if not self.job_dir.exists():
            return

        for job_path in self.job_dir.iterdir():
            if not job_path.is_dir():
                continue
            try:
                self._check_job_status(job_path)
            except Exception as e:
                print(f"[JobMonitor] Error checking job {job_path.name}: {e}")

    def _check_job_status(self, job_path: Path):
        config = self._load_job_config(job_path)
        if not config:
            return

        job_name = config.get("name", job_path.name)
        ds_email = config.get("submitted_by")

        if not ds_email:
            return

        # Skip old jobs on fresh state (avoid spamming about pre-existing jobs)
        # But process normally on restart (state exists) to catch missed notifications
        if self._is_fresh_state:
            config_file = job_path / "config.yaml"
            if config_file.exists():
                job_created = config_file.stat().st_mtime
                if job_created < self._startup_time:
                    # Fresh state + old job = skip (first-time setup scenario)
                    return

        # Check for new job (if not already notified)
        if not self.state.was_notified(job_name, "new"):
            success = self.handler.on_new_job(self.do_email, job_name, ds_email)
            if success:
                print(f"📬 JobMonitor: Sent new job notification: {job_name}")

        if (job_path / "approved").exists():
            success = self.handler.on_job_approved(ds_email, job_name)
            if success:
                print(f"✅ JobMonitor: Sent job approved notification: {job_name}")

        if (job_path / "done").exists():
            success = self.handler.on_job_executed(ds_email, job_name)
            if success:
                print(f"🎉 JobMonitor: Sent job executed notification: {job_name}")

    def _load_job_config(self, job_path: Path) -> Optional[dict]:
        config_file = job_path / "config.yaml"
        if not config_file.exists():
            return None

        try:
            with open(config_file, "r") as f:
                return yaml.safe_load(f)
        except (yaml.YAMLError, OSError, IOError) as e:
            print(f"[JobMonitor] Error reading job config {config_file}: {e}")
            return None
