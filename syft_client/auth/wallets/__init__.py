"""Wallet implementations for secure credential storage"""

from .base import BaseWallet
from .local_file import LocalFileWallet

# Registry of available wallet types
AVAILABLE_WALLETS = {
    "local_file": LocalFileWallet,
    # Future wallets:
    # '1password': OnePasswordWallet,
    # 'keychain': KeychainWallet,
}


def get_wallet_class(wallet_type: str):
    """Get wallet class by type name"""
    if wallet_type not in AVAILABLE_WALLETS:
        raise ValueError(
            f"Unknown wallet type: {wallet_type}. Available types: {list(AVAILABLE_WALLETS.keys())}"
        )
    return AVAILABLE_WALLETS[wallet_type]


__all__ = ["BaseWallet", "LocalFileWallet", "get_wallet_class", "AVAILABLE_WALLETS"]
