from pathlib import Path

from syft_perm import SyftPermContext

JOB_FOLDER_PATH = "app_data/job/"


def _ds_job_folder_path(ds_email: str) -> str:
    """Return the per-DS job folder path."""
    return f"{JOB_FOLDER_PATH}{ds_email}/"


def ensure_job_folder_permissions(
    syftbox_folder: Path, owner_email: str, ds_email: str, peer_emails: list[str]
) -> None:
    """Create/update permissions for a DS's job folder, granting write access to peers."""
    datasite = syftbox_folder / owner_email
    ctx = SyftPermContext(datasite=datasite)
    folder = ctx.open(_ds_job_folder_path(ds_email))
    for peer_email in peer_emails:
        folder.grant_write_access(peer_email)


def check_write_access(
    syftbox_folder: Path, owner_email: str, ds_email: str, sender_email: str
) -> bool:
    """Check if sender has write access to a DS's job folder."""
    datasite = syftbox_folder / owner_email
    ctx = SyftPermContext(datasite=datasite)
    folder = ctx.open(_ds_job_folder_path(ds_email))
    return folder.has_write_access(sender_email)
