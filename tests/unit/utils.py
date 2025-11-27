from syft_client.sync.events.file_change_event import FileChangeEventsMessage
from syft_client.sync.events.file_change_event import FileChangeEvent
from syft_client.sync.events.file_change_event import FileChangeEventsMessageFileName
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
        event_filepath=FileChangeEventsMessageFileName(
            id=uuid.uuid4(),
            file_path_in_datasite=file_path,
            timestamp=time.time(),
        ),
    )


def get_mock_events_messages(n_events: int = 2) -> List[FileChangeEventsMessage]:
    return [
        FileChangeEventsMessage(events=[get_mock_event(f"email@email.com/test{i}.job")])
        for i in range(n_events)
    ]


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


def create_tmp_dataset_files_with_parquet():
    """Create temporary dataset files with parquet files (binary format)."""
    import pandas as pd

    tmp_dir = Path("/tmp/syft-datasets-testing") / str(random.randint(1, 1000000))
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # Create parquet files (binary format)
    mock_df = pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
            "age": [25, 30, 35, 28, 32],
            "score": [85.5, 90.0, 88.5, 92.0, 87.5],
        }
    )
    mock_path = tmp_dir / "mock_data.parquet"
    mock_df.to_parquet(mock_path, index=False)

    private_df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "sensitive_data": ["secret1", "secret2", "secret3"],
            "value": [100, 200, 300],
        }
    )
    private_path = tmp_dir / "private_data.parquet"
    private_df.to_parquet(private_path, index=False)

    readme_path = tmp_dir / "readme.md"
    readme_path.write_text(
        "# Dataset with Parquet Files\n\nThis dataset contains parquet files."
    )

    return mock_path, private_path, readme_path
