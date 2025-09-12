"""Token wallet implementations for secure credential storage"""

from .base import BaseWallet
from .local_file import LocalFileWallet

# Registry of available wallet implementations
AVAILABLE_WALLETS = {
    'local_file': LocalFileWallet,
}

def get_wallet_class(wallet_type: str) -> type:
    """Get wallet class by type name"""
    if wallet_type not in AVAILABLE_WALLETS:
        raise ValueError(f"Unknown wallet type: {wallet_type}. Available: {list(AVAILABLE_WALLETS.keys())}")
    return AVAILABLE_WALLETS[wallet_type]

__all__ = [
    'BaseWallet',
    'LocalFileWallet',
    'AVAILABLE_WALLETS',
    'get_wallet_class',
]