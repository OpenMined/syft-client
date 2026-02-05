"""Configuration for the approval service."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from syft_bg.common.config import get_default_paths


@dataclass
class JobApprovalConfig:
    """Configuration for job auto-approval."""

    enabled: bool = True
    peers_only: bool = True
    required_scripts: dict[str, str] = field(default_factory=dict)
    required_filenames: list[str] = field(default_factory=list)
    allowed_users: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "JobApprovalConfig":
        return cls(
            enabled=data.get("enabled", True),
            peers_only=data.get("peers_only", True),
            required_scripts=data.get("required_scripts", {}),
            required_filenames=data.get("required_filenames", []),
            allowed_users=data.get("allowed_users", []),
        )


@dataclass
class PeerApprovalConfig:
    """Configuration for peer auto-approval."""

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
    """Main configuration for the approval service."""

    do_email: Optional[str] = None
    syftbox_root: Optional[Path] = None
    drive_token_path: Optional[Path] = None
    interval: int = 5
    jobs: JobApprovalConfig = field(default_factory=JobApprovalConfig)
    peers: PeerApprovalConfig = field(default_factory=PeerApprovalConfig)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "ApproveConfig":
        """Load configuration from YAML file."""
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
        """Save configuration to YAML file."""
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
