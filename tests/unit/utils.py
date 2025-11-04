from syft_client.sync.events.file_change_event import FileChangeEvent
from syft_client.sync.events.file_change_event import FileChangeEventFileName
import uuid
from typing import List
import time
from syft_client.sync.messages.proposed_filechange import ProposedFileChangesMessage
from syft_client.sync.messages.proposed_filechange import ProposedFileChange
from syft_client.sync.utils.syftbox_utils import get_event_hash_from_content


def get_mock_event(path: str = "email@email.com/test.job") -> FileChangeEvent:
    file_path = path.split("/")[-1]
    content = "Hello, world!"
    new_hash = get_event_hash_from_content(content)
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


def get_mock_events(n_events: int = 2) -> List[FileChangeEvent]:
    res = [get_mock_event(f"email@email.com/test{i}.job") for i in range(n_events)]
    return res


def mock_message(path: str = "email@email.com/test.job") -> ProposedFileChangesMessage:
    return ProposedFileChangesMessage(
        sender_email="email@email.com",
        proposed_file_changes=[
            ProposedFileChange(
                old_hash=None,
                path=path,
                content="Hello, world!",
            ),
        ],
    )


def get_mock_proposed_events_messages(
    n_events: int = 2,
) -> List[ProposedFileChangesMessage]:
    return [mock_message(f"email@email.com/test{i}.job") for i in range(n_events)]
