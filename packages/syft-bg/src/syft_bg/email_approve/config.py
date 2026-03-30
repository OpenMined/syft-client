"""Configuration for email-based approval service."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from syft_bg.common.config import get_default_paths, load_yaml, save_yaml


@dataclass
class EmailApproveConfig:
    """Configuration for the email approval service."""

    do_email: Optional[str] = None
    syftbox_root: Optional[Path] = None
    gmail_token_path: Optional[Path] = None
    drive_token_path: Optional[Path] = None
    credentials_path: Optional[Path] = None
    gcp_project_id: Optional[str] = None
    pubsub_topic: Optional[str] = None
    pubsub_subscription: Optional[str] = None

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "EmailApproveConfig":
        """Load config from YAML file."""
        if config_path is None:
            config_path = get_default_paths().config

        if not config_path.exists():
            return cls()

        data = load_yaml(config_path)
        common = {k: v for k, v in data.items() if not isinstance(v, dict)}
        section = data.get("email_approve", {})
        merged = {**common, **section}

        return cls(
            do_email=merged.get("do_email"),
            syftbox_root=Path(merged["syftbox_root"])
            if merged.get("syftbox_root")
            else None,
            gmail_token_path=Path(merged["gmail_token_path"])
            if merged.get("gmail_token_path")
            else None,
            drive_token_path=Path(merged["drive_token_path"])
            if merged.get("drive_token_path")
            else None,
            credentials_path=Path(merged["credentials_path"])
            if merged.get("credentials_path")
            else None,
            gcp_project_id=merged.get("gcp_project_id"),
            pubsub_topic=merged.get("pubsub_topic"),
            pubsub_subscription=merged.get("pubsub_subscription"),
        )

    def save_pubsub_config(self, config_path: Optional[Path] = None) -> None:
        """Save Pub/Sub settings back to config.yaml."""
        if config_path is None:
            config_path = get_default_paths().config

        data = load_yaml(config_path)
        if "email_approve" not in data:
            data["email_approve"] = {}

        data["email_approve"]["gcp_project_id"] = self.gcp_project_id
        data["email_approve"]["pubsub_topic"] = self.pubsub_topic
        data["email_approve"]["pubsub_subscription"] = self.pubsub_subscription
        save_yaml(config_path, data)
