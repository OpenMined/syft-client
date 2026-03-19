from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel


class JobSubmissionMetadata(BaseModel):
    """Represents the job submission metadata, stored as config.yaml in inbox/."""

    name: str
    type: Literal["python", "bash"] = "python"
    submitted_by: str
    submitted_at: datetime
    entrypoint: Optional[str] = None
    dependencies: list[str] = []
    files: list[str] = []  # manifest of code/ contents
    is_folder_submission: bool = False
    code_path: Optional[str] = None  # original source path (informational)
    job_type: Literal["local", "enclave"] = "local"

    def save(self, path: Path) -> None:
        """Write config to a YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(self.model_dump(mode="json"), f, default_flow_style=False)

    @classmethod
    def load(cls, path: Path) -> JobSubmissionMetadata:
        """Load config from a YAML file."""
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)
