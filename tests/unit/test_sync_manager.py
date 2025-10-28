from syft_client.syncv2.syftbox_manager import SyftboxManager
from syft_client.syncv2.messages.proposed_filechange import ProposedFileChange
import pytest

from syft_client.syncv2.sync.caches.datasite_owner_cache import (
    ProposedEventFileOutdatedException,
)


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

    ds_manager.datasite_outbox_puller.datasite_watcher_cache.sync_down(
        peer_email="email@email.com"
    )
    assert (
        len(ds_manager.datasite_outbox_puller.datasite_watcher_cache.get_all_events())
        == 1
    )
