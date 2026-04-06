"""Data contract between sync service and consumers."""

from typing import Optional

from pydantic import BaseModel


class InboxMessage(BaseModel):
    job_name: str
    submitter: str
    message_id: str


class SyncSnapshot(BaseModel):
    sync_time: float
    sync_count: int = 0
    sync_error: Optional[str] = None
    sync_duration_ms: int = 0

    job_names: list[str] = []
    approved_peer_emails: list[str] = []

    inbox_messages: list[InboxMessage] = []
    drive_peer_emails: list[str] = []
    drive_approved_peers: list[str] = []
