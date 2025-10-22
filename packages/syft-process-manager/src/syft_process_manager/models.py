from datetime import datetime
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, Field, field_validator

from syft_process_manager.utils import _utcnow, validate_process_name


class ProcessConfig(BaseModel):
    name: str
    cmd: list[str]
    env: dict[str, str] = Field(default_factory=dict)
    runner_type: str = "subprocess"
    created_at: datetime = Field(default_factory=_utcnow)
    process_dir: Path
    ttl_seconds: int | None = None
    log_level: str = "INFO"

    @field_validator("name")
    @classmethod
    def validate_name(cls: type[Self], v: Any) -> str:
        return validate_process_name(v)

    @classmethod
    def load(cls: type[Self], path: Path) -> Self:
        """Load config from config file, or process directory."""
        if path.is_dir():
            path = path / "config.json"
        content = path.read_text()
        return cls.model_validate_json(content)

    @property
    def config_path(self) -> Path:
        return self.process_dir / "config.json"

    @property
    def pid_path(self) -> Path:
        return self.process_dir / "pid.json"

    @property
    def health_path(self) -> Path:
        return self.process_dir / "health.json"

    @property
    def stdout_path(self) -> Path:
        return self.process_dir / "stdout.log"

    @property
    def stderr_path(self) -> Path:
        return self.process_dir / "stderr.log"

    @property
    def process_state_path(self) -> Path:
        return self.process_dir / "process_state.json"


class ProcessState(BaseModel):
    pid: int
    created_at: datetime = Field(default_factory=_utcnow)
    process_create_time: float  # Unix timestamp from psutil

    @classmethod
    def load(cls: type[Self], path: Path) -> Self:
        if path.is_dir():
            path = path / "process_state.json"
        content = path.read_text()
        return cls.model_validate_json(content)


class ProcessHealth(BaseModel):
    timestamp: datetime = Field(default_factory=_utcnow)
    status: str = "healthy"
    details: dict[str, Any] = Field(default_factory=dict)
