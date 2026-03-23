from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel


class JobStatus(str, Enum):
    """Status of a job in the system."""

    RECEIVED = "received"  # files arrived, not yet validated
    PENDING = "pending"  # validated, awaiting DO review
    APPROVED = "approved"  # DO approved, ready for execution
    REJECTED = "rejected"  # DO rejected
    RUNNING = "running"  # runner is executing
    DONE = "done"  # completed successfully
    FAILED = "failed"  # execution failed


class PartyApprovalStatus(BaseModel):
    """Tracks approval from a single party in a multi-party (enclave) job."""

    party: str
    dataset: Optional[str] = None
    status: JobStatus = JobStatus.PENDING
    approved_at: Optional[datetime] = None

    def save_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.model_dump(mode="json"), f)

    @classmethod
    def load_json(cls, path: Path) -> PartyApprovalStatus:
        with open(path, "r") as f:
            data = json.load(f)
        return cls(**data)


class JobState(BaseModel):
    """Represents the state of a job, stored as state.yaml in the review/ directory."""

    status: JobStatus = JobStatus.RECEIVED
    received_at: Optional[datetime] = None

    # Local job approval
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    # Rejection
    rejected_by: Optional[str] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    # Completion
    completed_at: Optional[datetime] = None
    return_code: Optional[int] = None

    # Multi-party approval (enclave jobs) — empty for local jobs
    approval_states: list[PartyApprovalStatus] = []

    @property
    def is_enclave_job(self) -> bool:
        """Check if the job is an enclave job."""
        return len(self.approval_states) > 0

    @property
    def all_parties_approved(self) -> bool:
        """Check if all parties have approved (for enclave jobs)."""
        if not self.is_enclave_job:
            return self.status == JobStatus.APPROVED
        return all(a.status == JobStatus.APPROVED for a in self.approval_states)

    @staticmethod
    def enclave_approval_file_name(do_email: str) -> str:
        return f"{do_email}_approval_state.json"

    @staticmethod
    def load_enclave_approval_files(review_dir: Path) -> list[PartyApprovalStatus]:
        """Load all *_approval_state.json files from review_dir."""
        if not review_dir.exists():
            return []
        results = []
        for f in sorted(review_dir.glob("*_approval_state.json")):
            results.append(PartyApprovalStatus.load_json(f))
        return results

    def save(self, path: Path) -> None:
        """Write state to a YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(self.model_dump(mode="json"), f, default_flow_style=False)

    @classmethod
    def load(cls, path: Path) -> JobState:
        """Load state from a YAML file."""
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)
