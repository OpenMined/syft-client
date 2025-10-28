from syft_client.syncv2.syftbox_manager import SyftboxManager
import os
from pathlib import Path
from time import sleep


SYFT_CLIENT_DIR = Path(__file__).parent.parent.parent
# These are in gitignore, create yourself
CREDENTIALS_DIR = SYFT_CLIENT_DIR / "credentials"

file_do = os.environ.get(
    "beach_credentials_1path", "token_koenlennartvanderveen@gmail.com.json"
)
file_ds = os.environ.get("beach_credentials_2path", "token_koen@openmined.org.json")

token_path_do = CREDENTIALS_DIR / file_do
token_path_ds = CREDENTIALS_DIR / file_ds


def test_google_drive_connection():
    manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email="koenlennartvanderveen@gmail.com",
        ds_email="koen@openmined.org",
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
    )

    # this eventually calls
    # connection.send_propose_file_change_message
    manager_ds.send_file_change(
        "koenlennartvanderveen@gmail.com/my.job", "Hello, world!"
    )
    # wait for the message to be sent
    sleep(1)

    manager_do.proposed_file_change_handler.pull_and_process_next_proposed_filechange(
        sender_email="koen@openmined.org"
    )

    manager_ds.datasite_outbox_puller.sync_down(
        peer_email="koenlennartvanderveen@gmail.com"
    )

    events = manager_ds.datasite_outbox_puller.datasite_watcher_cache.get_all_events()
    assert len(events) > 0
