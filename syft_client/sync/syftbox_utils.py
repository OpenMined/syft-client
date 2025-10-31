import random
import io
import tarfile
import time


def create_event_timestamp() -> float:
    return time.time()


def random_email():
    return f"test{random.randint(1, 1000000)}@test.com"


def random_base_path():
    return f"/tmp/syftbox{random.randint(1, 1000000)}"


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
