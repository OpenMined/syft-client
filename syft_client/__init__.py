"""
syft_client - A unified client for secure file syncing
"""

from .syft_client import SyftClient

# Make login available at package level for convenience
login = SyftClient.login

__version__ = "0.1.7"

__all__ = [
    "login",
    "SyftClient",
]