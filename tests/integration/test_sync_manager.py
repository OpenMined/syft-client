from syft_client.syncv2.syftbox_manager import SyftboxManager
import os
from pathlib import Path
import time
from time import sleep
import pytest


SYFT_CLIENT_DIR = Path(__file__).parent.parent.parent
# These are in gitignore, create yourself
CREDENTIALS_DIR = SYFT_CLIENT_DIR / "credentials"

# koen gmail
file_do = os.environ.get("beach_credentials_fname_do", "token_do.json")
email_do = os.environ["BEACH_EMAIL_DO"]

# koen openmined mail
file_ds = os.environ.get("beach_credentials_fname_ds", "token_ds.json")
email_ds = os.environ["BEACH_EMAIL_DS"]


token_path_do = CREDENTIALS_DIR / file_do
token_path_ds = CREDENTIALS_DIR / file_ds


def remove_syftboxes_from_drive():
    manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=email_do,
        ds_email=email_ds,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        add_peers=False,
    )
    manager_ds.delete_syftbox()
    manager_do.delete_syftbox()


@pytest.fixture(scope="module", autouse=True)
def setup_current_file():
    print("\nCleaning up syftboxes from drive for integration tests")
    tokens_exist = token_path_do.exists() and token_path_ds.exists()
    if not tokens_exist:
        raise ValueError(
            """"Credentials not found, create them using scripts/create_token.py and store them in /credentials
            as token_do.json and token_ds.json. Also set the environment variables BEACH_EMAIL_DO and BEACH_EMAIL_DS to the email addresses of the DO and DS."""
        )
    remove_syftboxes_from_drive()
    print("Syftboxes deleted from drive, starting tests")
    yield
    print("Tearing down")


def test_google_drive_connection():
    manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=email_do,
        ds_email=email_ds,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
    )

    # this calls connection.send_propose_file_change_message via callbacks
    sleep(1)
    start_time = time.time()
    manager_ds.send_file_change(f"{email_do}/my.job", "Hello, world!")
    end_time_sending = time.time()
    print(f"Time taken to send message: {end_time_sending - start_time} seconds")

    # wait for the message to be sent, this is not always needed
    sleep(1)

    # this is just for timing purposes, you can ignore it
    # continuing with the test

    manager_do.proposed_file_change_handler.pull_and_process_next_proposed_filechange(
        sender_email=email_ds
    )

    manager_ds.sync()

    events = manager_ds.datasite_outbox_puller.datasite_watcher_cache.get_all_events()
    assert len(events) > 0
