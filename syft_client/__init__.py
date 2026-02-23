"""
syft_client - A unified client for secure file syncing
"""

from pathlib import Path
from syft_client.version import SYFT_CLIENT_VERSION as __version__  # noqa: F401
from syft_client.sync.login import login_do, login_ds, login  # noqa: F401
from syft_client.utils import resolve_path, resolve_dataset_file_path, bug_report  # noqa: F401
from syft_client.gdrive_utils import download_from_gdrive  # noqa: F401

SYFT_CLIENT_DIR = Path(__file__).parent.parent
CREDENTIALS_DIR = SYFT_CLIENT_DIR / "credentials"
