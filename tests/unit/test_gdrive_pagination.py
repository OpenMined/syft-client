from unittest.mock import Mock
from syft_client.sync.connections.drive.gdrive_transport import GDriveConnection


def create_mock_connection():
    conn = GDriveConnection(email="test@test.com", verbose=False)
    conn.drive_service = Mock()
    return conn


def test_single_page_works():
    """Current implementation works for single page (< 100 files)"""
    conn = create_mock_connection()

    conn.drive_service.files().list().execute.return_value = {
        "files": [{"name": "file1.txt", "id": "id1"}]
    }

    files = conn.get_file_metadatas_from_folder("folder_id")

    assert len(files) == 1
    assert files[0]["name"] == "file1.txt"


def test_multiple_pages_pagination():
    """When there are >100 files, should fetch all pages"""
    conn = create_mock_connection()

    conn.drive_service.files().list().execute.side_effect = [
        {"files": [{"name": "file1.txt", "id": "id1"}], "nextPageToken": "token1"},
        {"files": [{"name": "file2.txt", "id": "id2"}], "nextPageToken": "token2"},
        {"files": [{"name": "file3.txt", "id": "id3"}]},
    ]

    files = conn.get_file_metadatas_from_folder("folder_id")

    assert len(files) == 3
    assert conn.drive_service.files().list().execute.call_count == 3


def test_empty_folder():
    """Empty folder should return empty list"""
    conn = create_mock_connection()

    conn.drive_service.files().list().execute.return_value = {"files": []}

    files = conn.get_file_metadatas_from_folder("folder_id")

    assert files == []
