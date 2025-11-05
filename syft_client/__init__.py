"""
syft_client - A unified client for secure file syncing
"""

from pathlib import Path
from syft_client.sync.login import login_do, login_ds, login  # noqa: F401
from syft_client.utils import resolve_path  # noqa: F401

__version__ = "0.1.88"

SYFT_CLIENT_DIR = Path(__file__).parent.parent
CREDENTIALS_DIR = SYFT_CLIENT_DIR / "credentials"
