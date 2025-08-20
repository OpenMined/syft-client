"""
syft_client - Transport-agnostic client for decentralized file syncing

A Python library for secure, decentralized file synchronization across
multiple transport protocols (email, Google Drive, WebRTC, etc.).

Based on the Beach RFC specifications for transport-agnostic communication.
"""

from syft_client.gdrive_unified import GDriveUnifiedClient, create_gdrive_client
from syft_client.auth import login, list_accounts, logout, add_current_credentials_to_wallet

__version__ = "0.1.0"

__all__ = [
    "GDriveUnifiedClient", 
    "create_gdrive_client",
    "login",
    "list_accounts",
    "logout",
    "add_current_credentials_to_wallet"
]