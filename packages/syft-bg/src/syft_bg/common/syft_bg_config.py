"""Top-level SyftBg configuration model (mirrors config.yaml)."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from syft_bg.approve.config import AutoApproveConfig
from syft_bg.common.config import get_default_paths
from syft_bg.notify.config import NotifyConfig


class SyftBgConfig(BaseModel):
    """Top-level syft-bg configuration, matching the config.yaml structure."""

    do_email: str | None = None
    syftbox_root: str | None = None
    notify: NotifyConfig = Field(default_factory=NotifyConfig)
    approve: AutoApproveConfig = Field(default_factory=AutoApproveConfig)

    @classmethod
    def load(cls, config_path: Path | None = None) -> "SyftBgConfig":
        """Load from a YAML config file."""
        if config_path is None:
            config_path = get_default_paths().config

        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

        return cls.model_validate(data)

    def save(self, config_path: Path | None = None) -> None:
        """Write to a YAML config file."""
        if config_path is None:
            config_path = get_default_paths().config

        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            yaml.dump(
                self.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
            )
