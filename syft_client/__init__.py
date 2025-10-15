"""
syft_client - A unified client for secure file syncing
"""

from .syft_client import SyftClient

# Make login available at package level for convenience
login = SyftClient.login

# Wallet management
reset_wallet = SyftClient.reset_wallet_static

# Resolve Syft Paths
from .syft_client import resolve_path

__version__ = "0.1.85"

__all__ = ["login", "reset_wallet", "SyftClient", "resolve_path"]
