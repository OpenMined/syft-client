"""Tests for Wave 2: DriveInboxScanner."""

import json
from unittest.mock import MagicMock, patch

from syft_bg.sync.drive_inbox_scanner import DriveInboxScanner
from syft_bg.sync.snapshot import InboxMessage


def _mock_drive(files_list_result=None):
    drive = MagicMock()
    if files_list_result is None:
        files_list_result = {"files": []}
    drive.files().list().execute.return_value = files_list_result
    return drive


class TestScanInboxMessages:
    def test_empty_when_no_folders(self):
        scanner = DriveInboxScanner(_mock_drive(), "do@test.com")
        assert scanner.scan_inbox_messages() == []

    def test_returns_inbox_message_for_valid_job(self):
        drive = MagicMock()

        # _find_inbox_folders returns one folder
        folders_result = {
            "files": [
                {
                    "name": "syft_datasite#do@test.com#inbox#ds@test.com",
                    "id": "folder1",
                }
            ]
        }
        # _get_pending_messages returns one message
        messages_result = {"files": [{"id": "msg1", "name": "msgv2_001"}]}

        # Chain the list calls: first for folders, second for messages
        drive.files().list().execute.side_effect = [folders_result, messages_result]

        # _parse_job_from_message: mock the ProposedFileChangesMessage
        mock_change = MagicMock()
        mock_change.path_in_datasite = "app_data/job/test_job/config.yaml"

        mock_msg = MagicMock()
        mock_msg.proposed_file_changes = [mock_change]
        mock_msg.sender_email = "ds@test.com"

        drive.files().get_media().execute.return_value = b"compressed_data"

        with patch.dict(
            "sys.modules",
            {
                "syft_client.sync.messages.proposed_filechange": MagicMock(
                    ProposedFileChangesMessage=MagicMock(
                        from_compressed_data=MagicMock(return_value=mock_msg)
                    )
                )
            },
        ):
            scanner = DriveInboxScanner(drive, "do@test.com")
            results = scanner.scan_inbox_messages()

        assert len(results) == 1
        assert isinstance(results[0], InboxMessage)
        assert results[0].job_name == "test_job"
        assert results[0].submitter == "ds@test.com"
        assert results[0].message_id == "msg1"

    def test_handles_drive_error(self):
        drive = MagicMock()
        drive.files().list().execute.side_effect = Exception("API error")
        scanner = DriveInboxScanner(drive, "do@test.com")
        assert scanner.scan_inbox_messages() == []


class TestScanPeerEmails:
    def test_empty_when_no_folders(self):
        scanner = DriveInboxScanner(_mock_drive(), "do@test.com")
        assert scanner.scan_peer_emails() == []

    def test_extracts_sender_emails(self):
        drive = _mock_drive(
            {
                "files": [
                    {
                        "name": "syft_datasite#do@test.com#inbox#ds@test.com",
                        "id": "f1",
                    }
                ]
            }
        )
        scanner = DriveInboxScanner(drive, "do@test.com")
        peers = scanner.scan_peer_emails()
        assert "ds@test.com" in peers

    def test_excludes_do_as_peer(self):
        drive = _mock_drive(
            {
                "files": [
                    {
                        "name": "syft_datasite#do@test.com#inbox#do@test.com",
                        "id": "f1",
                    }
                ]
            }
        )
        scanner = DriveInboxScanner(drive, "do@test.com")
        # DO should not appear as its own peer
        assert scanner.scan_peer_emails() == []

    def test_filters_by_datasite_email(self):
        drive = _mock_drive(
            {
                "files": [
                    {
                        "name": "syft_datasite#other@test.com#inbox#ds@test.com",
                        "id": "f1",
                    }
                ]
            }
        )
        scanner = DriveInboxScanner(drive, "do@test.com")
        # Folder belongs to other datasite, not ours
        assert scanner.scan_peer_emails() == []

    def test_handles_drive_error(self):
        drive = MagicMock()
        drive.files().list().execute.side_effect = Exception("API error")
        scanner = DriveInboxScanner(drive, "do@test.com")
        assert scanner.scan_peer_emails() == []


class TestScanApprovedPeers:
    def test_empty_when_no_peers_file(self):
        scanner = DriveInboxScanner(_mock_drive(), "do@test.com")
        assert scanner.scan_approved_peers() == []

    def test_parses_accepted_peers(self):
        drive = MagicMock()
        drive.files().list().execute.return_value = {"files": [{"id": "f1"}]}
        peers_json = json.dumps(
            {
                "ds@test.com": {"state": "accepted"},
                "other@test.com": {"state": "pending"},
            }
        ).encode()
        drive.files().get_media().execute.return_value = peers_json
        scanner = DriveInboxScanner(drive, "do@test.com")
        approved = scanner.scan_approved_peers()
        assert "ds@test.com" in approved
        assert "other@test.com" not in approved

    def test_handles_drive_error(self):
        drive = MagicMock()
        drive.files().list().execute.side_effect = Exception("API error")
        scanner = DriveInboxScanner(drive, "do@test.com")
        assert scanner.scan_approved_peers() == []


class TestParseP2PFolderName:
    def test_valid_folder(self):
        result = DriveInboxScanner._parse_p2p_folder_name(
            "syft_datasite#do@test.com#inbox#ds@test.com"
        )
        assert result == {
            "datasite_email": "do@test.com",
            "folder_type": "inbox",
            "peer_email": "ds@test.com",
        }

    def test_invalid_prefix(self):
        assert DriveInboxScanner._parse_p2p_folder_name("other#a#b#c") is None

    def test_wrong_part_count(self):
        assert DriveInboxScanner._parse_p2p_folder_name("syft_datasite#a#b") is None
