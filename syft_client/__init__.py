"""
syft_client - A unified client for secure file syncing
"""

from .syft_client import SyftClient

# Make login available at package level for convenience
login = SyftClient.login

# Wallet management
reset_wallet = SyftClient.reset_wallet_static

__version__ = "0.1.27"

__all__ = [
    "login",
    "reset_wallet",
    "SyftClient",
]