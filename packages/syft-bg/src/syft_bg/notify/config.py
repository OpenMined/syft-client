"""Configuration for notification service."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from syft_bg.common.config import get_default_paths, load_yaml


@dataclass
class NotifyConfig:
    """Configuration for the notification service."""

    do_email: Optional[str] = None
    syftbox_root: Optional[Path] = None
    drive_token_path: Optional[Path] = None
    gmail_token_path: Optional[Path] = None
    credentials_path: Optional[Path] = None
    interval: int = 30
    monitor_jobs: bool = True
    monitor_peers: bool = True

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "NotifyConfig":
        """Load config from YAML file."""
        if config_path is None:
            config_path = get_default_paths().config

        if not config_path.exists():
            return cls()

        data = load_yaml(config_path)
        common = {k: v for k, v in data.items() if not isinstance(v, dict)}
        notify_section = data.get("notify", {})
        merged = {**common, **notify_section}

        return cls(
            do_email=merged.get("do_email"),
            syftbox_root=Path(merged["syftbox_root"])
            if merged.get("syftbox_root")
            else None,
            drive_token_path=Path(merged["drive_token_path"])
            if merged.get("drive_token_path")
            else None,
            gmail_token_path=Path(merged["gmail_token_path"])
            if merged.get("gmail_token_path")
            else None,
            credentials_path=Path(merged["credentials_path"])
            if merged.get("credentials_path")
            else None,
            interval=merged.get("interval", 30),
            monitor_jobs=merged.get("monitor_jobs", True),
            monitor_peers=merged.get("monitor_peers", True),
        )
