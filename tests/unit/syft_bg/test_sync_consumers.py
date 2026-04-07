"""Tests for Wave 5: consumer services wired to sync snapshots."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from syft_bg.common.state import JsonStateManager
from syft_bg.notify.monitors.job import JobMonitor
from syft_bg.notify.monitors.peer import PeerMonitor
from syft_bg.sync.snapshot import InboxMessage, SyncSnapshot
from syft_bg.sync.snapshot_reader import SnapshotReader
from syft_bg.sync.snapshot_writer import SnapshotWriter


def _write_snapshot(path: Path, **kwargs) -> None:
    defaults = {"sync_time": time.time(), "sync_count": 1}
    defaults.update(kwargs)
    SnapshotWriter(path).write(SyncSnapshot(**defaults))


class TestJobMonitorWithSnapshot:
    def test_reads_inbox_from_snapshot(self, temp_dir):
        snapshot_path = temp_dir / "snapshot.json"
        _write_snapshot(
            snapshot_path,
            inbox_messages=[
                InboxMessage(job_name="j1", submitter="ds@t.com", message_id="m1")
            ],
        )
        reader = SnapshotReader(snapshot_path)
        handler = MagicMock()
        handler.on_new_job.return_value = True
        state = JsonStateManager(temp_dir / "state.json")

        monitor = JobMonitor(
            syftbox_root=temp_dir,
            do_email="do@test.com",
            handler=handler,
            state=state,
            snapshot_reader=reader,
        )
        monitor._check_all_entities()
        handler.on_new_job.assert_called_once_with("do@test.com", "j1", "ds@t.com")

    def test_skips_already_notified(self, temp_dir):
        snapshot_path = temp_dir / "snapshot.json"
        _write_snapshot(
            snapshot_path,
            inbox_messages=[
                InboxMessage(job_name="j1", submitter="ds@t.com", message_id="m1")
            ],
        )
        reader = SnapshotReader(snapshot_path)
        handler = MagicMock()
        state = JsonStateManager(temp_dir / "state.json")
        state.mark_notified("msg_m1", "processed")

        monitor = JobMonitor(
            syftbox_root=temp_dir,
            do_email="do@test.com",
            handler=handler,
            state=state,
            snapshot_reader=reader,
        )
        monitor._check_all_entities()
        handler.on_new_job.assert_not_called()

    def test_missing_snapshot_doesnt_crash(self, temp_dir):
        reader = SnapshotReader(temp_dir / "missing.json")
        handler = MagicMock()
        state = JsonStateManager(temp_dir / "state.json")

        monitor = JobMonitor(
            syftbox_root=temp_dir,
            do_email="do@test.com",
            handler=handler,
            state=state,
            snapshot_reader=reader,
        )
        monitor._check_all_entities()
        handler.on_new_job.assert_not_called()

    def test_snapshot_skips_drive_init(self, temp_dir):
        reader = SnapshotReader(temp_dir / "snapshot.json")
        handler = MagicMock()
        state = JsonStateManager(temp_dir / "state.json")

        monitor = JobMonitor(
            syftbox_root=temp_dir,
            do_email="do@test.com",
            handler=handler,
            state=state,
            snapshot_reader=reader,
        )
        assert monitor._drive_service is None


class TestPeerMonitorWithSnapshot:
    def test_reads_peers_from_snapshot(self, temp_dir):
        snapshot_path = temp_dir / "snapshot.json"
        _write_snapshot(snapshot_path, drive_peer_emails=["ds@test.com"])
        reader = SnapshotReader(snapshot_path)
        handler = MagicMock()
        handler.on_new_peer_request_to_do.return_value = True
        handler.on_peer_request_sent.return_value = True
        state = JsonStateManager(temp_dir / "state.json")

        monitor = PeerMonitor(
            do_email="do@test.com",
            drive_token_path=None,
            handler=handler,
            state=state,
            snapshot_reader=reader,
        )
        monitor._check_all_entities()
        handler.on_new_peer_request_to_do.assert_called_once_with(
            "do@test.com", "ds@test.com"
        )

    def test_reads_approved_peers_from_snapshot(self, temp_dir):
        snapshot_path = temp_dir / "snapshot.json"
        _write_snapshot(snapshot_path, drive_approved_peers=["ds@test.com"])
        reader = SnapshotReader(snapshot_path)
        handler = MagicMock()
        handler.on_peer_granted.return_value = True
        state = JsonStateManager(temp_dir / "state.json")

        monitor = PeerMonitor(
            do_email="do@test.com",
            drive_token_path=None,
            handler=handler,
            state=state,
            snapshot_reader=reader,
        )
        monitor._check_all_entities()
        handler.on_peer_granted.assert_called_once_with("ds@test.com", "do@test.com")

    def test_missing_snapshot_returns_empty_peers(self, temp_dir):
        reader = SnapshotReader(temp_dir / "missing.json")
        handler = MagicMock()
        state = JsonStateManager(temp_dir / "state.json")

        monitor = PeerMonitor(
            do_email="do@test.com",
            drive_token_path=None,
            handler=handler,
            state=state,
            snapshot_reader=reader,
        )
        monitor._check_all_entities()
        handler.on_new_peer_request_to_do.assert_not_called()
        handler.on_peer_granted.assert_not_called()

    def test_snapshot_skips_drive_init(self, temp_dir):
        reader = SnapshotReader(temp_dir / "snapshot.json")
        handler = MagicMock()
        state = JsonStateManager(temp_dir / "state.json")

        monitor = PeerMonitor(
            do_email="do@test.com",
            drive_token_path=None,
            handler=handler,
            state=state,
            snapshot_reader=reader,
        )
        assert monitor._drive_service is None


class TestJobMonitorLocalStatusChanges:
    """Tests for _check_local_for_status_changes with inbox/review directory structure."""

    def _setup_job(self, temp_dir, ds_email="ds@t.com", job_name="test_job"):
        """Create a job in the inbox/<ds_email>/<job_name>/ structure."""
        do_email = "do@test.com"
        job_dir = temp_dir / do_email / "app_data" / "job"

        # Create inbox job directory with config
        inbox_job = job_dir / "inbox" / ds_email / job_name
        inbox_job.mkdir(parents=True)
        config = inbox_job / "config.yaml"
        config.write_text(f"name: {job_name}\ntype: python\n")

        return job_dir, inbox_job

    def _setup_review_state(self, temp_dir, ds_email, job_name, state_data):
        """Create a review state.yaml for a job."""
        do_email = "do@test.com"
        review_dir = (
            temp_dir / do_email / "app_data" / "job" / "review" / ds_email / job_name
        )
        review_dir.mkdir(parents=True, exist_ok=True)
        import yaml

        (review_dir / "state.yaml").write_text(yaml.dump(state_data))

    def test_detects_new_job(self, temp_dir):
        self._setup_job(temp_dir)
        handler = MagicMock()
        handler.on_new_job.return_value = True
        state = JsonStateManager(temp_dir / "state.json")
        state.mark_notified("_dummy", "x")  # non-empty state → not fresh

        monitor = JobMonitor(
            syftbox_root=temp_dir,
            do_email="do@test.com",
            handler=handler,
            state=state,
        )
        monitor._check_local_for_status_changes()
        handler.on_new_job.assert_called_once_with(
            "do@test.com", "test_job", "ds@t.com"
        )

    def test_detects_approved_status(self, temp_dir):
        self._setup_job(temp_dir)
        self._setup_review_state(
            temp_dir, "ds@t.com", "test_job", {"approved_at": "2026-01-01T00:00:00Z"}
        )
        handler = MagicMock()
        handler.on_new_job.return_value = True
        handler.on_job_approved.return_value = True
        state = JsonStateManager(temp_dir / "state.json")
        state.mark_notified("_dummy", "x")

        monitor = JobMonitor(
            syftbox_root=temp_dir,
            do_email="do@test.com",
            handler=handler,
            state=state,
        )
        monitor._check_local_for_status_changes()
        handler.on_job_approved.assert_called_once_with("ds@t.com", "test_job")

    def test_detects_executed_status(self, temp_dir):
        self._setup_job(temp_dir)
        self._setup_review_state(
            temp_dir,
            "ds@t.com",
            "test_job",
            {
                "approved_at": "2026-01-01T00:00:00Z",
                "completed_at": "2026-01-01T00:01:00Z",
            },
        )
        handler = MagicMock()
        handler.on_new_job.return_value = True
        handler.on_job_approved.return_value = True
        handler.on_job_executed.return_value = True
        state = JsonStateManager(temp_dir / "state.json")
        state.mark_notified("_dummy", "x")

        monitor = JobMonitor(
            syftbox_root=temp_dir,
            do_email="do@test.com",
            handler=handler,
            state=state,
        )
        monitor._check_local_for_status_changes()
        handler.on_job_executed.assert_called_once_with("ds@t.com", "test_job")

    def test_skips_old_jobs_on_fresh_state(self, temp_dir):
        self._setup_job(temp_dir)
        handler = MagicMock()
        state = JsonStateManager(temp_dir / "state.json")  # empty = fresh

        monitor = JobMonitor(
            syftbox_root=temp_dir,
            do_email="do@test.com",
            handler=handler,
            state=state,
        )
        monitor._check_local_for_status_changes()
        handler.on_new_job.assert_not_called()

    def test_no_inbox_dir_doesnt_crash(self, temp_dir):
        handler = MagicMock()
        state = JsonStateManager(temp_dir / "state.json")

        monitor = JobMonitor(
            syftbox_root=temp_dir,
            do_email="do@test.com",
            handler=handler,
            state=state,
        )
        monitor._check_local_for_status_changes()  # should not raise
        handler.on_new_job.assert_not_called()


class TestPreSyncEnvVar:
    def _start_service(self, name: str, mock_popen):
        from syft_bg.services.base import Service

        svc = Service(
            name=name,
            description="test",
            pid_file=Path("/tmp/test.pid"),
            log_file=Path("/tmp/test.log"),
        )
        mock_popen.return_value = MagicMock(pid=1234)
        svc.start()
        return mock_popen.call_args.kwargs.get("env", {})

    def test_consumer_service_sets_pre_sync_false(self):
        with (
            patch.dict("os.environ", {"PATH": "/usr/bin"}, clear=True),
            patch("subprocess.Popen") as mock_popen,
        ):
            env = self._start_service("notify", mock_popen)
            assert env.get("PRE_SYNC") == "false"

    def test_sync_service_does_not_set_pre_sync_false(self):
        with (
            patch.dict("os.environ", {"PATH": "/usr/bin"}, clear=True),
            patch("subprocess.Popen") as mock_popen,
        ):
            env = self._start_service("sync", mock_popen)
            assert env.get("PRE_SYNC") != "false"
