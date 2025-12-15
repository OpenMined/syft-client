from syft_client.sync.syftbox_manager import SyftboxManager
from time import sleep
import pytest
from unittest.mock import patch

from tests.integration.conftest import (
    get_email_do,
    get_email_ds,
    TOKEN_PATH_DO,
    TOKEN_PATH_DS,
)


@pytest.mark.usefixtures("setup_delete_syftboxes")
def test_pagination_with_small_page_size():
    from syft_client.sync.connections.drive.gdrive_transport import GDriveConnection

    EMAIL_DO = get_email_do()
    EMAIL_DS = get_email_ds()

    manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=TOKEN_PATH_DO,
        ds_token_path=TOKEN_PATH_DS,
    )

    for i in range(5):
        manager_ds.send_file_change(f"{EMAIL_DO}/job_{i}.job", f"Job {i}")
        sleep(0.2)

    sleep(1)

    original_method = GDriveConnection.get_file_metadatas_from_folder
    page_num = [0]  # Use list to maintain state across calls

    def get_files_page_size_2_with_logging(
        self, folder_id, since_timestamp=None, page_size=100
    ):
        page_num[0] += 1

        # Log before calling the method
        print(f"\n[TEST LOG] === API Call #{page_num[0]} ===")
        print(f"[TEST LOG] Forcing page_size=2 (instead of {page_size})")

        # Call original method with page_size=2
        result = original_method(self, folder_id, since_timestamp, page_size=2)

        # Log after getting results
        print(f"[TEST LOG] Total files returned: {len(result)}")
        if result:
            print("[TEST LOG] File names:")
            for f in result:
                print(f"[TEST LOG]   - {f['name']}")
        print(f"[TEST LOG] === End of API Call #{page_num[0]} ===\n")

        return result

    with patch.object(
        GDriveConnection,
        "get_file_metadatas_from_folder",
        get_files_page_size_2_with_logging,
    ):
        manager_do.sync()

    events = manager_do.proposed_file_change_handler.event_cache.get_cached_events()
    assert len(events) == 5
