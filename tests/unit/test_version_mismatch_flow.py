"""End-to-end test for version mismatch and backup flow with mock drive."""

from unittest.mock import patch

from syft_client.gdrive_utils import delete_local_syftbox
from syft_client.sync.connections.drive.gdrive_transport import (
    GDRIVE_P2P_FOLDER_DATASITE_PREFIX,
    GOOGLE_FOLDER_MIME_TYPE,
)
from syft_client.sync.syftbox_manager import SyftboxManager

from tests.unit.utils import create_test_project_folder, create_tmp_dataset_files

NEW_VERSION = "99.0.0"

# All modules that import SYFT_CLIENT_VERSION at module level
VERSION_PATCHES = [
    "syft_client.version.SYFT_CLIENT_VERSION",
    "syft_client.sync.connections.drive.gdrive_transport.SYFT_CLIENT_VERSION",
    "syft_client.sync.login.SYFT_CLIENT_VERSION",
]


def _patch_version():
    """Context manager that patches SYFT_CLIENT_VERSION everywhere."""
    import contextlib

    return contextlib.ExitStack()


def _apply_version_patches(stack):
    for target in VERSION_PATCHES:
        stack.enter_context(patch(target, NEW_VERSION))


def _list_version_subfolders(connection, p2p_folder_id):
    """List version subfolder names inside a P2P folder."""
    q = (
        f"'{p2p_folder_id}' in parents"
        f" and mimeType='{GOOGLE_FOLDER_MIME_TYPE}'"
        " and trashed=false"
    )
    results = connection.drive_service.files().list(q=q, fields="files(name)").execute()
    return [f["name"] for f in results.get("files", [])]


def _find_p2p_folders(connection, email):
    """Find all P2P folders owned by this connection's user for a given email."""
    q = (
        f"name contains '{GDRIVE_P2P_FOLDER_DATASITE_PREFIX}'"
        f" and mimeType='{GOOGLE_FOLDER_MIME_TYPE}'"
        " and 'me' in owners and trashed=false"
    )
    results = (
        connection.drive_service.files().list(q=q, fields="files(id, name)").execute()
    )
    return results.get("files", [])


def test_version_mismatch_and_backup_flow():
    """Full flow: create state on v1 -> upgrade to v2 -> old state preserved, new version works."""

    # -- Step 1: Create DO/DS on current version --
    ds_manager, do_manager = SyftboxManager.pair_with_mock_drive_service_connection(
        use_in_memory_cache=False,
        sync_automatically=False,
    )

    # -- Step 2: Create dataset + submit job --
    mock_path, private_path, readme_path = create_tmp_dataset_files()
    do_manager.create_dataset(
        name="my dataset",
        mock_path=mock_path,
        private_path=private_path,
        summary="Test dataset",
        readme_path=readme_path,
        users=[ds_manager.email],
    )
    do_manager.sync()
    ds_manager.sync()

    project_dir = create_test_project_folder(with_pyproject=False)
    ds_manager.submit_python_job(
        user=do_manager.email,
        code_path=str(project_dir),
        job_name="pre_upgrade.job",
        entrypoint="main.py",
    )
    do_manager.sync()
    assert len(do_manager.jobs) == 1
    do_manager.jobs[0].approve()
    do_manager.process_approved_jobs()
    do_manager.sync()
    ds_manager.sync()

    # Verify job completed on DO side
    assert do_manager.jobs[0].status == "done"

    # Record P2P folder state before upgrade
    do_conn = do_manager.peer_manager.connection_router.connections[0]
    do_p2p_folders_before = _find_p2p_folders(do_conn, ds_manager.email)
    assert len(do_p2p_folders_before) > 0

    # -- Step 3: Simulate DO upgrade --
    with _patch_version() as stack:
        _apply_version_patches(stack)

        # Delete local state (simulates upgrade choice [1])
        delete_local_syftbox(
            email=do_manager.email,
            local_syftbox_path=do_manager.syftbox_folder,
        )
        do_manager.reset_all_connection_caches()

        # Reload peers + restore permissions (what _init_client does)
        do_manager.load_peers()
        do_manager.ensure_local_peer_permissions()

        # Verify: old P2P folders still exist (not deleted)
        do_p2p_folders_after = _find_p2p_folders(do_conn, ds_manager.email)
        assert len(do_p2p_folders_after) == len(do_p2p_folders_before)

        # Verify: version subfolders created in DO-owned P2P folders
        for folder in do_p2p_folders_after:
            subfolders = _list_version_subfolders(do_conn, folder["id"])
            assert NEW_VERSION in subfolders, (
                f"Missing {NEW_VERSION} subfolder in {folder['name']}"
            )

        # -- Step 4: DS also upgrades --
        delete_local_syftbox(
            email=ds_manager.email,
            local_syftbox_path=ds_manager.syftbox_folder,
        )
        ds_manager.reset_all_connection_caches()
        ds_manager.load_peers()
        ds_manager.ensure_local_peer_permissions()

        # -- Step 5: DS submits new job on new version --
        # Use a simple bash job (no dataset dependency — datasets were
        # deleted locally during upgrade)
        ds_manager.submit_bash_job(
            user=do_manager.email,
            script='echo "hello from new version"',
            job_name="post_upgrade.job",
        )

        # DO syncs and processes the new job
        do_manager.sync()
        new_jobs = [j for j in do_manager.jobs if j.name == "post_upgrade.job"]
        assert len(new_jobs) == 1, f"Expected 1 post_upgrade job, got {len(new_jobs)}"

        new_jobs[0].approve()
        do_manager.process_approved_jobs()
        do_manager.sync()

        # Re-fetch to get updated status
        done_jobs = [j for j in do_manager.jobs if j.name == "post_upgrade.job"]
        assert done_jobs[0].status == "done"
