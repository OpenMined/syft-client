from syft_client.syncv2.syftbox_manager import SyftboxManager


def test_in_memory_connection():
    manager1, manager2 = SyftboxManager.pair_with_in_memory_connection()
    message_received = False

    def patch_file_receive(*args, **kwargs):
        nonlocal message_received
        message_received = True

    manager2.file_change_handler.handle_file_change = patch_file_receive

    manager1.send_file_change("test.txt", "Hello, world!")
    assert message_received


test_in_memory_connection()
