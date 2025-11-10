import os
from syft_client import SYFT_CLIENT_DIR
from syft_client.sync.syftbox_manager import SyftboxManager

CREDENTIALS_DIR = SYFT_CLIENT_DIR / "credentials"

# koen gmail
FILE_DO = os.environ.get("beach_credentials_fname_do", "token_do.json")
EMAIL_DO = os.environ["BEACH_EMAIL_DO"]

# koen openmined mail
FILE_DS = os.environ.get("beach_credentials_fname_ds", "token_ds.json")
EMAIL_DS = os.environ["BEACH_EMAIL_DS"]

token_path_do = CREDENTIALS_DIR / FILE_DO
token_path_ds = CREDENTIALS_DIR / FILE_DS

tokens_exist = token_path_do.exists() and token_path_ds.exists()

if not tokens_exist:
    raise ValueError(
        """"Credentials not found, create them using scripts/create_token.py and store them in /credentials
        as token_do.json and token_ds.json. Also set the environment variables BEACH_EMAIL_DO and BEACH_EMAIL_DS to the email addresses of the DO and DS."""
    )

manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
    do_email=EMAIL_DO,
    ds_email=EMAIL_DS,
    do_token_path=token_path_do,
    ds_token_path=token_path_ds,
    add_peers=False,
    load_peers=False,
)
manager_ds.delete_syftbox()
manager_do.delete_syftbox()
