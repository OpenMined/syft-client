"""Approval service for auto-approving jobs and peers."""

from syft_bg.approve.config import ApproveConfig, JobApprovalConfig, PeerApprovalConfig
from syft_bg.approve.orchestrator import ApprovalOrchestrator

__all__ = [
    "ApproveConfig",
    "JobApprovalConfig",
    "PeerApprovalConfig",
    "ApprovalOrchestrator",
]
