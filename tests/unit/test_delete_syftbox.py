"""Tests for version mismatch check and delete_syftbox utilities."""

from unittest.mock import patch, MagicMock

from syft_client.gdrive_utils import (
    delete_syftbox,
    read_local_version,
    write_local_version,
)
from syft_client.sync.version.version_info import VersionInfo
from syft_client.version import VERSION_FILE_NAME, SYFT_CLIENT_VERSION


EMAIL = "test@example.com"


def _old_version_info() -> VersionInfo:
    return VersionInfo(
        syft_client_version="0.0.1",
        min_supported_syft_client_version="0.0.1",
        protocol_version="1.0.0",
        min_supported_protocol_version="1.0.0",
    )


def _make_client(tmp_path, has_do_role=False, has_ds_role=False):
    client = MagicMock()
    client.email = EMAIL
    client.has_do_role = has_do_role
    client.has_ds_role = has_ds_role
    client.syftbox_folder = tmp_path / f"SyftBox_{EMAIL}"
    client.syftbox_folder.mkdir(parents=True, exist_ok=True)
    # _get_client_token_path reads connections[0].token_path
    client.peer_manager.connection_router.connections = [
        MagicMock(token_path="/fake/token.json")
    ]
    return client


class TestLocalVersionRoundTrip:
    def test_read_returns_none_when_no_file(self, tmp_path):
        assert read_local_version(tmp_path) is None

    def test_write_then_read(self, tmp_path):
        write_local_version(tmp_path)
        version_info = read_local_version(tmp_path)
        assert version_info is not None
        assert version_info.syft_client_version == SYFT_CLIENT_VERSION


class TestVersionMismatchCheck:
    """Test _check_existing_state_version with role-aware DO/DS handling."""

    @patch("syft_client.sync.login.delete_remote_syftbox")
    @patch("syft_client.sync.login.delete_local_syftbox")
    @patch("builtins.input", return_value="1")
    def test_do_mismatch_deletes_all(
        self, mock_input, mock_delete_local, mock_delete_remote, tmp_path
    ):
        """DO with mismatch picks delete → both local and remote deleted."""
        from syft_client.sync.login import _check_existing_state_version

        client = _make_client(tmp_path, has_do_role=True)
        version_file = client.syftbox_folder / VERSION_FILE_NAME
        version_file.write_text(_old_version_info().to_json())
        client.read_own_version.return_value = _old_version_info()

        _check_existing_state_version(client)

        mock_delete_local.assert_called_once()
        mock_delete_remote.assert_called_once()
        mock_input.assert_called_once()

    @patch("syft_client.sync.login.delete_remote_syftbox")
    @patch("syft_client.sync.login.delete_local_syftbox")
    @patch("syft_client.sync.login.archive_remote_p2p_folders", return_value={"id1"})
    @patch("builtins.input", return_value="1")
    def test_ds_mismatch_archive(
        self, mock_input, mock_archive, mock_delete_local, mock_delete_remote, tmp_path
    ):
        """DS with mismatch picks archive → archive called, then delete with exclude_ids."""
        from syft_client.sync.login import _check_existing_state_version

        client = _make_client(tmp_path, has_ds_role=True)
        version_file = client.syftbox_folder / VERSION_FILE_NAME
        version_file.write_text(_old_version_info().to_json())
        client.read_own_version.return_value = _old_version_info()

        _check_existing_state_version(client)

        mock_archive.assert_called_once()
        mock_delete_remote.assert_called_once()
        # Verify exclude_ids was passed through
        call_kwargs = mock_delete_remote.call_args[1]
        assert call_kwargs["exclude_ids"] == {"id1"}

    @patch("syft_client.sync.login.delete_remote_syftbox")
    @patch("syft_client.sync.login.delete_local_syftbox")
    @patch("builtins.input", return_value="2")
    def test_ds_mismatch_delete(
        self, mock_input, mock_delete_local, mock_delete_remote, tmp_path
    ):
        """DS with mismatch picks delete → no archive, just delete."""
        from syft_client.sync.login import _check_existing_state_version

        client = _make_client(tmp_path, has_ds_role=True)
        client.read_own_version.return_value = _old_version_info()

        _check_existing_state_version(client)

        mock_delete_local.assert_called_once()
        mock_delete_remote.assert_called_once()

    def test_no_mismatch_no_prompt(self, tmp_path):
        """Both versions match installed → no prompt."""
        from syft_client.sync.login import _check_existing_state_version

        client = _make_client(tmp_path, has_do_role=True)
        write_local_version(client.syftbox_folder)
        client.read_own_version.return_value = VersionInfo.current()

        # Should not call input() — if it did, it would error since input is not mocked
        _check_existing_state_version(client)


class TestDeleteSyftboxImport:
    def test_importable_from_top_level(self):
        from syft_client import delete_syftbox as fn
        assert callable(fn)

    def test_new_functions_importable_from_top_level(self):
        from syft_client import delete_local_syftbox, delete_remote_syftbox
        assert callable(delete_local_syftbox)
        assert callable(delete_remote_syftbox)

    def test_archive_importable_from_top_level(self):
        from syft_client import archive_remote_p2p_folders
        assert callable(archive_remote_p2p_folders)
