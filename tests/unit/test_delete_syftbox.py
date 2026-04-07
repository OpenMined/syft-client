"""Tests for the standalone delete_syftbox utility function."""

from unittest.mock import patch


from syft_client.gdrive_utils import (
    delete_syftbox,
    _get_default_syftbox_path,
)


EMAIL = "test@example.com"


class TestDeleteSyftboxLocalDirs:
    """Test local directory cleanup (no GDrive calls needed)."""

    @patch(
        "syft_client.sync.connections.drive.gdrive_transport.GDriveConnection.from_token_path"
    )
    def test_deletes_local_dirs(self, mock_from_token, tmp_path):
        mock_conn = mock_from_token.return_value
        mock_conn.gather_all_file_and_folder_ids.return_value = []
        mock_conn.find_orphaned_message_files.return_value = []
        syftbox_dir = tmp_path / "my_syftbox"
        events_dir = tmp_path / "my_syftbox-events"
        event_messages_dir = tmp_path / "my_syftbox-event-messages"
        for d in [syftbox_dir, events_dir, event_messages_dir]:
            d.mkdir()
            (d / "dummy.txt").write_text("data")

        delete_syftbox(
            token_path="/fake/token.json",
            email=EMAIL,
            local_syftbox_path=syftbox_dir,
            verbose=False,
        )

        assert not syftbox_dir.exists()
        assert not events_dir.exists()
        assert not event_messages_dir.exists()

    @patch(
        "syft_client.sync.connections.drive.gdrive_transport.GDriveConnection.from_token_path"
    )
    def test_skips_missing_local_dirs(self, mock_from_token, tmp_path):
        mock_conn = mock_from_token.return_value
        mock_conn.gather_all_file_and_folder_ids.return_value = []
        mock_conn.find_orphaned_message_files.return_value = []

        nonexistent = tmp_path / "does_not_exist"

        # Should not raise
        delete_syftbox(
            token_path="/fake/token.json",
            email=EMAIL,
            local_syftbox_path=nonexistent,
            verbose=False,
        )


class TestDeleteSyftboxAutoDetect:
    """Test auto-detection of local SyftBox path."""

    def test_default_path_jupyter(self):
        from pathlib import Path

        path = _get_default_syftbox_path(EMAIL)
        assert path == Path.home() / f"SyftBox_{EMAIL}"

    def test_default_path_colab(self):
        from pathlib import Path
        from syft_client.sync.environments.environment import Environment

        with patch(
            "syft_client.gdrive_utils.check_env", return_value=Environment.COLAB
        ):
            path = _get_default_syftbox_path(EMAIL)
        assert path == Path("/content") / f"SyftBox_{EMAIL}"

    @patch(
        "syft_client.sync.connections.drive.gdrive_transport.GDriveConnection.from_token_path"
    )
    def test_auto_detects_local_path(self, mock_from_token, tmp_path):
        """When local_syftbox_path is not provided, auto-detects and cleans up."""
        mock_conn = mock_from_token.return_value
        mock_conn.gather_all_file_and_folder_ids.return_value = []
        mock_conn.find_orphaned_message_files.return_value = []

        # Patch the default path to point to tmp_path
        syftbox_dir = tmp_path / f"SyftBox_{EMAIL}"
        events_dir = tmp_path / f"SyftBox_{EMAIL}-events"
        event_messages_dir = tmp_path / f"SyftBox_{EMAIL}-event-messages"
        for d in [syftbox_dir, events_dir, event_messages_dir]:
            d.mkdir()
            (d / "dummy.txt").write_text("data")

        with patch(
            "syft_client.gdrive_utils._get_default_syftbox_path",
            return_value=syftbox_dir,
        ):
            delete_syftbox(
                token_path="/fake/token.json",
                email=EMAIL,
                verbose=False,
            )

        assert not syftbox_dir.exists()
        assert not events_dir.exists()
        assert not event_messages_dir.exists()


class TestDeleteSyftboxImport:
    def test_importable_from_top_level(self):
        from syft_client import delete_syftbox as fn

        assert callable(fn)
