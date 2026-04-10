"""Tests for Wave 6: sync observability — status command sync health."""

import time
from unittest.mock import patch

from click.testing import CliRunner

from syft_bg.cli.commands import status
from syft_bg.common.config import DefaultPaths
from syft_bg.sync.snapshot import SyncSnapshot
from syft_bg.sync.snapshot_writer import SnapshotWriter


def _write_snapshot(path, **kwargs):
    defaults = {"sync_time": time.time(), "sync_count": 5, "sync_duration_ms": 250}
    defaults.update(kwargs)
    SnapshotWriter(path).write(SyncSnapshot(**defaults))


def _make_paths(temp_dir):
    return DefaultPaths(
        config=temp_dir / "config.yaml",
        credentials=temp_dir / "credentials.json",
        gmail_token=temp_dir / "gmail_token.json",
        drive_token=temp_dir / "drive_token.json",
        notify_state=temp_dir / "notify" / "state.json",
        notify_pid=temp_dir / "notify" / "daemon.pid",
        notify_log=temp_dir / "notify" / "daemon.log",
        approve_state=temp_dir / "approve" / "state.json",
        approve_pid=temp_dir / "approve" / "daemon.pid",
        approve_log=temp_dir / "approve" / "daemon.log",
        auto_approvals_dir=temp_dir / "auto_approvals",
        email_approve_state=temp_dir / "email_approve" / "state.json",
        email_approve_pid=temp_dir / "email_approve" / "daemon.pid",
        email_approve_log=temp_dir / "email_approve" / "daemon.log",
        sync_state=temp_dir / "sync" / "state.json",
        sync_pid=temp_dir / "sync" / "daemon.pid",
        sync_log=temp_dir / "sync" / "daemon.log",
        notify_setup_state=temp_dir / "notify" / "setup_state.json",
        approve_setup_state=temp_dir / "approve" / "setup_state.json",
        email_approve_setup_state=temp_dir / "email_approve" / "setup_state.json",
        sync_setup_state=temp_dir / "sync" / "setup_state.json",
    )


class TestSyncHealthInStatus:
    def test_shows_sync_health_when_snapshot_exists(self, temp_dir):
        snapshot_path = temp_dir / "sync" / "state.json"
        _write_snapshot(
            snapshot_path,
            job_names=["job1", "job2"],
            approved_peer_emails=["a@t.com"],
        )
        paths = _make_paths(temp_dir)
        with patch("syft_bg.common.config.get_default_paths", return_value=paths):
            runner = CliRunner()
            result = runner.invoke(status)
        assert "SYNC HEALTH" in result.output
        assert "Sync count:  5" in result.output
        assert "Jobs:        2" in result.output
        assert "Peers:       1" in result.output

    def test_no_sync_health_when_no_snapshot(self, temp_dir):
        paths = _make_paths(temp_dir)
        with patch("syft_bg.common.config.get_default_paths", return_value=paths):
            runner = CliRunner()
            result = runner.invoke(status)
        assert "SYNC HEALTH" not in result.output

    def test_shows_error_when_snapshot_has_error(self, temp_dir):
        snapshot_path = temp_dir / "sync" / "state.json"
        _write_snapshot(snapshot_path, sync_error="Connection timeout")
        paths = _make_paths(temp_dir)
        with patch("syft_bg.common.config.get_default_paths", return_value=paths):
            runner = CliRunner()
            result = runner.invoke(status)
        assert "Connection timeout" in result.output

    def test_shows_stale_warning(self, temp_dir):
        snapshot_path = temp_dir / "sync" / "state.json"
        _write_snapshot(snapshot_path, sync_time=time.time() - 300, sync_count=1)
        paths = _make_paths(temp_dir)
        with patch("syft_bg.common.config.get_default_paths", return_value=paths):
            runner = CliRunner()
            result = runner.invoke(status)
        assert "stale" in result.output.lower()
