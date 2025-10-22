import re
from datetime import datetime
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, Field, field_validator

from syft_process_manager.utils import _utcnow, validate_process_name


class ProcessInfo(BaseModel):
    name: str
    pid: int
    cmd: list[str]
    runner_type: str = "subprocess"
    created_at: datetime = Field(default_factory=_utcnow)

    info_path: Path  # where to save this model
    process_dir: Path  # directory for logs and health info

    @field_validator("name")
    @classmethod
    def validate_name(cls: type[Self], v: Any) -> str:
        return validate_process_name(v)

    def save(self) -> int:
        self.info_path.parent.mkdir(parents=True, exist_ok=True)
        return self.info_path.write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls: type[Self], path: Path) -> Self:
        content = path.read_text()
        return cls.model_validate_json(content)

    @property
    def stdout_path(self) -> Path:
        return self.process_dir / "stdout.log"

    @property
    def stderr_path(self) -> Path:
        return self.process_dir / "stderr.log"

    @property
    def health_path(self) -> Path:
        return self.process_dir / "health.json"


class ProcessHealth(BaseModel):
    timestamp: datetime = Field(default_factory=_utcnow)
    status: str = "healthy"
    details: dict[str, Any] = Field(default_factory=dict)
