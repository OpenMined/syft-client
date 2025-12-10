from syft_client.sync.syftbox_manager import SyftboxManager
import os
from pathlib import Path
from time import sleep
import pytest
from unittest.mock import patch
from dotenv import load_dotenv

SYFT_CLIENT_DIR = Path(__file__).parent.parent.parent
CREDENTIALS_DIR = SYFT_CLIENT_DIR / "credentials"

# inside credentials directory
# create .env and set the following variables:
# BEACH_EMAIL_DO=your_do_email
# BEACH_EMAIL_DS=your_ds_email
ENV_FILE = CREDENTIALS_DIR / ".env"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

FILE_DO = os.environ.get("beach_credentials_fname_do", "token_do.json")
EMAIL_DO = os.environ["BEACH_EMAIL_DO"]

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
    tokens_exist = token_path_do.exists() and token_path_ds.exists()
    if not tokens_exist:
        raise ValueError("Credentials not found")
    remove_syftboxes_from_drive()
    yield


@pytest.mark.usefixtures("setup_delete_syftboxes")
def test_early_termination_with_since_timestamp():
    from syft_client.sync.connections.drive.gdrive_transport import GDriveConnection

    manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
    )

    for i in range(5):
        manager_ds.send_file_change(f"{EMAIL_DO}/job_{i}.job", f"Job {i}")
        sleep(0.3)

    sleep(1)
    manager_do.sync()

    initial_events = (
        manager_do.proposed_file_change_handler.event_cache.get_cached_events()
    )
    assert len(initial_events) == 5

    # Use the latest processed event as the checkpoint so we only fetch truly new events
    checkpoint_timestamp = initial_events[-1].timestamp

    # Add buffer time to ensure new events have timestamps clearly after checkpoint
    sleep(2)

    for i in range(5, 8):
        manager_ds.send_file_change(f"{EMAIL_DO}/job_{i}.job", f"Job {i}")
        sleep(0.5)

    sleep(2)
    # Ensure DO processes the newly submitted jobs to emit events before DS pulls
    manager_do.sync()

    connection = manager_ds.datasite_outbox_puller.datasite_watcher_cache.connection_router.connection_for_datasite_watcher()

    # Add test-level logging to track early termination
    original_method = GDriveConnection.get_file_metadatas_from_folder
    call_num = [0]  # Use list to maintain state across calls

    def get_file_metadatas_with_logging(
        self, folder_id, since_timestamp=None, page_size=100
    ):
        call_num[0] += 1

        # Log before calling the method
        print(f"\n[TEST LOG] === API Call #{call_num[0]} ===")
        print(f"[TEST LOG] since_timestamp: {since_timestamp}")
        print(f"[TEST LOG] page_size: {page_size}")

        # Call original method
        result = original_method(self, folder_id, since_timestamp, page_size)

        # Log after getting results
        print(f"[TEST LOG] Total files returned: {len(result)}")
        if result:
            print("[TEST LOG] File names:")
            for f in result:
                print(f"[TEST LOG]   - {f['name']}")
        print(f"[TEST LOG] === End of API Call #{call_num[0]} ===\n")

        return result

    with patch.object(
        GDriveConnection,
        "get_file_metadatas_from_folder",
        get_file_metadatas_with_logging,
    ):
        new_events = connection.get_events_messages_for_datasite_watcher(
            EMAIL_DO, since_timestamp=checkpoint_timestamp
        )

    new_event_timestamps = [e.timestamp for e in new_events]
    assert all(t > checkpoint_timestamp for t in new_event_timestamps)
    assert len(new_events) == 3
    print(
        f"\n✅ Test PASSED: Early termination worked, only {len(new_events)} new events fetched"
    )
