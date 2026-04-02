"""Tests for the standalone delete_syftbox utility function."""

from pathlib import Path
from unittest.mock import patch

import pytest

from syft_client.gdrive_utils import delete_syftbox


EMAIL = "test@example.com"


class TestDeleteSyftboxValidation:
    """Test argument validation (no GDrive calls needed)."""

    @patch("syft_client.gdrive_utils.check_env", return_value=None)
    def test_raises_without_email_locally(self, _):
        with pytest.raises(ValueError, match="email is required"):
            delete_syftbox(token_path="/fake/token.json")

    @patch("syft_client.gdrive_utils.check_env", return_value=None)
    @patch("syft_client.gdrive_utils.settings")
    def test_raises_without_token_locally(self, mock_settings, _):
        mock_settings.token_path = None
        with pytest.raises(ValueError, match="token_path is required"):
            delete_syftbox(email=EMAIL)


class TestDeleteSyftboxLocalDirs:
    """Test local directory cleanup (no GDrive calls needed)."""

    @patch("syft_client.gdrive_utils.check_env", return_value=None)
    @patch("syft_client.sync.connections.drive.gdrive_transport.GDriveConnection.from_token_path")
    def test_deletes_local_dirs(self, mock_from_token, _, tmp_path):
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

    @patch("syft_client.gdrive_utils.check_env", return_value=None)
    @patch("syft_client.sync.connections.drive.gdrive_transport.GDriveConnection.from_token_path")
    def test_skips_missing_local_dirs(self, mock_from_token, _, tmp_path):
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


class TestDeleteSyftboxImport:
    def test_importable_from_top_level(self):
        from syft_client import delete_syftbox as fn
        assert callable(fn)
