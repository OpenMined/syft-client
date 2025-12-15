"""
Pytest fixtures for integration tests.

Common fixtures for Google Drive integration tests including credentials,
email configuration, and syftbox cleanup.
"""

import os
from pathlib import Path
import pytest

from syft_client.sync.syftbox_manager import SyftboxManager


# Directory paths
SYFT_CLIENT_DIR = Path(__file__).parent.parent.parent
CREDENTIALS_DIR = SYFT_CLIENT_DIR / "credentials"

# Credential files (in gitignore, create yourself)
FILE_DO = os.environ.get("beach_credentials_fname_do", "token_do.json")
FILE_DS = os.environ.get("beach_credentials_fname_ds", "token_ds.json")

# Token paths
TOKEN_PATH_DO = CREDENTIALS_DIR / FILE_DO
TOKEN_PATH_DS = CREDENTIALS_DIR / FILE_DS


def get_email_do():
    """Get DO email from environment variable."""
    return os.environ["BEACH_EMAIL_DO"]


def get_email_ds():
    """Get DS email from environment variable."""
    return os.environ["BEACH_EMAIL_DS"]


def remove_syftboxes_from_drive():
    """Delete all syftboxes from Google Drive for clean test state."""
    manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=get_email_do(),
        ds_email=get_email_ds(),
        do_token_path=TOKEN_PATH_DO,
        ds_token_path=TOKEN_PATH_DS,
        add_peers=False,
    )
    manager_ds.delete_syftbox()
    manager_do.delete_syftbox()


def check_credentials_exist():
    """Check if credentials files and environment variables are configured."""
    tokens_exist = TOKEN_PATH_DO.exists() and TOKEN_PATH_DS.exists()
    if not tokens_exist:
        raise ValueError(
            """Credentials not found. Create them using scripts/create_token.py
            and store them in /credentials as token_do.json and token_ds.json.
            Also set the environment variables BEACH_EMAIL_DO and BEACH_EMAIL_DS
            to the email addresses of the DO and DS."""
        )
    # Also verify environment variables are set
    try:
        get_email_do()
        get_email_ds()
    except KeyError as e:
        raise ValueError(f"Environment variable {e} not set") from e


@pytest.fixture()
def setup_delete_syftboxes():
    """
    Fixture that cleans up syftboxes before each test.

    Usage:
        @pytest.mark.usefixtures("setup_delete_syftboxes")
        def test_something():
            ...
    """
    print("\nCleaning up syftboxes from drive for integration tests")
    check_credentials_exist()
    remove_syftboxes_from_drive()
    print("Syftboxes deleted from drive, starting tests")
    yield
    print("Tearing down")


@pytest.fixture()
def gdrive_managers():
    """
    Fixture that provides configured DS and DO managers for Google Drive testing.

    Returns:
        tuple: (manager_ds, manager_do)

    Usage:
        def test_something(gdrive_managers):
            manager_ds, manager_do = gdrive_managers
            ...
    """
    check_credentials_exist()
    manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=get_email_do(),
        ds_email=get_email_ds(),
        do_token_path=TOKEN_PATH_DO,
        ds_token_path=TOKEN_PATH_DS,
    )
    return manager_ds, manager_do


@pytest.fixture()
def gdrive_managers_fresh(setup_delete_syftboxes):
    """
    Fixture that provides fresh DS and DO managers after cleaning syftboxes.

    This combines setup_delete_syftboxes with gdrive_managers for convenience.

    Returns:
        tuple: (manager_ds, manager_do)

    Usage:
        def test_something(gdrive_managers_fresh):
            manager_ds, manager_do = gdrive_managers_fresh
            ...
    """
    manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=get_email_do(),
        ds_email=get_email_ds(),
        do_token_path=TOKEN_PATH_DO,
        ds_token_path=TOKEN_PATH_DS,
    )
    return manager_ds, manager_do
