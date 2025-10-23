from syft_client.syncv2.syftbox_manager import SyftboxManager
from syft_client.syncv2.messages.proposed_filechange import ProposedFileChange


def test_in_memory_connection():
    manager1, manager2 = SyftboxManager.pair_with_in_memory_connection()
    message_received = False

    def patch_job_handler_file_receive(*args, **kwargs):
        nonlocal message_received
        message_received = True

    manager2.job_file_change_handler.handle_file_change = patch_job_handler_file_receive

    manager1.send_file_change("my.job", "Hello, world!")
    assert message_received


def test_sync_to_syftbox_eventlog():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()

    # initial event is present
    events_in_backing_platform = do_manager.get_all_events()
    assert len(events_in_backing_platform) == 1

    ds_manager.send_file_change("test.job", "Hello, world!")

    # second event is present
    events_in_backing_platform = do_manager.get_all_events()
    assert len(events_in_backing_platform) == 2


def test_merging_branches():
    ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()

    root_event_id = do_manager.proposed_file_change_handler.event_cache.get_checkpoint_root().event.id

    event1 = ProposedFileChange(
        path="test.job",
        content="Content 1",
        parent_id=root_event_id,
    )
    do_manager.proposed_file_change_handler.handle_proposed_filechange_event(event1)

    event2 = ProposedFileChange(
        path="test.job",
        content="Content 2",
        parent_id=root_event_id,
    )
    do_manager.proposed_file_change_handler.handle_proposed_filechange_event(event2)

    print(do_manager.proposed_file_change_handler.connection_router.get_all_events())
