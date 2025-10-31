from syft_client.sync.syftbox_manager import SyftboxManager
import os
from pathlib import Path
import time
from time import sleep
import pytest
from tests.integration.utils import get_mock_events

# from tests.integration.utils import get_mock_events


SYFT_CLIENT_DIR = Path(__file__).parent.parent.parent
# These are in gitignore, create yourself
CREDENTIALS_DIR = SYFT_CLIENT_DIR / "credentials"

# koen gmail
FILE_DO = os.environ.get("beach_credentials_fname_do", "token_do.json")
EMAIL_DO = os.environ["BEACH_EMAIL_DO"]

# koen openmined mail
FILE_DS = os.environ.get("beach_credentials_fname_ds", "token_ds.json")
EMAIL_DS = os.environ["BEACH_EMAIL_DS"]


token_path_do = CREDENTIALS_DIR / FILE_DO
token_path_ds = CREDENTIALS_DIR / FILE_DS


def remove_syftboxes_from_drive():
    manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        add_peers=False,
    )
    manager_ds.delete_syftbox()
    manager_do.delete_syftbox()


@pytest.fixture()
def setup_delete_syftboxes():
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


@pytest.mark.usefixtures("setup_delete_syftboxes")
def test_google_drive_connection_syncing():
    manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
    )

    # this calls connection.send_propose_file_change_message via callbacks
    sleep(1)
    start_time = time.time()
    manager_ds.send_file_change(f"{EMAIL_DO}/my.job", "Hello, world!")
    end_time_sending = time.time()
    print(f"Time taken to send message: {end_time_sending - start_time} seconds")

    # wait for the message to be sent, this is not always needed
    sleep(1)

    # this is just for timing purposes, you can ignore it
    # continuing with the test

    manager_do.proposed_file_change_handler.pull_and_process_next_proposed_filechange(
        sender_email=EMAIL_DS
    )

    manager_ds.sync()

    events = (
        manager_ds.datasite_outbox_puller.datasite_watcher_cache.get_cached_events()
    )
    assert len(events) > 0


@pytest.mark.usefixtures("setup_delete_syftboxes")
def test_google_drive_connection_load_state():
    # create the state

    # load the clients and add the peers
    manager_ds1, manager_do1 = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        add_peers=True,
        load_peers=False,
    )

    # make some changes
    manager_ds1.send_file_change(f"{EMAIL_DO}/my.job", "Hello, world!")
    manager_ds1.send_file_change(f"{EMAIL_DO}/my_second.job", "Hello, world!")

    # test loading the peers and loading the inbox
    manager_ds2, manager_do2 = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        add_peers=False,
        load_peers=False,
    )

    manager_do2.load_peers()
    assert len(manager_do2.peers) == 1

    manager_ds2.load_peers()
    assert len(manager_ds2.peers) == 1

    # sync so we have something in the syftbox and do outbox
    manager_do2.sync()

    assert (
        len(manager_do2.proposed_file_change_handler.event_cache.get_cached_events())
        == 2
    )

    # we have created some state now, so now we can log in again and load the state
    manager_ds3, manager_do3 = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        add_peers=False,
        load_peers=True,
    )

    manager_do3.sync()
    manager_ds3.sync()

    loaded_events_do = (
        manager_do3.proposed_file_change_handler.event_cache.get_cached_events()
    )
    assert len(loaded_events_do) == 2

    loaded_events_ds = (
        manager_ds3.datasite_outbox_puller.datasite_watcher_cache.get_cached_events()
    )
    assert len(loaded_events_ds) == 2
