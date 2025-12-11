from pathlib import Path
import json
import tarfile
import tempfile

import pytest
import yaml

from syft_client.sync.messages.proposed_filechange import ProposedFileChangesMessage
from syft_client.sync.syftbox_manager import SyftboxManager
from syft_client.sync.connections.inmemory_connection import InMemoryBackingPlatform
from syft_client.sync.messages.proposed_filechange import ProposedFileChange
from syft_datasets.dataset import Dataset
from tests.unit.utils import (
    create_tmp_dataset_files,
    create_tmp_dataset_files_with_parquet,
)

from syft_client.sync.sync.caches.datasite_owner_cache import (
    ProposedEventFileOutdatedException,
)
from tests.unit.utils import get_mock_events_messages
from tests.unit.utils import get_mock_proposed_events_messages


def test_in_memory_connection():
    file_path = "email@email.com/my.job"
    manager1, manager2 = SyftboxManager.pair_with_in_memory_connection()
    message_received = False

    def patch_job_handler_file_receive(*args, **kwargs):
        nonlocal message_received
        message_received = True

    manager2.job_file_change_handler.handle_file_change = patch_job_handler_file_receive

    manager1.send_file_change(file_path, "Hello, world!")
    assert message_received


def test_sync_to_syftbox_eventlog():
    file_path = "email@email.com/my.job"
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()

    # no events initially
    events_in_backing_platform = do_manager.get_all_accepted_events_do()
    assert len(events_in_backing_platform) == 0

    ds_manager.send_file_change(file_path, "Hello, world!")

    # first event is present
    events_in_backing_platform = do_manager.get_all_accepted_events_do()
    assert len(events_in_backing_platform) > 0


def test_valid_and_invalid_proposed_filechange_event():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()
    ds_email = ds_manager.email
    do_email = do_manager.email

    path_from_syftbox = "email@email.com/test.job"
    path_in_datasite = path_from_syftbox.split("/")[-1]

    message_1 = ProposedFileChangesMessage(
        sender_email=ds_email,
        proposed_file_changes=[
            ProposedFileChange(
                old_hash=None,
                path_in_datasite=path_in_datasite,
                content="Content 1",
                datasite_email=do_email,
            )
        ],
    )

    hash1 = message_1.proposed_file_changes[0].new_hash
    do_manager.proposed_file_change_handler.handle_proposed_filechange_events_message(
        ds_email, message_1
    )

    message_2 = ProposedFileChangesMessage(
        sender_email=ds_email,
        proposed_file_changes=[
            ProposedFileChange(
                old_hash=hash1,
                path_in_datasite=path_in_datasite,
                content="Content 2",
                datasite_email=do_email,
            )
        ],
    )
    do_manager.proposed_file_change_handler.handle_proposed_filechange_events_message(
        ds_email, message_2
    )

    content = (
        do_manager.proposed_file_change_handler.event_cache.file_connection.read_file(
            path_in_datasite
        )
    )
    assert content == "Content 2"

    message_3_outdated = ProposedFileChangesMessage(
        sender_email=ds_email,
        proposed_file_changes=[
            ProposedFileChange(
                old_hash=hash1,
                path_in_datasite=path_in_datasite,
                content="Content 3",
                datasite_email=do_email,
            )
        ],
    )

    # This should fail, as the event is outdated
    with pytest.raises(ProposedEventFileOutdatedException):
        do_manager.proposed_file_change_handler.handle_proposed_filechange_events_message(
            ds_email, message_3_outdated
        )

    content = (
        do_manager.proposed_file_change_handler.event_cache.file_connection.read_file(
            path_in_datasite
        )
    )
    assert content == "Content 2"


def test_sync_back_to_ds_cache():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()
    file_path = "email@email.com/test.job"
    ds_manager.send_file_change(file_path, "Hello, world!")

    ds_manager.sync()
    assert (
        len(
            ds_manager.datasite_outbox_puller.datasite_watcher_cache.get_cached_events()
        )
        == 1
    )


def test_sync_existing_datasite_state_do():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()

    store: InMemoryBackingPlatform = do_manager.connection_router.connections[
        0
    ].backing_store

    events_messages = get_mock_events_messages(2)

    store.syftbox_events_message_log.extend(events_messages)
    store.outboxes["all"].extend(events_messages)

    # sync down existing state
    do_manager.sync()

    n_messages_in_cache = len(
        do_manager.proposed_file_change_handler.event_cache.events_messages_connection
    )
    n_files_in_cache = len(
        do_manager.proposed_file_change_handler.event_cache.file_connection
    )
    hashes_in_cache = len(
        do_manager.proposed_file_change_handler.event_cache.file_hashes
    )
    assert n_messages_in_cache == 2
    assert n_files_in_cache == 2
    assert hashes_in_cache == 2
    # outbox should still be 2
    assert len(store.outboxes["all"]) == 2


def test_sync_existing_inbox_state_do():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()
    store: InMemoryBackingPlatform = do_manager.connection_router.connections[
        0
    ].backing_store

    proposed_events_messages = get_mock_proposed_events_messages(2)
    store.proposed_events_inbox.extend(proposed_events_messages)

    do_manager.sync()

    n_events_message_in_cache = len(
        do_manager.proposed_file_change_handler.event_cache.events_messages_connection
    )
    n_files_in_cache = len(
        do_manager.proposed_file_change_handler.event_cache.file_connection
    )
    hashes_in_cache = len(
        do_manager.proposed_file_change_handler.event_cache.file_hashes
    )
    assert n_events_message_in_cache == 2
    assert n_files_in_cache == 2
    assert hashes_in_cache == 2

    n_events_in_syftbox = len(
        do_manager.connection_router.connections[
            0
        ].backing_store.syftbox_events_message_log
    )
    assert n_events_in_syftbox == 2

    assert len(store.outboxes["all"]) == 2


def test_sync_existing_datasite_state_ds():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()

    store: InMemoryBackingPlatform = ds_manager.connection_router.connections[
        0
    ].backing_store

    events_messages = get_mock_events_messages(2)
    store.syftbox_events_message_log.extend(events_messages)
    store.outboxes["all"].extend(events_messages)

    ds_manager.sync()

    ds_events_in_cache = len(
        ds_manager.datasite_outbox_puller.datasite_watcher_cache.events_connection
    )
    assert ds_events_in_cache == 2


def test_load_peers():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        add_peers=False
    )

    ds_manager.add_peer("peer1@email.com")
    ds_manager.add_peer("peer2@email.com")

    do_manager.add_peer("peer3@email.com")

    # reset the peers and load them from connection
    do_manager.peers = []
    ds_manager.peers = []

    do_manager.load_peers()
    ds_manager.load_peers()

    assert len(ds_manager.peers) == 2
    assert len(do_manager.peers) == 1


def test_file_connections():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False
    )

    datasite_dir_do = (
        do_manager.proposed_file_change_handler.event_cache.file_connection.base_dir
    )

    syftbox_dir_ds = ds_manager.datasite_outbox_puller.datasite_watcher_cache.file_connection.base_dir

    assert datasite_dir_do != syftbox_dir_ds

    job_path = "email@email.com/test.job"
    job_path_in_datasite = job_path.split("/")[-1]

    ds_manager.send_file_change(job_path, "Hello, world!")

    assert (datasite_dir_do / job_path_in_datasite).exists()

    result_rel_path = "test_result.job"
    result_path = datasite_dir_do / result_rel_path
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with open(result_path, "w") as f:
        f.write("I am a result")

    do_manager.sync()

    ds_manager.sync()

    assert (syftbox_dir_ds / do_manager.email / result_rel_path).exists()


def test_datasets():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False
    )

    mock_dset_path, private_dset_path, readme_path = create_tmp_dataset_files()
    do_manager.create_dataset(
        name="my dataset",
        mock_path=mock_dset_path,
        private_path=private_dset_path,
        summary="This is a summary",
        readme_path=readme_path,
        tags=["tag1", "tag2"],
    )

    backing_store = (
        do_manager.proposed_file_change_handler.connection_router.connections[
            0
        ].backing_store
    )

    syftbox_events = backing_store.syftbox_events_message_log
    assert len(syftbox_events) == 1
    # for message in syftbox_events:
    #     for event in message.events:

    outbox_events_messages = backing_store.outboxes["all"]
    outbox_events = [
        event for message in outbox_events_messages for event in message.events
    ]
    assert not any("private" in str(event.path_in_datasite) for event in outbox_events)

    datasets = do_manager.datasets.get_all()
    assert len(datasets) == 1

    # Retrieve dataset by name
    dataset_do = do_manager.datasets["my dataset"]
    assert isinstance(dataset_do, Dataset)
    assert len(dataset_do.private_files) > 0
    assert len(dataset_do.mock_files) > 0

    ds_manager.sync()

    assert len(ds_manager.datasets.get_all()) == 1

    dataset_ds = ds_manager.datasets.get("my dataset", datasite=do_manager.email)

    assert dataset_ds.mock_files[0].exists()

    mock_content_ds = (dataset_ds.mock_dir / "mock.txt").read_text()
    assert len(mock_content_ds) > 0

    def has_file(root_dir, filename):
        return any(p.name == filename for p in Path(root_dir).rglob("*"))

    assert has_file(ds_manager.syftbox_folder, "mock.txt")
    assert not has_file(ds_manager.syftbox_folder, "private.txt")


def test_datasets_with_parquet():
    """Test dataset creation and sync with parquet files (binary format)."""
    import pandas as pd

    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False
    )

    mock_dset_path, private_dset_path, readme_path = (
        create_tmp_dataset_files_with_parquet()
    )

    # This should work without errors even though parquet files are binary
    do_manager.create_dataset(
        name="parquet dataset",
        mock_path=mock_dset_path,
        private_path=private_dset_path,
        summary="This is a dataset with parquet files",
        readme_path=readme_path,
        tags=["parquet", "binary"],
    )

    backing_store = (
        do_manager.proposed_file_change_handler.connection_router.connections[
            0
        ].backing_store
    )

    syftbox_events = backing_store.syftbox_events_message_log
    assert len(syftbox_events) == 1

    outbox_events_messages = backing_store.outboxes["all"]
    outbox_events = [
        event for message in outbox_events_messages for event in message.events
    ]
    assert not any("private" in str(event.path_in_datasite) for event in outbox_events)

    datasets = do_manager.datasets.get_all()
    assert len(datasets) == 1

    # Retrieve dataset by name
    dataset_do = do_manager.datasets["parquet dataset"]
    assert isinstance(dataset_do, Dataset)
    assert len(dataset_do.private_files) > 0
    assert len(dataset_do.mock_files) > 0

    # Verify parquet files are present
    mock_files = [f.name for f in dataset_do.mock_files]
    assert "mock_data.parquet" in mock_files

    private_files = [f.name for f in dataset_do.private_files]
    assert "private_data.parquet" in private_files

    # Sync to datasite
    ds_manager.sync()

    assert len(ds_manager.datasets.get_all()) == 1

    dataset_ds = ds_manager.datasets.get("parquet dataset", datasite=do_manager.email)

    # Verify the parquet file exists and can be read
    mock_parquet_path = dataset_ds.mock_dir / "mock_data.parquet"
    assert mock_parquet_path.exists()

    # Verify we can read the parquet file back
    df = pd.read_parquet(mock_parquet_path)
    assert len(df) == 5
    assert "name" in df.columns
    assert "age" in df.columns

    def has_file(root_dir, filename):
        return any(p.name == filename for p in Path(root_dir).rglob("*"))

    assert has_file(ds_manager.syftbox_folder, "mock_data.parquet")
    assert not has_file(ds_manager.syftbox_folder, "private_data.parquet")


def test_jobs():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False,
        sync_automatically=False,
    )

    test_py_path = "/tmp/test.py"
    with open(test_py_path, "w") as f:
        f.write("""
import os
os.makedirs("outputs", exist_ok=True)
with open("outputs/result.json", "w") as f:
    f.write('{"result": 1}')
""")

    ds_manager.submit_python_job(
        user=do_manager.email,
        code_path=test_py_path,
        job_name="test.job",
    )

    backing_store = (
        do_manager.proposed_file_change_handler.connection_router.connections[
            0
        ].backing_store
    )

    # We want to make sure that we only send one message for the multiple files in the job.
    # this is to reduce the number of messages sent, which increases the speed of sync
    # we do this by not always syncing on a file change, currently this logic is a bit of
    # a short cut, but we could do this based on timing eventually (if there are items in the
    # queue for longer than a certain time we start pushing)
    assert len(backing_store.proposed_events_inbox) == 1

    do_manager.sync()

    assert len(do_manager.job_client.jobs) == 1
    job = do_manager.job_client.jobs[0]

    job.approve()

    do_manager.job_runner.process_approved_jobs()

    do_manager.sync()

    ds_manager.sync()

    output_path = ds_manager.job_client.jobs[-1].output_paths[0]
    with open(output_path, "r") as f:
        json_content = json.loads(f.read())

    assert json_content["result"] == 1


def test_job_flow_with_dataset():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False
    )

    mock_dset_path, private_dset_path, readme_path = create_tmp_dataset_files()
    do_manager.create_dataset(
        name="my dataset",
        mock_path=mock_dset_path,
        private_path=private_dset_path,
        summary="This is a summary",
        readme_path=readme_path,
        tags=["tag1", "tag2"],
    )

    datasets = do_manager.datasets.get_all()
    assert len(datasets) == 1

    ds_manager.sync()

    assert len(ds_manager.datasets.get_all()) == 1

    test_py_path = "/tmp/test.py"
    with open(test_py_path, "w") as f:
        f.write("""
import os, json
import numpy as np

# Test that we can use numpy in the job environment
arr = np.array([1, 2, 3, 4, 5])
result = {"result": int(arr.sum())}

os.makedirs("outputs", exist_ok=True)
with open("outputs/result.json", "w") as f:
    f.write(json.dumps(result))
""")

    ds_manager.submit_python_job(
        user=do_manager.email,
        code_path=test_py_path,
        job_name="test.job",
        dependencies=["numpy"],
    )

    assert len(do_manager.job_client.jobs) == 1
    job = do_manager.job_client.jobs[0]

    job.approve()

    do_manager.job_runner.process_approved_jobs()

    do_manager.sync()

    ds_manager.sync()

    output_path = ds_manager.job_client.jobs[-1].output_paths[0]
    with open(output_path, "r") as f:
        json_content = json.loads(f.read())

    assert json_content["result"] == 15  # sum of [1, 2, 3, 4, 5]


def test_file_deletion_do_to_ds():
    """Test that DO can delete a file and it syncs to DS"""
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False
    )

    datasite_dir_do = do_manager.syftbox_folder
    syftbox_dir_ds = ds_manager.syftbox_folder

    # DO creates a file
    result_rel_path = "test_file.txt"
    result_path = datasite_dir_do / do_manager.email / result_rel_path
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with open(result_path, "w") as f:
        f.write("This is a test file")

    # DO syncs (sends file to DS)
    do_manager.sync()

    # DS syncs (receives file from DO)
    ds_manager.sync()

    # Verify file exists on DS side
    ds_file_path = syftbox_dir_ds / do_manager.email / result_rel_path
    assert ds_file_path.exists(), "File should exist on DS side after sync"

    # DO deletes the file
    result_path.unlink()
    assert not result_path.exists(), "File should be deleted on DO side"

    # DO syncs (propagates deletion)
    do_manager.sync()

    # DS syncs (receives deletion)
    ds_manager.sync()

    # Verify file is deleted on DS side
    assert not ds_file_path.exists(), (
        "File should be deleted on DS side after DO deletes and both sync"
    )

    # Verify hash is removed from caches
    do_cache = do_manager.proposed_file_change_handler.event_cache
    assert result_rel_path not in do_cache.file_hashes, (
        "Hash should be removed from DO cache"
    )

    ds_cache = ds_manager.datasite_outbox_puller.datasite_watcher_cache
    expected_path = Path(do_manager.email) / result_rel_path
    assert expected_path not in ds_cache.file_hashes, (
        "Hash should be removed from DS cache"
    )


def test_in_memory_deletion():
    """Test deletion works with in-memory cache"""
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=True
    )

    # Create file via send_file_change
    job_path = "email@email.com/test.job"
    job_path_in_datasite = job_path.split("/")[-1]

    ds_manager.send_file_change(job_path, "Hello, world!")

    # Verify file exists in DO cache
    do_cache = do_manager.proposed_file_change_handler.event_cache
    assert job_path_in_datasite in [
        str(p) for p, _ in do_cache.file_connection.get_items()
    ]

    # Simulate deletion by removing from DO cache
    do_cache.file_connection.delete_file(job_path_in_datasite)

    # Process deletion
    do_manager.sync()
    ds_manager.sync()

    # Verify deletion propagated
    ds_cache = ds_manager.datasite_outbox_puller.datasite_watcher_cache
    ds_path = Path(do_manager.email) / job_path_in_datasite
    assert str(ds_path) not in [str(p) for p, _ in ds_cache.file_connection.get_items()]


def test_folder_job_submission():
    """Test folder job submission with pyproject.toml and multiple files (uses uv sync)."""
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False,
        sync_automatically=False,
    )

    # Create a test project folder with pyproject.toml and multiple Python files
    project_dir = Path(tempfile.mkdtemp()) / "test-project"
    project_dir.mkdir()

    # Write pyproject.toml with a dependency
    (project_dir / "pyproject.toml").write_text(
        """[project]
name = "test-project"
version = "0.1.0"
dependencies = ["cowsay"]
"""
    )

    # Write helper module that uses the dependency
    (project_dir / "helper.py").write_text(
        """import cowsay

def get_message():
    # Verify cowsay is installed by using it
    return f"folder_job_success_with_{cowsay.__name__}"
"""
    )

    # Write main.py that imports from helper
    (project_dir / "main.py").write_text(
        """import os
from helper import get_message

os.makedirs("outputs", exist_ok=True)
with open("outputs/result.json", "w") as f:
    f.write(f'{{"result": "{get_message()}"}}')
"""
    )

    # Submit folder job
    ds_manager.submit_python_job(
        user=do_manager.email,
        code_path=str(project_dir),
        job_name="folder-test-job",
    )

    do_manager.sync()

    # Verify job received
    assert len(do_manager.job_client.jobs) == 1
    job = do_manager.job_client.jobs[0]

    # Verify tarball exists
    tarball_path = job.location / "test-project.tar.gz"
    assert tarball_path.exists()

    # Verify tarball contains expected files (including helper module)
    with tarfile.open(tarball_path, "r:gz") as tar:
        names = tar.getnames()
        assert "test-project/main.py" in names
        assert "test-project/helper.py" in names
        assert "test-project/pyproject.toml" in names

    # Verify run.sh creates outputs symlink and uses uv sync (for pyproject.toml projects)
    run_sh = (job.location / "run.sh").read_text()
    assert "ln -s ../outputs outputs" in run_sh
    assert "uv sync" in run_sh
    assert "uv run python main.py" in run_sh

    # Verify config.yaml has correct fields
    with open(job.location / "config.yaml") as f:
        config = yaml.safe_load(f)
    assert config["type"] == "python"
    assert config["has_pyproject"] is True
    assert config["entry_point"] == "main.py"

    # Approve and execute
    job.approve()
    do_manager.job_runner.process_approved_jobs()

    do_manager.sync()
    ds_manager.sync()

    # Verify output (includes cowsay module name proving dependency was installed)
    output_path = ds_manager.job_client.jobs[-1].output_paths[0]
    with open(output_path, "r") as f:
        result = json.loads(f.read())
    assert result["result"] == "folder_job_success_with_cowsay"


def test_folder_job_submission_no_pyproject():
    """Test folder job submission without pyproject.toml (uses uv pip install)."""
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False,
        sync_automatically=False,
    )

    # Create a test project folder WITHOUT pyproject.toml but with multiple files
    project_dir = Path(tempfile.mkdtemp()) / "simple-project"
    project_dir.mkdir()

    # Write utils module that uses numpy
    (project_dir / "utils.py").write_text(
        """import numpy as np

def compute_value():
    return int(np.array([1, 2, 3, 4, 5]).sum())
"""
    )

    # Write main.py that imports from utils
    (project_dir / "main.py").write_text(
        """import os
from utils import compute_value

os.makedirs("outputs", exist_ok=True)
with open("outputs/result.json", "w") as f:
    f.write(f'{{"result": "no_pyproject_success", "value": {compute_value()}}}')
"""
    )

    # Submit folder job with numpy as dependency
    ds_manager.submit_python_job(
        user=do_manager.email,
        code_path=str(project_dir),
        job_name="simple-folder-job",
        dependencies=["numpy"],
    )

    do_manager.sync()

    # Verify job received
    assert len(do_manager.job_client.jobs) == 1
    job = do_manager.job_client.jobs[0]

    # Verify tarball exists
    tarball_path = job.location / "simple-project.tar.gz"
    assert tarball_path.exists()

    # Verify tarball contains expected files (main.py and utils.py)
    with tarfile.open(tarball_path, "r:gz") as tar:
        names = tar.getnames()
        assert "simple-project/main.py" in names
        assert "simple-project/utils.py" in names

    # Verify run.sh creates outputs symlink, cds into folder, and uses uv pip install
    run_sh = (job.location / "run.sh").read_text()
    assert "ln -s ../outputs outputs" in run_sh
    assert "cd simple-project" in run_sh
    assert "uv venv" in run_sh
    assert "uv pip install" in run_sh
    assert "numpy" in run_sh  # User-specified dependency

    # Verify config.yaml has correct fields
    with open(job.location / "config.yaml") as f:
        config = yaml.safe_load(f)
    assert config["type"] == "python"
    assert config["has_pyproject"] is False

    # Approve and execute
    job.approve()
    do_manager.job_runner.process_approved_jobs()

    do_manager.sync()
    ds_manager.sync()

    # Verify output (includes value from utils.py proving numpy import worked)
    output_path = ds_manager.job_client.jobs[-1].output_paths[0]
    with open(output_path, "r") as f:
        result = json.loads(f.read())
    assert result["result"] == "no_pyproject_success"
    assert result["value"] == 15  # sum of [1, 2, 3, 4, 5]
