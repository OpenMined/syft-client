import random
import io
import tarfile
import time
from syft_client.sync.environments.environment import Environment
from hashlib import sha256
from pathlib import Path


def check_env() -> Environment:
    try:
        import google.colab  # noqa: F401

        return Environment.COLAB
    except Exception:
        # this is bad, also do jupyter check
        return Environment.JUPYTER


def get_email_colab() -> str | None:
    from google.colab import auth
    from googleapiclient.discovery import build

    auth.authenticate_user()

    oauth2 = build("oauth2", "v2")
    userinfo = oauth2.userinfo().get().execute()
    return userinfo.get("email")


def get_event_hash_from_content(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


def create_event_timestamp() -> float:
    return time.time()


def random_email():
    return f"test{random.randint(1, 1000000)}@test.com"


def random_syftbox_folder_for_testing():
    return Path(f"/tmp/sb_folder_testing-{random.randint(1, 1000000)}")


def compress_data(data: bytes) -> bytes:
    tar_bytes = io.BytesIO()

    with tarfile.open(fileobj=tar_bytes, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="proposed_file_changes.json")
        info.size = len(data)
        tar.addfile(tarinfo=info, fileobj=io.BytesIO(data))
    tar_bytes.seek(0)
    compressed_data = tar_bytes.getvalue()
    return compressed_data


def uncompress_data(data: bytes) -> bytes:
    tar_bytes = io.BytesIO(data)
    with tarfile.open(fileobj=tar_bytes, mode="r:gz") as tar:
        info = tar.getmember("proposed_file_changes.json")
        data = tar.extractfile(info).read()
    return data
