from syft_client.sync.events.file_change_event import FileChangeEvent
from syft_client.sync.events.file_change_event import FileChangeEventFileName
import uuid
import time
from typing import List
from syft_client.sync.utils.syftbox_utils import get_event_hash_from_content


def get_mock_event(path: str = "email@email.com/test.job") -> FileChangeEvent:
    email = path.split("/")[0]
    file_path = path.split("/")[-1]
    content = "Hello, world!"
    new_hash = get_event_hash_from_content(content)
    return FileChangeEvent(
        datasite_email=email,
        id=uuid.uuid4(),
        path_in_datasite=file_path,
        submitted_timestamp=time.time(),
        timestamp=time.time(),
        content=content,
        new_hash=new_hash,
        event_filepath=FileChangeEventFileName(
            id=uuid.uuid4(),
            file_path_in_datasite=file_path,
            timestamp=time.time(),
        ),
    )


def get_mock_events(email: str, n_events: int = 2) -> List[FileChangeEvent]:
    res = [get_mock_event(f"{email}/test{i}.job") for i in range(n_events)]
    return res
