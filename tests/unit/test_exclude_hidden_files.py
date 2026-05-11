"""Tests for hidden/generated file exclusion in sync and notifications."""

import tempfile
from pathlib import Path

from syft_client.sync.syftbox_manager import SyftboxManager
from syft_client.sync.utils.path_filters import is_excluded_path


def _create_job_dir_with_hidden_files(base: Path) -> Path:
    """Create a fake job directory containing both normal and hidden files."""
    job_dir = base / "my_job"
    job_dir.mkdir(parents=True)

    # Normal files that should be included
    (job_dir / "main.py").write_text("print('hello')")
    (job_dir / "utils.py").write_text("x = 1")

    # Hidden / generated dirs that should be excluded
    venv = job_dir / ".venv" / "lib"
    venv.mkdir(parents=True)
    (venv / "site.py").write_text("# venv")

    git = job_dir / ".git"
    git.mkdir()
    (git / "config").write_text("[core]")

    pycache = job_dir / "__pycache__"
    pycache.mkdir()
    (pycache / "main.cpython-312.pyc").write_bytes(b"\x00")

    return job_dir


def test_read_job_code_skips_hidden_files():
    """_read_job_code should not include files under excluded directories."""
    from syft_bg.notify.handlers.job import _read_job_code
    from unittest.mock import MagicMock

    with tempfile.TemporaryDirectory() as tmp:
        job_dir = _create_job_dir_with_hidden_files(Path(tmp))

        # Build a minimal mock job_client with one job whose code_dir is our temp dir
        mock_job = MagicMock()
        mock_job.name = "my_job"
        mock_job.code_dir = job_dir

        mock_client = MagicMock()
        mock_client.jobs = [mock_job]

        result = _read_job_code(mock_client, "my_job")

        assert result is not None
        assert "main.py" in result
        assert "utils.py" in result

        # None of the hidden/generated files should appear
        for key in result:
            assert not is_excluded_path(key), f"excluded file leaked through: {key}"


def test_push_job_files_skips_hidden_files():
    """push_job_files should not sync files under excluded directories to DO."""
    ds_manager, do_manager = SyftboxManager.pair_with_mock_drive_service_connection()

    with tempfile.TemporaryDirectory() as tmp:
        job_dir = _create_job_dir_with_hidden_files(Path(tmp))

        # Place the job dir inside ds_manager's syftbox folder so relative paths work
        target = (
            Path(ds_manager.syftbox_folder)
            / do_manager.email
            / "app_data"
            / "job"
            / "inbox"
            / ds_manager.email
            / "my.job"
        )
        import shutil

        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(job_dir, target)

        ds_manager.push_job_files(target)
        do_manager.sync()

        # Collect all paths that arrived on the DO side
        event_messages = do_manager._get_all_accepted_events_do()
        arrived_paths = [
            str(e.path_in_datasite) for msg in event_messages for e in msg.events
        ]

        # Normal files should arrive
        assert any("main.py" in p for p in arrived_paths)
        assert any("utils.py" in p for p in arrived_paths)

        # Excluded files should NOT arrive
        for p in arrived_paths:
            assert not is_excluded_path(p), f"excluded file synced to DO: {p}"
