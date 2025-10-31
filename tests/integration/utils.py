from syft_client.syncv2.events.file_change_event import FileChangeEvent
from syft_client.syncv2.events.file_change_event import FileChangeEventFileName
import uuid
import time
from typing import List


def get_mock_event(path: str = "email@email.com/test.job") -> FileChangeEvent:
    file_path = path.split("/")[-1]
    content = "Hello, world!"
    new_hash = hash(content)
    return FileChangeEvent(
        id=uuid.uuid4(),
        path=file_path,
        submitted_timestamp=time.time(),
        timestamp=time.time(),
        content=content,
        new_hash=new_hash,
        event_filepath=FileChangeEventFileName(
            id=uuid.uuid4(),
            file_path=file_path,
            timestamp=time.time(),
        ),
    )


def get_mock_events(email: str, n_events: int = 2) -> List[FileChangeEvent]:
    res = [get_mock_event(f"{email}/test{i}.job") for i in range(n_events)]
    return res
