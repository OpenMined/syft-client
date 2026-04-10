"""Pydantic model for persisting orchestrator setup results."""

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class SetupStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


class SetupState(BaseModel):
    """Persisted setup state for a background service."""

    service_name: str
    setup_status: SetupStatus
    error: Optional[str] = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, path: Path) -> Optional["SetupState"]:
        if not path.exists():
            return None
        return cls.model_validate_json(path.read_text())
