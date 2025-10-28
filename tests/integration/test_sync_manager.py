from syft_client.syncv2.syftbox_manager import SyftboxManager
import os
from pathlib import Path
from time import sleep


SYFT_CLIENT_DIR = Path(__file__).parent.parent.parent
# These are in gitignore, create yourself
CREDENTIALS_DIR = SYFT_CLIENT_DIR / "credentials"

# koen gmail
file_do = os.environ.get("beach_credentials_fname_do", "token_do.json")
email_do = os.environ.get("beach_email_do", "koenlennartvanderveen@gmail.com")

# koen openmined mail
file_ds = os.environ.get("beach_credentials_fname_ds", "token_ds.json")
email_ds = os.environ.get("beach_email_ds", "koen@openmined.org")


token_path_do = CREDENTIALS_DIR / file_do
token_path_ds = CREDENTIALS_DIR / file_ds


def test_google_drive_connection():
    manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=email_do,
        ds_email=email_ds,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
    )

    # this eventually calls
    # connection.send_propose_file_change_message
    manager_ds.send_file_change(f"{email_do}/my.job", "Hello, world!")
    # wait for the message to be sent
    sleep(1)

    manager_do.proposed_file_change_handler.pull_and_process_next_proposed_filechange(
        sender_email=email_ds
    )

    manager_ds.datasite_outbox_puller.sync_down(peer_email=email_do)

    events = manager_ds.datasite_outbox_puller.datasite_watcher_cache.get_all_events()
    assert len(events) > 0
