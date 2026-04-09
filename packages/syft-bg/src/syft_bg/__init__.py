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
    logs,
    restart,
    reset,
    start,
    stop,
)
from syft_bg.services import ServiceManager

__all__ = [
    "ServiceManager",
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
    "reset",
]


def __getattr__(name: str):
    if name == "status":
        from syft_bg.api import status

        return status()

    if name == "config":
        from syft_bg.common.syft_bg_config import SyftBgConfig

        try:
            return SyftBgConfig.from_path()
        except FileNotFoundError:
            print("No config file found, run syft_bg.init() first")
            return
    raise AttributeError(f"module 'syft_bg' has no attribute {name!r}")
