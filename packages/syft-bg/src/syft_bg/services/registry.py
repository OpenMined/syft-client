from pathlib import Path

from syft_bg.services.base import Service

# Default paths (same as syft-notify and syft-approve)
COLAB_DRIVE_PATH = Path("/content/drive/MyDrive")
CREDS_DIR_NAME = "syft-creds"


def get_creds_dir() -> Path:
    if COLAB_DRIVE_PATH.exists():
        return COLAB_DRIVE_PATH / CREDS_DIR_NAME
    return Path.home() / f".{CREDS_DIR_NAME}"


def _create_services() -> dict[str, Service]:
    creds = get_creds_dir()

    return {
        "notify": Service(
            name="notify",
            command="syft-notify",
            description="Email notifications for job and peer events",
            pid_file=creds / "notify" / "daemon.pid",
            log_file=creds / "notify" / "daemon.log",
        ),
        "approve": Service(
            name="approve",
            command="syft-approve",
            description="Auto-approve jobs and peer requests",
            pid_file=creds / "approve" / "daemon.pid",
            log_file=creds / "approve" / "daemon.log",
        ),
    }


SERVICES = _create_services()
