__version__ = "0.1.0"

from syft_bg.api import (
    AuthResult,
    InitResult,
    StatusResult,
    authenticate,
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
