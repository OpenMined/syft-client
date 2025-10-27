from syft_client.syncv2.syftbox_manager import SyftboxManager
import os
from pathlib import Path


SYFT_CLIENT_DIR = Path(__file__).parent.parent.parent
# These are in gitignore, create yourself
CREDENTIALS_DIR = SYFT_CLIENT_DIR / "credentials"

file1 = os.environ.get(
    "beach_credentials_1path", "token_koenlennartvanderveen@gmail.com.json"
)
file2 = os.environ.get("beach_credentials_2path", "token_koen@openmined.org.json")

token_path1 = CREDENTIALS_DIR / file1
token_path2 = CREDENTIALS_DIR / file2


def test_google_drive_connection():
    manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
        email1="koenlennartvanderveen@gmail.com",
        email2="koen@openmined.org",
        token_path1=token_path1,
        token_path2=token_path2,
    )

    # this eventually calls
    # connection.send_propose_file_change_message
    manager_ds.send_file_change(
        "koenlennartvanderveen@gmail.com/my.job", "Hello, world!"
    )

    manager_do.proposed_file_change_handler.pull_and_process_next_proposed_filechange()

    # manager1.sync_down()

    # assert len(manager1.get_all_events()) == 1
