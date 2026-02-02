from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

COLAB_DRIVE_PATH = Path("/content/drive/MyDrive")
CREDS_DIR_NAME = "syft-creds"


def get_creds_dir() -> Path:
    if COLAB_DRIVE_PATH.exists():
        return COLAB_DRIVE_PATH / CREDS_DIR_NAME
    return Path.home() / f".{CREDS_DIR_NAME}"


@dataclass
class DefaultPaths:
    config: Path
    drive_token: Path
    state: Path
    pid: Path
    log: Path


def get_default_paths() -> DefaultPaths:
    creds = get_creds_dir()
    return DefaultPaths(
        config=creds / "config.yaml",
        drive_token=creds / "token_do.json",
        state=creds / "approve" / "state.json",
        pid=creds / "approve" / "daemon.pid",
        log=creds / "approve" / "daemon.log",
    )


@dataclass
class JobApprovalConfig:
    enabled: bool = True
    peers_only: bool = True
    required_scripts: dict[str, str] = field(default_factory=dict)
    required_filenames: list[str] = field(default_factory=list)
    required_json_keys: dict[str, list[str]] = field(default_factory=dict)
    allowed_users: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "JobApprovalConfig":
        return cls(
            enabled=data.get("enabled", True),
            peers_only=data.get("peers_only", True),
            required_scripts=data.get("required_scripts", {}),
            required_filenames=data.get("required_filenames", []),
            required_json_keys=data.get("required_json_keys", {}),
            allowed_users=data.get("allowed_users", []),
        )


@dataclass
class PeerApprovalConfig:
    enabled: bool = False
    approved_domains: list[str] = field(default_factory=list)
    auto_share_datasets: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "PeerApprovalConfig":
        return cls(
            enabled=data.get("enabled", False),
            approved_domains=data.get("approved_domains", []),
            auto_share_datasets=data.get("auto_share_datasets", []),
        )


@dataclass
class ApproveConfig:
    do_email: Optional[str] = None
    syftbox_root: Optional[Path] = None
    drive_token_path: Optional[Path] = None
    interval: int = 5
    jobs: JobApprovalConfig = field(default_factory=JobApprovalConfig)
    peers: PeerApprovalConfig = field(default_factory=PeerApprovalConfig)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "ApproveConfig":
        if config_path is None:
            config_path = get_default_paths().config
        else:
            config_path = Path(config_path).expanduser()

        if not config_path.exists():
            return cls()

        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

        common = {k: v for k, v in data.items() if not isinstance(v, dict)}
        approve_section = data.get("approve", {})

        jobs_data = approve_section.get("jobs", {})
        peers_data = approve_section.get("peers", {})

        return cls(
            do_email=common.get("do_email"),
            syftbox_root=Path(common["syftbox_root"]).expanduser()
            if common.get("syftbox_root")
            else None,
            drive_token_path=Path(common["drive_token_path"]).expanduser()
            if common.get("drive_token_path")
            else None,
            interval=approve_section.get("interval", 5),
            jobs=JobApprovalConfig.from_dict(jobs_data),
            peers=PeerApprovalConfig.from_dict(peers_data),
        )

    def save(self, config_path: Optional[Path] = None) -> None:
        if config_path is None:
            config_path = get_default_paths().config
        else:
            config_path = Path(config_path).expanduser()

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

        data["approve"] = {
            "interval": self.interval,
            "jobs": {
                "enabled": self.jobs.enabled,
                "peers_only": self.jobs.peers_only,
                "required_scripts": self.jobs.required_scripts,
                "required_filenames": self.jobs.required_filenames,
                "required_json_keys": self.jobs.required_json_keys,
                "allowed_users": self.jobs.allowed_users,
            },
            "peers": {
                "enabled": self.peers.enabled,
                "approved_domains": self.peers.approved_domains,
                "auto_share_datasets": self.peers.auto_share_datasets,
            },
        }

        with open(config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
