from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from syft_client.platforms.google_common.gdrive_files import GDriveFilesTransport

# Path to credentials
CLIENT_SECRETS_PATH = "/Users/koen/Downloads/credentials.json"
SCOPES = ["https://www.googleapis.com/auth/drive"]

TOKEN_PATH = Path(__file__).parent / "token_koenlennartvanderveen@gmail.com.json"


def create_token():
    """Create a token for the GDriveFilesTransport"""
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_PATH, SCOPES)
    creds = flow.run_local_server(port=0)
    with open(TOKEN_PATH, "w") as token:
        token.write(creds.to_json())
    return creds


create_token()
