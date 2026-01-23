from pathlib import Path
import json
from syft_client.sync.messages.proposed_filechange import ProposedFileChangesMessage
from syft_client.sync.syftbox_manager import SyftboxManager
from syft_client.sync.connections.inmemory_connection import InMemoryBackingPlatform
from syft_client.sync.messages.proposed_filechange import ProposedFileChange
from syft_datasets.dataset import Dataset
import pytest
from tests.unit.utils import (
    create_tmp_dataset_files,
    create_tmp_dataset_files_with_parquet,
    create_test_project_folder,
)
import tempfile
import shutil


from syft_client.sync.sync.caches.datasite_owner_cache import (
    ProposedEventFileOutdatedException,
)
from tests.unit.utils import get_mock_events_messages
from tests.unit.utils import get_mock_proposed_events_messages
from tests.unit.utils import setup_mock_peer_version


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

    events_in_backing_platform = do_manager.get_all_accepted_events_do()
    assert len(events_in_backing_platform) == 0

    ds_manager.send_file_change(file_path, "Hello, world!")

    # second event is present
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
    do_manager.datasite_owner_syncer.handle_proposed_filechange_events_message(
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
    do_manager.datasite_owner_syncer.handle_proposed_filechange_events_message(
        ds_email, message_2
    )

    content = (
        do_manager.datasite_owner_syncer.event_cache.file_connection.read_file(
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
        do_manager.datasite_owner_syncer.handle_proposed_filechange_events_message(
            ds_email, message_3_outdated
        )

    content = (
        do_manager.datasite_owner_syncer.event_cache.file_connection.read_file(
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
            ds_manager.datasite_watcher_syncer.datasite_watcher_cache.get_cached_events()
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
    outbox_folder = store.get_or_create_outbox_folder(
        owner_email=do_manager.email, recipient_email=ds_manager.email
    )
    outbox_folder.messages.extend(events_messages)

    # sync down existing state
    do_manager.sync()

    n_messages_in_cache = len(
        do_manager.datasite_owner_syncer.event_cache.events_messages_connection
    )
    n_files_in_cache = len(
        do_manager.datasite_owner_syncer.event_cache.file_connection
    )
    hashes_in_cache = len(
        do_manager.datasite_owner_syncer.event_cache.file_hashes
    )
    assert n_messages_in_cache == 2
    assert n_files_in_cache == 2
    assert hashes_in_cache == 2
    # outbox should still be 2
    outbox_folder = store.get_outbox_folder(
        owner_email=do_manager.email, recipient_email=ds_manager.email
    )
    assert len(outbox_folder.messages) == 2


def test_sync_existing_inbox_state_do():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()
    store: InMemoryBackingPlatform = do_manager.connection_router.connections[
        0
    ].backing_store

    proposed_events_messages = get_mock_proposed_events_messages(2)
    store.proposed_events_inbox.extend(proposed_events_messages)

    # add the peers for the messages, otherwise it wont sync them
    for message in proposed_events_messages:
        store.peer_states[do_manager.email] = {message.sender_email: "accepted"}
        # Set up version file for the mock peer so DO can read it
        setup_mock_peer_version(store, message.sender_email, do_manager.email)
        # Load the peer version into the version manager's cache
        do_manager.version_manager.load_peer_version(message.sender_email)
    do_manager.load_peers()

    do_manager.sync()

    n_events_message_in_cache = len(
        do_manager.datasite_owner_syncer.event_cache.events_messages_connection
    )
    n_files_in_cache = len(
        do_manager.datasite_owner_syncer.event_cache.file_connection
    )
    hashes_in_cache = len(
        do_manager.datasite_owner_syncer.event_cache.file_hashes
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

    # Messages are written to outbox for the sender (email@email.com)
    outbox_folder = store.get_outbox_folder(
        owner_email=do_manager.email, recipient_email="email@email.com"
    )
    assert len(outbox_folder.messages) == 2


def test_sync_existing_datasite_state_ds():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()

    store: InMemoryBackingPlatform = ds_manager.connection_router.connections[
        0
    ].backing_store

    events_messages = get_mock_events_messages(2)
    store.syftbox_events_message_log.extend(events_messages)
    outbox_folder = store.get_or_create_outbox_folder(
        owner_email=do_manager.email, recipient_email=ds_manager.email
    )
    outbox_folder.messages.extend(events_messages)

    ds_manager.sync()

    ds_events_in_cache = len(
        ds_manager.datasite_watcher_syncer.datasite_watcher_cache.events_connection
    )
    assert ds_events_in_cache == 2


def test_load_peers():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        add_peers=False
    )

    ds_manager.add_peer("peer1@email.com")
    ds_manager.add_peer(do_manager.email)

    do_manager.load_peers()

    do_manager.approve_peer_request(ds_manager.email)

    # reset the peers and load them from connection
    do_manager._approved_peers = []
    do_manager._peer_requests = []
    do_manager._outstanding_peer_requests = []
    ds_manager._approved_peers = []
    ds_manager._peer_requests = []
    ds_manager._outstanding_peer_requests = []

    do_manager.load_peers()
    ds_manager.load_peers()

    assert len(ds_manager.peers) == 2
    assert len(do_manager.peers) == 1


def test_file_connections():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False
    )

    datasite_dir_do = (
        do_manager.datasite_owner_syncer.event_cache.file_connection.base_dir
    )

    syftbox_dir_ds = ds_manager.datasite_watcher_syncer.datasite_watcher_cache.file_connection.base_dir

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

    # Create dataset with specific users
    do_manager.create_dataset(
        name="my dataset",
        mock_path=mock_dset_path,
        private_path=private_dset_path,
        summary="This is a summary",
        readme_path=readme_path,
        tags=["tag1", "tag2"],
        users=[ds_manager.email],  # Share with specific user
    )

    # Verify collection created
    collections = do_manager.connection_router.list_dataset_collections_as_do()
    assert "my dataset" in collections

    backing_store = (
        do_manager.datasite_owner_syncer.connection_router.connections[
            0
        ].backing_store
    )

    # Dataset files are excluded from outbox sync (they use their own dedicated channel)
    syftbox_events = backing_store.syftbox_events_message_log
    assert len(syftbox_events) == 0

    datasets = do_manager.datasets.get_all()
    assert len(datasets) == 1

    # Retrieve dataset by name
    dataset_do = do_manager.datasets["my dataset"]
    assert isinstance(dataset_do, Dataset)
    assert len(dataset_do.private_files) > 0
    assert len(dataset_do.mock_files) > 0

    ds_manager.sync()

    # Verify DS can see collection
    ds_collections = ds_manager.connection_router.list_dataset_collections_as_ds()
    assert any(c["tag"] == "my dataset" for c in ds_collections)

    assert len(ds_manager.datasets.get_all()) == 1

    dataset_ds = ds_manager.datasets.get("my dataset", datasite=do_manager.email)

    assert dataset_ds.mock_files[0].exists()

    mock_content_ds = (dataset_ds.mock_dir / "mock.txt").read_text()
    assert len(mock_content_ds) > 0

    # test getting it via resolve path
    from syft_client import resolve_dataset_file_path

    mock_file_path = resolve_dataset_file_path("my dataset", client=ds_manager)
    assert mock_file_path.exists()

    mock_content_ds = mock_file_path.read_text()
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
        users=[ds_manager.email],
    )

    backing_store = (
        do_manager.datasite_owner_syncer.connection_router.connections[
            0
        ].backing_store
    )

    # Dataset files are excluded from outbox sync (they use their own dedicated channel)
    syftbox_events = backing_store.syftbox_events_message_log
    assert len(syftbox_events) == 0

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


def test_dataset_empty_permissions_no_access():
    """Test that empty permissions list means no one can access the dataset collection."""
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False
    )

    mock_dset_path, private_dset_path, readme_path = create_tmp_dataset_files()

    # Create dataset with empty permissions list (share with no one)
    do_manager.create_dataset(
        name="private dataset",
        mock_path=mock_dset_path,
        private_path=private_dset_path,
        summary="This is a private summary",
        readme_path=readme_path,
        tags=["private"],
        users=[],  # Empty list - no one has access
    )

    # Verify collection created
    collections = do_manager.connection_router.list_dataset_collections_as_do()
    assert "private dataset" in collections

    # DO should be able to see their own dataset
    datasets = do_manager.datasets.get_all()
    assert len(datasets) == 1

    # DS syncs
    ds_manager.sync()

    # DS should NOT see the collection (no permissions)
    ds_collections = ds_manager.connection_router.list_dataset_collections_as_ds()
    assert not any(c["tag"] == "private dataset" for c in ds_collections)

    # Get the hash from DO's backing store and try to download anyway
    do_backing_store = do_manager.connection_router.connections[0].backing_store
    collection = [
        c for c in do_backing_store.dataset_collections if c.tag == "private dataset"
    ][0]
    content_hash = collection.content_hash

    # DS should NOT be able to download the dataset collection (no permissions)
    try:
        ds_manager.connection_router.download_dataset_collection(
            "private dataset", content_hash, do_manager.email
        )
        assert False, "Should have raised PermissionError"
    except PermissionError:
        pass  # Expected


def test_dataset_only_mock_data_uploaded():
    """Test that only mock data is uploaded to the collection, not private data."""
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False
    )

    mock_dset_path, private_dset_path, readme_path = create_tmp_dataset_files()

    do_manager.create_dataset(
        name="test dataset",
        mock_path=mock_dset_path,
        private_path=private_dset_path,
        summary="Test summary",
        readme_path=readme_path,
        tags=["test"],
        users=[ds_manager.email],
    )

    # Get the backing store
    backing_store = (
        do_manager.datasite_owner_syncer.connection_router.connections[
            0
        ].backing_store
    )

    # Find the dataset collection
    collection = None
    for c in backing_store.dataset_collections:
        if c.tag == "test dataset" and c.owner_email == do_manager.email:
            collection = c
            break

    assert collection is not None, "Dataset collection not found"

    # Check files in the collection
    file_names = list(collection.files.keys())

    # Should have mock.txt and dataset.yaml, but NOT private.txt
    assert "mock.txt" in file_names, "mock.txt should be in collection"
    assert "dataset.yaml" in file_names, "dataset.yaml should be in collection"
    assert "readme.md" in file_names, "readme.md should be in collection"
    assert "private.txt" not in file_names, "private.txt should NOT be in collection"

    # Verify the actual content of mock.txt is there
    mock_content = collection.files["mock.txt"]
    assert len(mock_content) > 0, "Mock file should have content"
    assert b"Hello" in mock_content, "Mock file should contain expected data"


def test_jobs():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False,
        sync_automatically=False,
    )

    test_py_path = "/tmp/test.py"
    with open(test_py_path, "w") as f:
        f.write("""
import os
os.mkdir("outputs")
with open("outputs/result.json", "w") as f:
    f.write('{"result": 1}')
""")

    ds_manager.submit_python_job(
        user=do_manager.email,
        code_path=test_py_path,
        job_name="test.job",
    )

    backing_store = (
        do_manager.datasite_owner_syncer.connection_router.connections[
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


def test_jobs_with_dataset():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False,
        sync_automatically=False,
    )

    mock_dset_path, private_dset_path, readme_path = create_tmp_dataset_files()

    do_manager.create_dataset(
        name="my dataset",
        mock_path=mock_dset_path,
        private_path=private_dset_path,
        summary="This is a summary",
        readme_path=readme_path,
        tags=["tag1", "tag2"],
        users=[ds_manager.email],
    )
    do_manager.sync()

    ds_manager.sync()
    assert len(ds_manager.datasets.get_all()) == 1

    dataset_ds = ds_manager.datasets.get("my dataset", datasite=do_manager.email)
    assert dataset_ds.mock_files[0].exists()
    import syft_client as sc

    assert (
        sc.resolve_dataset_file_path("my dataset", client=ds_manager)
        == dataset_ds.mock_files[0]
    )

    test_py_path = "/tmp/test.py"
    with open(test_py_path, "w") as f:
        f.write("""
import syft_client as sc
import os
import json

data_path = sc.resolve_dataset_file_path("my dataset")
with open(data_path, "r") as f:
    data = f.read()
result = {"result": len(data)}
os.mkdir("outputs")
with open("outputs/result.json", "w") as f:
    f.write(json.dumps(result))
""")

    ds_manager.submit_python_job(
        user=do_manager.email,
        code_path=test_py_path,
        job_name="test.job",
    )

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

    with open(private_dset_path, "r") as f:
        private_data_length = len(f.read())

    assert json_content["result"] == private_data_length


def test_single_file_job_submission_without_pyproject():
    """Test that code files are copied directly to job_dir (not job_dir/code/).

    Verifies backwards compatibility fix - code should be at:
        job_dir/main.py  (not job_dir/code/main.py)
    """
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False,
        sync_automatically=False,
    )

    # Test with single file submission
    test_py_path = "/tmp/test_direct_copy.py"
    with open(test_py_path, "w") as f:
        f.write('print("hello")')

    ds_manager.submit_python_job(
        user=do_manager.email,
        code_path=test_py_path,
        job_name="test.direct.copy",
    )

    do_manager.sync()

    assert len(do_manager.job_client.jobs) == 1
    job = do_manager.job_client.jobs[0]
    job_dir = job.location

    # Verify code is directly in job_dir, not in job_dir/code/
    assert (job_dir / "test_direct_copy.py").exists(), (
        "Code should be directly in job_dir"
    )
    assert (job_dir / "run.sh").exists(), "run.sh should exist"
    assert (job_dir / "config.yaml").exists(), "config.yaml should exist"


def test_folder_job_submission_without_pyproject():
    """Test folder submission without pyproject.toml uses uv venv + uv pip install.

    Verifies:
        - Folder without pyproject.toml works
        - Folder is preserved with its name (not dumped at root)
        - Generated run.sh uses 'uv venv' (not 'uv sync')
        - Entrypoint path includes folder name
    """
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False,
        sync_automatically=False,
    )

    # Create a folder without pyproject.toml
    project_dir = tempfile.mkdtemp(prefix="test_no_pyproject_")
    folder_name = Path(project_dir).name

    try:
        # Create main.py
        main_path = Path(project_dir) / "main.py"
        with open(main_path, "w") as f:
            f.write("""
import os
os.mkdir("outputs")
with open("outputs/result.txt", "w") as f:
    f.write("success")
""")

        # Create a helper module
        helper_path = Path(project_dir) / "helper.py"
        with open(helper_path, "w") as f:
            f.write("VALUE = 42\n")

        # Submit folder (no pyproject.toml)
        ds_manager.submit_python_job(
            user=do_manager.email,
            code_path=project_dir,
            job_name="test.no.pyproject",
            entrypoint="main.py",
        )

        do_manager.sync()

        assert len(do_manager.job_client.jobs) == 1
        job = do_manager.job_client.jobs[0]
        job_dir = job.location

        # Verify folder structure - folder preserved with its name
        assert (job_dir / folder_name).exists(), (
            f"Folder {folder_name} should exist in job_dir"
        )
        assert (job_dir / folder_name / "main.py").exists(), (
            "main.py should be inside folder"
        )
        assert (job_dir / folder_name / "helper.py").exists(), (
            "helper.py should be inside folder"
        )
        assert (job_dir / "run.sh").exists(), "run.sh should be at job_dir root"
        assert (job_dir / "config.yaml").exists(), (
            "config.yaml should be at job_dir root"
        )

        # Verify run.sh uses uv venv (not uv sync) and correct entrypoint path
        run_script = (job_dir / "run.sh").read_text()
        assert "uv venv" in run_script, (
            "Should use 'uv venv' for folders without pyproject.toml"
        )
        assert "uv sync" not in run_script, (
            "Should NOT use 'uv sync' without pyproject.toml"
        )
        assert f"python {folder_name}/main.py" in run_script, (
            "Should run folder_name/main.py"
        )

    finally:
        shutil.rmtree(project_dir, ignore_errors=True)


def test_folder_job_submission_with_pyproject():
    """Test folder submission with pyproject.toml uses uv sync.

    Verifies:
        - Folder is preserved with its name inside job_dir
        - pyproject.toml is inside the folder, not at job_dir root
        - run.sh uses 'uv sync' inside the folder
        - Entrypoint path includes folder name
    """
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False,
        sync_automatically=False,
    )

    # Create a folder with pyproject.toml
    project_dir = tempfile.mkdtemp(prefix="test_with_pyproject_")
    folder_name = Path(project_dir).name

    try:
        # Create pyproject.toml
        pyproject_path = Path(project_dir) / "pyproject.toml"
        with open(pyproject_path, "w") as f:
            f.write("""
[project]
name = "test-project"
version = "0.1.0"
dependencies = []
""")

        # Create main.py
        main_path = Path(project_dir) / "main.py"
        with open(main_path, "w") as f:
            f.write('print("hello from pyproject project")')

        # Submit folder (with pyproject.toml)
        ds_manager.submit_python_job(
            user=do_manager.email,
            code_path=project_dir,
            job_name="test.with.pyproject",
            entrypoint="main.py",
        )

        do_manager.sync()

        assert len(do_manager.job_client.jobs) == 1
        job = do_manager.job_client.jobs[0]
        job_dir = job.location

        # Verify folder structure - folder preserved with its name
        assert (job_dir / folder_name).exists(), (
            f"Folder {folder_name} should exist in job_dir"
        )
        assert (job_dir / folder_name / "main.py").exists(), (
            "main.py should be inside folder"
        )
        assert (job_dir / folder_name / "pyproject.toml").exists(), (
            "pyproject.toml should be inside folder"
        )
        assert (job_dir / "run.sh").exists(), "run.sh should be at job_dir root"
        assert (job_dir / "config.yaml").exists(), (
            "config.yaml should be at job_dir root"
        )

        # Verify run.sh uses uv sync inside folder and correct entrypoint path
        run_script = (job_dir / "run.sh").read_text()
        assert "uv sync" in run_script, (
            "Should use 'uv sync' for folders with pyproject.toml"
        )
        assert f"cd {folder_name}" in run_script, "Should cd into folder for uv sync"
        assert f"python {folder_name}/main.py" in run_script, (
            "Should run folder_name/main.py"
        )

    finally:
        shutil.rmtree(project_dir, ignore_errors=True)


def test_folder_job_auto_detect_main_py():
    """Test that entrypoint is auto-detected when main.py exists."""
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False,
        sync_automatically=False,
    )

    project_dir = tempfile.mkdtemp(prefix="test_auto_main_")
    folder_name = Path(project_dir).name

    try:
        # Create main.py and another file
        (Path(project_dir) / "main.py").write_text('print("main")')
        (Path(project_dir) / "utils.py").write_text('print("utils")')

        # Submit without entrypoint - should auto-detect main.py
        ds_manager.submit_python_job(
            user=do_manager.email,
            code_path=project_dir,
            job_name="test.auto.main",
            # No entrypoint specified
        )

        do_manager.sync()
        job = do_manager.job_client.jobs[0]
        job_dir = job.location

        # Verify main.py was auto-detected
        run_script = (job_dir / "run.sh").read_text()
        assert f"python {folder_name}/main.py" in run_script, (
            "Should auto-detect main.py as entrypoint"
        )

    finally:
        shutil.rmtree(project_dir, ignore_errors=True)


def test_folder_job_auto_detect_single_py():
    """Test that entrypoint is auto-detected when only one .py file exists."""
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False,
        sync_automatically=False,
    )

    project_dir = tempfile.mkdtemp(prefix="test_auto_single_")
    folder_name = Path(project_dir).name

    try:
        # Create only one .py file (not named main.py)
        (Path(project_dir) / "script.py").write_text('print("script")')
        (Path(project_dir) / "README.md").write_text("# Readme")

        # Submit without entrypoint - should auto-detect script.py
        ds_manager.submit_python_job(
            user=do_manager.email,
            code_path=project_dir,
            job_name="test.auto.single",
        )

        do_manager.sync()
        job = do_manager.job_client.jobs[0]
        job_dir = job.location

        # Verify script.py was auto-detected
        run_script = (job_dir / "run.sh").read_text()
        assert f"python {folder_name}/script.py" in run_script, (
            "Should auto-detect single .py file as entrypoint"
        )

    finally:
        shutil.rmtree(project_dir, ignore_errors=True)


def test_folder_job_no_auto_detect_multiple_py():
    """Test that auto-detection fails when multiple .py files and no main.py."""
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False,
        sync_automatically=False,
    )

    project_dir = tempfile.mkdtemp(prefix="test_no_auto_")

    try:
        # Create multiple .py files (no main.py)
        (Path(project_dir) / "script1.py").write_text('print("1")')
        (Path(project_dir) / "script2.py").write_text('print("2")')

        # Submit without entrypoint - should fail
        with pytest.raises(ValueError, match="Could not auto-detect entrypoint"):
            ds_manager.submit_python_job(
                user=do_manager.email,
                code_path=project_dir,
                job_name="test.no.auto",
            )

    finally:
        shutil.rmtree(project_dir, ignore_errors=True)


def test_single_file_job_flow_with_dataset():
    """Test complete job submission flow with dataset access.

    This test verifies the end-to-end flow of:
    1. Data Owner (DO) creates a dataset with mock and private data
    2. Data Scientist (DS) syncs and sees the dataset
    3. DS submits a Python job that accesses the private dataset
    4. DO approves and runs the job
    5. Job reads private data using syft:// protocol
    6. Results sync back to DS

    Test flow:
        DO: create_dataset("my dataset") with private.txt containing "Hello, world!"
                ↓
        DS: sync() → sees dataset
                ↓
        DS: submit_python_job() with code that reads syft://private/...
                ↓
        DO: sync() → receives job
                ↓
        DO: job.approve() + process_approved_jobs()
                ↓
        Job executes: reads private data → writes outputs/result.json
                ↓
        DO: sync() → sends results
                ↓
        DS: sync() → receives results
                ↓
        Assert: result.json contains {"result": "Hello, world!"}

    Verifies:
        - Dataset creation and sync between DO and DS
        - Job submission with syft:// path resolution
        - Job approval and execution workflow
        - Output file sync back to DS
    """
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
        users=[ds_manager.email],  # Share with DS so they can access the dataset
    )

    datasets = do_manager.datasets.get_all()
    assert len(datasets) == 1

    ds_manager.sync()

    assert len(ds_manager.datasets.get_all()) == 1

    test_py_path = "/tmp/test.py"
    with open(test_py_path, "w") as f:
        f.write("""
import os, json
import syft_client as sc

data_path = "syft://private/syft_datasets/my dataset/private.txt"
resolved_path = sc.resolve_path(data_path)

with open(resolved_path, "r") as data_file:
    data = data_file.read()

result = {"result": data}

os.mkdir("outputs")
with open("outputs/result.json", "w") as f:
    f.write(json.dumps(result))
""")

    ds_manager.submit_python_job(
        user=do_manager.email,
        code_path=test_py_path,
        job_name="test.job",
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

    assert json_content["result"] == "Hello, world private!"


def test_folder_job_flow_with_dataset():
    """Test job submission with a folder containing multiple Python files.

    Tests folder structure:
        project_dir/
        ├── main.py              # entrypoint, imports from helpers.helper
        └── helpers/
            ├── __init__.py      # package marker
            └── helper.py        # helper functions

    Verifies:
        - Folder submission with entrypoint parameter works
        - Nested package imports work (from helpers.helper import ...)
        - Outputs created at job root (not inside code/)
        - End-to-end flow: submit → approve → run → sync → verify output
    """
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
        users=[ds_manager.email],  # Share with DS so they can access the dataset
    )

    ds_manager.sync()
    assert len(ds_manager.datasets.get_all()) == 1

    # Create test project folder (no pyproject.toml, multiplier=2)
    project_dir = create_test_project_folder(with_pyproject=False, multiplier=2)

    try:
        ds_manager.submit_python_job(
            user=do_manager.email,
            code_path=str(project_dir),
            job_name="test.folder.job",
            entrypoint="main.py",
        )

        assert len(do_manager.job_client.jobs) == 1
        job = do_manager.job_client.jobs[0]

        job.approve()
        do_manager.job_runner.process_approved_jobs()

        do_manager.sync()
        ds_manager.sync()

        # Verify the job completed and produced output
        output_path = ds_manager.job_client.jobs[-1].output_paths[0]
        with open(output_path, "r") as f:
            json_content = json.loads(f.read())

        # Verify the helper module was imported and used correctly
        assert json_content["original"] == "Hello, world private!"
        assert json_content["processed"] == "Processed: Hello, world private!"
        assert json_content["multiplier"] == 2

    finally:
        shutil.rmtree(project_dir, ignore_errors=True)


def test_pyproject_folder_job_flow_with_dataset():
    """Test job submission with a folder containing pyproject.toml.

    Tests folder structure:
        project_dir/
        ├── pyproject.toml       # project config with dependencies
        ├── main.py              # entrypoint, imports from helpers.helper
        └── helpers/
            ├── __init__.py      # package marker
            └── helper.py        # helper functions

    Verifies:
        - Folder with pyproject.toml uses 'uv sync' (not 'uv venv')
        - Folder is preserved with its name in job_dir
        - .venv is created inside the code folder by uv sync
        - Nested package imports work
        - End-to-end flow: submit → approve → run → sync → verify output
    """
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
        users=[ds_manager.email],  # Share with DS so they can access the dataset
    )

    ds_manager.sync()
    assert len(ds_manager.datasets.get_all()) == 1

    # Create test project folder with pyproject.toml, multiplier=3
    project_dir = create_test_project_folder(
        with_pyproject=True, multiplier=3, prefix="test_pyproject_"
    )
    folder_name = project_dir.name

    try:
        ds_manager.submit_python_job(
            user=do_manager.email,
            code_path=str(project_dir),
            job_name="test.pyproject.job",
            entrypoint="main.py",
        )

        assert len(do_manager.job_client.jobs) == 1
        job = do_manager.job_client.jobs[0]
        job_dir = job.location

        # Verify folder structure before running
        assert (job_dir / folder_name).exists(), (
            f"Folder {folder_name} should exist in job_dir"
        )
        assert (job_dir / folder_name / "pyproject.toml").exists(), (
            "pyproject.toml should be inside folder"
        )
        assert (job_dir / folder_name / "main.py").exists(), (
            "main.py should be inside folder"
        )
        assert (job_dir / "run.sh").exists(), "run.sh should be at job_dir root"

        # Verify run.sh uses uv sync (pyproject.toml case)
        run_script = (job_dir / "run.sh").read_text()
        assert "uv sync" in run_script, (
            "Should use 'uv sync' for folders with pyproject.toml"
        )
        assert f"cd {folder_name}" in run_script, "Should cd into folder for uv sync"
        assert f"python {folder_name}/main.py" in run_script, (
            "Should run folder_name/main.py"
        )

        # Run the job
        job.approve()
        do_manager.job_runner.process_approved_jobs()

        # Verify .venv was created inside the code folder (by uv sync)
        assert (job_dir / folder_name / ".venv").exists(), (
            ".venv should be created inside folder by uv sync"
        )

        do_manager.sync()
        ds_manager.sync()

        # Verify the job completed and produced output
        output_path = ds_manager.job_client.jobs[-1].output_paths[0]
        with open(output_path, "r") as f:
            json_content = json.loads(f.read())

        # Verify the helper module was imported and used correctly
        assert json_content["original"] == "Hello, world private!"
        assert json_content["processed"] == "Processed: Hello, world private!"
        assert json_content["multiplier"] == 3

    finally:
        shutil.rmtree(project_dir, ignore_errors=True)


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
    do_cache = do_manager.datasite_owner_syncer.event_cache
    assert result_rel_path not in do_cache.file_hashes, (
        "Hash should be removed from DO cache"
    )

    ds_cache = ds_manager.datasite_watcher_syncer.datasite_watcher_cache
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
    do_cache = do_manager.datasite_owner_syncer.event_cache
    assert job_path_in_datasite in [
        str(p) for p, _ in do_cache.file_connection.get_items()
    ]

    # Simulate deletion by removing from DO cache
    do_cache.file_connection.delete_file(job_path_in_datasite)

    # Process deletion
    do_manager.sync()
    ds_manager.sync()

    # Verify deletion propagated
    ds_cache = ds_manager.datasite_watcher_syncer.datasite_watcher_cache
    ds_path = Path(do_manager.email) / job_path_in_datasite
    assert str(ds_path) not in [str(p) for p, _ in ds_cache.file_connection.get_items()]


def test_syft_datasets_excluded_from_outbox_sync():
    """Test that files in syft_datasets folder are excluded from outbox sync.

    Datasets have their own dedicated sync channel with proper permissions,
    so they should not be broadcast to all peers via the general outbox.
    """
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False
    )

    datasite_dir_do = do_manager.syftbox_folder / do_manager.email

    # Create a regular file (should be synced)
    regular_file = datasite_dir_do / "public" / "regular_file.txt"
    regular_file.parent.mkdir(parents=True, exist_ok=True)
    regular_file.write_text("regular content")

    # Create a dataset file (should NOT be synced via outbox)
    dataset_file = (
        datasite_dir_do / "public" / "syft_datasets" / "my_dataset" / "dataset.yaml"
    )
    dataset_file.parent.mkdir(parents=True, exist_ok=True)
    dataset_file.write_text("name: my_dataset")

    # Sync DO to generate events
    do_manager.sync()

    # Check which files are in the DO's event cache (i.e., what gets sent to outbox)
    do_cache = do_manager.datasite_owner_syncer.event_cache
    cached_paths = [str(p) for p in do_cache.file_hashes.keys()]

    # Regular file should be in cache (will be synced)
    assert any("regular_file.txt" in p for p in cached_paths), (
        "Regular files should be included in outbox sync"
    )

    # Dataset file should NOT be in cache (excluded from outbox)
    assert not any("syft_datasets" in p for p in cached_paths), (
        "Files in syft_datasets should be excluded from outbox sync"
    )


def test_job_files_only_sync_to_submitter():
    """Test that job files only sync to the peer who submitted the job.

    When a DO has multiple approved peers, job results should only be sent
    to the peer who submitted that specific job, not broadcast to all peers.
    """
    import yaml

    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
        use_in_memory_cache=False
    )

    # The submitter is a different peer (not ds_manager)
    submitter_email = "submitter_peer@example.com"
    non_submitter_email = ds_manager.email

    datasite_dir_do = do_manager.syftbox_folder / do_manager.email

    # Create a job with config.yaml that has submitted_by set to the submitter
    job_name = "test_job_123"
    job_dir = datasite_dir_do / "app_data" / "job" / job_name
    job_dir.mkdir(parents=True, exist_ok=True)

    # Write config.yaml with submitted_by
    config_path = job_dir / "config.yaml"
    config_data = {"submitted_by": submitter_email, "status": "completed"}
    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    # Create job result file
    result_file = job_dir / "outputs" / "result.json"
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_text('{"result": 42}')

    # Create a regular file (non-job) that should go to all peers
    regular_file = datasite_dir_do / "public" / "shared.txt"
    regular_file.parent.mkdir(parents=True, exist_ok=True)
    regular_file.write_text("shared content")

    # Process local changes with both recipients
    recipients = [submitter_email, non_submitter_email]
    do_manager.datasite_owner_syncer.process_local_changes(recipients)

    # Check what's in the outbox folders
    backing_store = do_manager.connection_router.connections[0].backing_store

    # Get events from per-recipient outbox folders
    submitter_folder = backing_store.get_outbox_folder(
        owner_email=do_manager.email, recipient_email=submitter_email
    )
    non_submitter_folder = backing_store.get_outbox_folder(
        owner_email=do_manager.email, recipient_email=non_submitter_email
    )

    submitter_events = submitter_folder.messages if submitter_folder else []
    non_submitter_events = non_submitter_folder.messages if non_submitter_folder else []

    # Extract paths from events
    submitter_paths = []
    for msg in submitter_events:
        for event in msg.events:
            submitter_paths.append(str(event.path_in_datasite))

    non_submitter_paths = []
    for msg in non_submitter_events:
        for event in msg.events:
            non_submitter_paths.append(str(event.path_in_datasite))

    # Job files should ONLY be in submitter's outbox
    assert any("app_data/job" in p for p in submitter_paths), (
        "Job files should be sent to submitter"
    )
    assert not any("app_data/job" in p for p in non_submitter_paths), (
        "Job files should NOT be sent to non-submitter peers"
    )

    # Regular files should be in BOTH outboxes
    assert any("shared.txt" in p for p in submitter_paths), (
        "Regular files should be sent to submitter"
    )
    assert any("shared.txt" in p for p in non_submitter_paths), (
        "Regular files should be sent to non-submitter peers"
    )
