from syft_client.syncv2.syftbox_manager import SyftboxManager
from syft_client.syncv2.connections.inmemory_connection import InMemoryBackingPlatform
from syft_client.syncv2.messages.proposed_filechange import ProposedFileChange
from syft_client.syncv2.events.file_change_event import FileChangeEvent
from syft_client.syncv2.messages.proposed_filechange import ProposedFileChangesMessage
import pytest
import uuid
import time
from typing import List

from syft_client.syncv2.events.file_change_event import FileChangeEventFileName
from syft_client.syncv2.sync.caches.datasite_owner_cache import (
    ProposedEventFileOutdatedException,
)


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

    events_in_backing_platform = do_manager.get_all_events()
    assert len(events_in_backing_platform) == 0

    ds_manager.send_file_change(file_path, "Hello, world!")

    # second event is present
    events_in_backing_platform = do_manager.get_all_events()
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

    # print(do_manager.proposed_file_change_handler.connection_router.get_all_events())


def test_sync_back_to_ds_cache():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()
    file_path = "email@email.com/test.job"
    ds_manager.send_file_change(file_path, "Hello, world!")

    ds_manager.sync()
    assert (
        len(ds_manager.datasite_outbox_puller.datasite_watcher_cache.get_all_events())
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
