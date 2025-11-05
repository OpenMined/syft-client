from syft_client.sync.events.file_change_event import FileChangeEvent
from syft_client.sync.events.file_change_event import FileChangeEventFileName
from pathlib import Path
import uuid
import random
from typing import List
import time
from syft_client.sync.messages.proposed_filechange import ProposedFileChangesMessage
from syft_client.sync.messages.proposed_filechange import ProposedFileChange
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


def get_mock_events(n_events: int = 2) -> List[FileChangeEvent]:
    res = [get_mock_event(f"email@email.com/test{i}.job") for i in range(n_events)]
    return res


def mock_message(path: str = "email@email.com/test.job") -> ProposedFileChangesMessage:
    email = path.split("/")[0]
    return ProposedFileChangesMessage(
        sender_email="email@email.com",
        proposed_file_changes=[
            ProposedFileChange(
                old_hash=None,
                path_in_datasite=path,
                content="Hello, world!",
                datasite_email=email,
            ),
        ],
    )


def get_mock_proposed_events_messages(
    n_events: int = 2,
) -> List[ProposedFileChangesMessage]:
    return [mock_message(f"email@email.com/test{i}.job") for i in range(n_events)]


def create_tmp_dataset_files():
    tmp_dir = Path("/tmp/syft-datasets-testing") / str(random.randint(1, 1000000))
    tmp_dir.mkdir(parents=True, exist_ok=True)
    mock_path = tmp_dir / "mock.txt"
    private_path = tmp_dir / "private.txt"
    readme_path = tmp_dir / "readme.md"
    mock_path.write_text("Hello, world!")
    private_path.write_text("Hello, world!")
    readme_path.write_text("Hello, world!")
    return mock_path, private_path, readme_path
