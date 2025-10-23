from syft_client.syncv2.syftbox_manager import SyftboxManager


def test_in_memory_connection():
    manager1, manager2 = SyftboxManager.pair_with_google_drive_testing_connection()
    message_received = False

    def patch_job_handler_file_receive(*args, **kwargs):
        nonlocal message_received
        message_received = True

    manager2.job_file_change_handler.handle_file_change = patch_job_handler_file_receive

    manager1.send_file_change("my.job", "Hello, world!")
    assert message_received
