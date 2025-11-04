from pathlib import Path
from syft_client.sync.syftbox_manager import SyftboxManager
from syft_client.sync.connections.inmemory_connection import InMemoryBackingPlatform
from syft_client.sync.messages.proposed_filechange import ProposedFileChange
import pytest
from tests.unit.utils import create_tmp_dataset_files

from syft_client.sync.sync.caches.datasite_owner_cache import (
    ProposedEventFileOutdatedException,
)
from tests.unit.utils import get_mock_events
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

    events_in_backing_platform = do_manager.get_all_accepted_events_do()
    assert len(events_in_backing_platform) == 0

    ds_manager.send_file_change(file_path, "Hello, world!")

    # second event is present
    events_in_backing_platform = do_manager.get_all_accepted_events_do()
    assert len(events_in_backing_platform) > 0


def test_valid_and_invalid_proposed_filechange_event():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()
    ds_email = ds_manager.email

    file_path = "email@email.com/test.job"

    event1 = ProposedFileChange(
        old_hash=None,
        path=file_path,
        content="Content 1",
    )
    hash1 = event1.new_hash
    do_manager.proposed_file_change_handler.handle_proposed_filechange_event(
        ds_email, event1
    )

    event2 = ProposedFileChange(
        old_hash=hash1,
        path=file_path,
        content="Content 2",
    )
    do_manager.proposed_file_change_handler.handle_proposed_filechange_event(
        ds_email, event2
    )

    content = (
        do_manager.proposed_file_change_handler.event_cache.file_connection.read_file(
            file_path
        )
    )
    assert content == "Content 2"

    event3_outdated = ProposedFileChange(
        old_hash=hash1,
        path=file_path,
        content="Content 3",
    )

    # This should fail, as the event is outdated
    with pytest.raises(ProposedEventFileOutdatedException):
        do_manager.proposed_file_change_handler.handle_proposed_filechange_event(
            ds_email, event3_outdated
        )

    content = (
        do_manager.proposed_file_change_handler.event_cache.file_connection.read_file(
            file_path
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

    events = get_mock_events(2)
    store.event_log.extend(events)
    store.outboxes["all"].extend(events)

    # sync down existing state
    do_manager.sync()

    n_events_in_cache = len(
        do_manager.proposed_file_change_handler.event_cache.events_connection
    )
    n_files_in_cache = len(
        do_manager.proposed_file_change_handler.event_cache.file_connection
    )
    hashes_in_cache = len(
        do_manager.proposed_file_change_handler.event_cache.file_hashes
    )
    assert n_events_in_cache == 2
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

    n_events_in_cache = len(
        do_manager.proposed_file_change_handler.event_cache.events_connection
    )
    n_files_in_cache = len(
        do_manager.proposed_file_change_handler.event_cache.file_connection
    )
    hashes_in_cache = len(
        do_manager.proposed_file_change_handler.event_cache.file_hashes
    )
    assert n_events_in_cache == 2
    assert n_files_in_cache == 2
    assert hashes_in_cache == 2

    n_events_in_syftbox = len(
        do_manager.connection_router.connections[0].backing_store.event_log
    )
    assert n_events_in_syftbox == 2

    assert len(store.outboxes["all"]) == 2


def test_sync_existing_datasite_state_ds():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()

    store: InMemoryBackingPlatform = ds_manager.connection_router.connections[
        0
    ].backing_store

    events = get_mock_events(2)
    store.event_log.extend(events)
    store.outboxes["all"].extend(events)

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

    syftbox_dir_do = (
        do_manager.proposed_file_change_handler.event_cache.file_connection.base_dir
    )

    syftbox_dir_ds = ds_manager.datasite_outbox_puller.datasite_watcher_cache.file_connection.base_dir

    assert syftbox_dir_do != syftbox_dir_ds

    job_path = "email@email.com/test.job"

    ds_manager.send_file_change(job_path, "Hello, world!")

    assert (syftbox_dir_do / job_path).exists()

    result_rel_path = "do@email.com/test_result.job"
    result_path = syftbox_dir_do / result_rel_path
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with open(result_path, "w") as f:
        f.write("I am a result")

    do_manager.sync()

    ds_manager.sync()

    assert (syftbox_dir_ds / result_rel_path).exists()


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

    datasets = do_manager.datasets.get_all()
    assert len(datasets) == 1
    dataset = datasets[0]
    print(dataset.mock_url)

    ds_manager.sync()

    assert len(ds_manager.datasets.get_all()) == 1

    def has_file(root_dir, filename):
        return any(p.name == filename for p in Path(root_dir).rglob("*"))

    assert has_file(ds_manager.syftbox_folder, "mock.txt")
    assert not has_file(ds_manager.syftbox_folder, "private.txt")
