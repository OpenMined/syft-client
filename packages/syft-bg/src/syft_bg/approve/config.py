"""Configuration for the approval service."""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field

from syft_bg.common.config import get_default_paths


class FileEntry(BaseModel):
    """A file stored in the auto-approvals directory with its hash."""

    name: str  # e.g. "main.py"
    path: str  # e.g. "~/.syft-creds/auto_approvals/my_analysis/main.py"
    hash: str  # e.g. "sha256:abc123..."


class AutoApprovalObj(BaseModel):
    """An auto-approval object bundling content-matched files, name-only files, and peers."""

    file_contents: list[FileEntry] = Field(
        default_factory=list
    )  # files matched by content+hash
    file_names: list[str] = Field(default_factory=list)  # files matched by name only
    peers: list[str] = Field(default_factory=list)  # peer emails


class AutoApprovalsConfig(BaseModel):
    """Configuration for auto-approval objects."""

    enabled: bool = True
    objects: dict[str, AutoApprovalObj] = Field(default_factory=dict)


class PeerApprovalConfig(BaseModel):
    """Configuration for peer auto-approval."""

    enabled: bool = False
    approved_domains: list[str] = Field(default_factory=list)
    auto_share_datasets: list[str] = Field(default_factory=list)


class AutoApproveConfig(BaseModel):
    """Main configuration for the approval service."""

    do_email: Optional[str] = None
    syftbox_root: Optional[Path] = None
    drive_token_path: Optional[Path] = None
    interval: int = 5
    auto_approvals: AutoApprovalsConfig = Field(default_factory=AutoApprovalsConfig)
    peers: PeerApprovalConfig = Field(default_factory=PeerApprovalConfig)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "AutoApproveConfig":
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

        auto_approvals_data = approve_section.get("auto_approvals", {})
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
            auto_approvals=AutoApprovalsConfig(**auto_approvals_data)
            if auto_approvals_data
            else AutoApprovalsConfig(),
            peers=PeerApprovalConfig(**peers_data)
            if peers_data
            else PeerApprovalConfig(),
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
            "auto_approvals": self.auto_approvals.model_dump(),
            "peers": self.peers.model_dump(),
        }

        with open(config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)


# --- Backwards-compatible aliases (deprecated, will be removed) ---

ScriptEntry = FileEntry
ScriptRule = FileEntry


class PeerApprovalEntry(BaseModel):
    """Deprecated: use AutoApprovalObj instead."""

    mode: str = "strict"
    scripts: list[FileEntry] = Field(default_factory=list)


PeerJobConfig = PeerApprovalEntry


class JobApprovalConfig(BaseModel):
    """Deprecated: use AutoApprovalsConfig instead."""

    enabled: bool = True
    peers: dict[str, PeerApprovalEntry] = Field(default_factory=dict)
