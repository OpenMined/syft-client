from syft_datasets.dataset import Dataset
from syft_client.sync.syftbox_manager import SyftboxManager
import os
from pathlib import Path
import time
import json
from time import sleep
import pytest
from tests.unit.utils import create_tmp_dataset_files

# from tests.integration.utils import get_mock_events


SYFT_CLIENT_DIR = Path(__file__).parent.parent.parent
# These are in gitignore, create yourself
CREDENTIALS_DIR = SYFT_CLIENT_DIR / "credentials"

# koen gmail
FILE_DO = os.environ.get("beach_credentials_fname_do", "token_do.json")
EMAIL_DO = os.environ["BEACH_EMAIL_DO"]

# koen openmined mail
FILE_DS = os.environ.get("beach_credentials_fname_ds", "token_ds.json")
EMAIL_DS = os.environ["BEACH_EMAIL_DS"]


token_path_do = CREDENTIALS_DIR / FILE_DO
token_path_ds = CREDENTIALS_DIR / FILE_DS


def remove_syftboxes_from_drive():
    manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        add_peers=False,
    )
    manager_ds.delete_syftbox()
    manager_do.delete_syftbox()


@pytest.fixture()
def setup_delete_syftboxes():
    print("\nCleaning up syftboxes from drive for integration tests")
    tokens_exist = token_path_do.exists() and token_path_ds.exists()
    if not tokens_exist:
        raise ValueError(
            """"Credentials not found, create them using scripts/create_token.py and store them in /credentials
            as token_do.json and token_ds.json. Also set the environment variables BEACH_EMAIL_DO and BEACH_EMAIL_DS to the email addresses of the DO and DS."""
        )
    remove_syftboxes_from_drive()
    print("Syftboxes deleted from drive, starting tests")
    yield
    print("Tearing down")


@pytest.mark.usefixtures("setup_delete_syftboxes")
def test_google_drive_connection_syncing():
    manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
    )

    # this calls connection.send_propose_file_change_message via callbacks
    sleep(1)
    start_time = time.time()
    manager_ds.send_file_change(f"{EMAIL_DO}/my.job", "Hello, world!")
    end_time_sending = time.time()
    print(f"Time taken to send message: {end_time_sending - start_time} seconds")

    # wait for the message to be sent, this is not always needed
    sleep(1)

    # this is just for timing purposes, you can ignore it
    # continuing with the test

    manager_do.proposed_file_change_handler.sync(peer_emails=[EMAIL_DS])
    assert (
        len(manager_do.proposed_file_change_handler.event_cache.get_cached_events()) > 0
    )

    manager_ds.sync()

    events = (
        manager_ds.datasite_outbox_puller.datasite_watcher_cache.get_cached_events()
    )
    assert len(events) > 0


@pytest.mark.usefixtures("setup_delete_syftboxes")
def test_google_drive_connection_load_state():
    # create the state

    # load the clients and add the peers
    manager_ds1, manager_do1 = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        add_peers=True,
        load_peers=False,
    )

    # make some changes
    manager_ds1.send_file_change(f"{EMAIL_DO}/my.job", "Hello, world!")
    manager_ds1.send_file_change(f"{EMAIL_DO}/my_second.job", "Hello, world!")

    # test loading the peers and loading the inbox
    manager_ds2, manager_do2 = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        add_peers=False,
        load_peers=False,
    )

    manager_do2.load_peers()
    assert len(manager_do2.peers) == 1

    manager_ds2.load_peers()
    assert len(manager_ds2.peers) == 1

    # sync so we have something in the syftbox and do outbox
    manager_do2.sync()

    assert (
        len(manager_do2.proposed_file_change_handler.event_cache.get_cached_events())
        == 2
    )

    # we have created some state now, so now we can log in again and load the state
    manager_ds3, manager_do3 = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        add_peers=False,
        load_peers=True,
    )

    manager_do3.sync()
    manager_ds3.sync()

    loaded_events_do = (
        manager_do3.proposed_file_change_handler.event_cache.get_cached_events()
    )
    assert len(loaded_events_do) == 2

    loaded_events_ds = (
        manager_ds3.datasite_outbox_puller.datasite_watcher_cache.get_cached_events()
    )
    assert len(loaded_events_ds) == 2


@pytest.mark.usefixtures("setup_delete_syftboxes")
def test_google_drive_files():
    manager_ds, manager_do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        use_in_memory_cache=False,
    )

    # syftbox_dir / EMAIL_DO
    datasite_dir_do = (
        manager_do.proposed_file_change_handler.event_cache.file_connection.base_dir
    )

    # syftbox_dir (ds)
    syftbox_dir_ds = manager_ds.datasite_outbox_puller.datasite_watcher_cache.file_connection.base_dir

    assert datasite_dir_do != syftbox_dir_ds

    job_path = "test.job"
    job_send_path = f"{EMAIL_DO}/{job_path}"

    manager_ds.send_file_change(job_send_path, "This is a job")
    sleep(1)

    manager_do.sync()

    assert (datasite_dir_do / job_path).exists()

    result_rel_path = "test_result.result"
    result_path = datasite_dir_do / result_rel_path
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with open(result_path, "w") as f:
        f.write("I am a result")

    manager_do.sync()
    sleep(1)

    manager_ds.sync()

    assert (syftbox_dir_ds / EMAIL_DO / result_rel_path).exists()


@pytest.mark.usefixtures("setup_delete_syftboxes")
def test_datasets():
    ds_manager, do_manager = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        use_in_memory_cache=False,
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

    # Retrieve dataset by name
    dataset_do = do_manager.datasets["my dataset"]
    assert isinstance(dataset_do, Dataset)

    ds_manager.sync()

    assert len(ds_manager.datasets.get_all()) == 1

    dataset_ds = ds_manager.datasets.get("my dataset", datasite=do_manager.email)

    mock_content_ds = (dataset_ds.mock_dir / "mock.txt").read_text()
    assert len(mock_content_ds) > 0

    def has_file(root_dir, filename):
        return any(p.name == filename for p in Path(root_dir).rglob("*"))

    assert has_file(ds_manager.syftbox_folder, "mock.txt")
    assert not has_file(ds_manager.syftbox_folder, "private.txt")


@pytest.mark.usefixtures("setup_delete_syftboxes")
def test_jobs():
    ds_manager, do_manager = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        use_in_memory_cache=False,
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
