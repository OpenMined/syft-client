"""Configuration utilities shared across services."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

COLAB_DRIVE_PATH = Path("/content/drive/MyDrive")
CREDS_DIR_NAME = "syft-creds"


def get_creds_dir() -> Path:
    """Get the credentials directory, handling Colab vs local environments."""
    if COLAB_DRIVE_PATH.exists():
        return COLAB_DRIVE_PATH / CREDS_DIR_NAME
    return Path.home() / f".{CREDS_DIR_NAME}"


@dataclass
class DefaultPaths:
    """Default paths for all services."""

    # Shared paths
    config: Path
    credentials: Path
    gmail_token: Path
    drive_token: Path

    # Notify service paths
    notify_state: Path
    notify_pid: Path
    notify_log: Path

    # Approve service paths
    approve_state: Path
    approve_pid: Path
    approve_log: Path


def get_default_paths() -> DefaultPaths:
    """Get default paths for all services."""
    creds = get_creds_dir()
    return DefaultPaths(
        # Shared
        config=creds / "config.yaml",
        credentials=creds / "credentials.json",
        gmail_token=creds / "gmail_token.json",
        drive_token=creds / "token_do.json",
        # Notify
        notify_state=creds / "notify" / "state.json",
        notify_pid=creds / "notify" / "daemon.pid",
        notify_log=creds / "notify" / "daemon.log",
        # Approve
        approve_state=creds / "approve" / "state.json",
        approve_pid=creds / "approve" / "daemon.pid",
        approve_log=creds / "approve" / "daemon.log",
    )


def load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML config file."""
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    """Save data to YAML config file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
