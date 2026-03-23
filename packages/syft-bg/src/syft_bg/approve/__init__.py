"""Approval service for auto-approving jobs and peers."""

from syft_bg.approve.config import (
    ApproveConfig,
    AutoApprovalObj,
    AutoApprovalsConfig,
    PeerApprovalConfig,
    ScriptEntry,
)
from syft_bg.approve.orchestrator import ApprovalOrchestrator

__all__ = [
    "ApproveConfig",
    "AutoApprovalsConfig",
    "AutoApprovalObj",
    "ScriptEntry",
    "PeerApprovalConfig",
    "ApprovalOrchestrator",
]
