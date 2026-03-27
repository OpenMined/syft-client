__version__ = "0.2.2"

from syft_bg.api import (
    AuthResult,
    AutoApproveResult,
    InitResult,
    StatusResult,
    authenticate,
    auto_approve,
    auto_approve_job,
    ensure_running,
    init,
    logs,
    restart,
    start,
    stop,
)
from syft_bg.services import ServiceManager

__all__ = [
    "ServiceManager",
    "init",
    "InitResult",
    "authenticate",
    "AuthResult",
    "auto_approve",
    "auto_approve_job",
    "AutoApproveResult",
    "status",
    "StatusResult",
    "start",
    "stop",
    "restart",
    "logs",
    "ensure_running",
]


def __getattr__(name: str):
    if name == "status":
        from syft_bg.api import status

        return status()
    raise AttributeError(f"module 'syft_bg' has no attribute {name!r}")
