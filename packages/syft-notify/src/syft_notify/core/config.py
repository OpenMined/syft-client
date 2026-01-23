from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

COLAB_DRIVE_PATH = Path("/content/drive/MyDrive")
CREDS_DIR_NAME = "syft-creds"


def get_creds_dir() -> Path:
    if COLAB_DRIVE_PATH.exists():
        return COLAB_DRIVE_PATH / CREDS_DIR_NAME
    return Path.home() / f".{CREDS_DIR_NAME}"


def get_default_paths() -> dict:
    creds = get_creds_dir()
    return {
        "config": creds / "config.yaml",
        "credentials": creds / "credentials.json",
        "gmail_token": creds / "gmail_token.json",
        "drive_token": creds / "token_do.json",
        "state": creds / "notify" / "state.json",
        "pid": creds / "notify" / "daemon.pid",
        "log": creds / "notify" / "daemon.log",
    }


@dataclass
class NotifyConfig:
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
        if config_path is None:
            config_path = get_default_paths()["config"]

        if not config_path.exists():
            return cls()

        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

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

    def save(self, config_path: Optional[Path] = None) -> None:
        if config_path is None:
            config_path = get_default_paths()["config"]

        config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {}
        if config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}

        if self.do_email:
            data["do_email"] = self.do_email
        if self.syftbox_root:
            data["syftbox_root"] = str(self.syftbox_root)
        if self.drive_token_path:
            data["drive_token_path"] = str(self.drive_token_path)
        if self.gmail_token_path:
            data["gmail_token_path"] = str(self.gmail_token_path)
        if self.credentials_path:
            data["credentials_path"] = str(self.credentials_path)

        data["notify"] = {
            "interval": self.interval,
            "monitor_jobs": self.monitor_jobs,
            "monitor_peers": self.monitor_peers,
        }

        with open(config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
