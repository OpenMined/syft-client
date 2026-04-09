"""Tests for Wave 1: sync module foundation."""

import json
import time
from pathlib import Path


from syft_bg.common.config import get_default_paths
from syft_bg.common.syft_bg_config import SyftBgConfig
from syft_bg.sync.config import SyncConfig
from syft_bg.sync.snapshot import SyncSnapshot
from syft_bg.sync.snapshot_reader import SnapshotReader
from syft_bg.sync.snapshot_writer import SnapshotWriter


class TestSyncConfig:
    def test_defaults(self):
        config = SyncConfig()
        assert config.interval == 10
        assert config.max_retries == 3
        assert config.retry_backoff == 2.0
        assert config.do_email is None

    def test_from_dict(self):
        config = SyncConfig.model_validate({"interval": 20, "do_email": "a@b.com"})
        assert config.interval == 20
        assert config.do_email == "a@b.com"


class TestSyncSnapshot:
    def test_defaults(self):
        snap = SyncSnapshot(sync_time=1000.0)
        assert snap.job_names == []
        assert snap.peer_emails == []
        assert snap.approved_peer_emails == []
        assert snap.sync_error is None
        assert snap.sync_count == 0

    def test_roundtrip(self):
        snap = SyncSnapshot(
            sync_time=1000.0,
            sync_count=5,
            job_names=["j1"],
            peer_emails=["a@b.com", "c@d.com"],
            approved_peer_emails=["a@b.com"],
        )
        restored = SyncSnapshot.model_validate(snap.model_dump())
        assert restored.sync_count == 5
        assert restored.peer_emails == ["a@b.com", "c@d.com"]
        assert restored.approved_peer_emails == ["a@b.com"]


class TestSnapshotWriter:
    def test_write_creates_file(self, temp_dir):
        path = temp_dir / "snapshot.json"
        SnapshotWriter(path).write(SyncSnapshot(sync_time=1000.0, sync_count=1))
        assert path.exists()
        assert json.loads(path.read_text())["sync_count"] == 1

    def test_write_overwrites(self, temp_dir):
        path = temp_dir / "snapshot.json"
        writer = SnapshotWriter(path)
        writer.write(SyncSnapshot(sync_time=1.0, sync_count=1))
        writer.write(SyncSnapshot(sync_time=2.0, sync_count=2))
        assert json.loads(path.read_text())["sync_count"] == 2

    def test_write_creates_parent_dirs(self, temp_dir):
        path = temp_dir / "nested" / "dir" / "snapshot.json"
        SnapshotWriter(path).write(SyncSnapshot(sync_time=1.0))
        assert path.exists()


class TestSnapshotReader:
    def test_read_missing_file(self, temp_dir):
        assert SnapshotReader(temp_dir / "missing.json").read() is None

    def test_read_valid_snapshot(self, temp_dir):
        path = temp_dir / "snapshot.json"
        SnapshotWriter(path).write(SyncSnapshot(sync_time=1000.0, sync_count=3))
        assert SnapshotReader(path).read().sync_count == 3

    def test_read_corrupt_file(self, temp_dir):
        path = temp_dir / "snapshot.json"
        path.write_text("not json")
        assert SnapshotReader(path).read() is None

    def test_is_healthy_fresh(self, temp_dir):
        path = temp_dir / "snapshot.json"
        SnapshotWriter(path).write(SyncSnapshot(sync_time=time.time(), sync_count=1))
        assert SnapshotReader(path).is_healthy(max_age_seconds=60)

    def test_is_healthy_stale(self, temp_dir):
        path = temp_dir / "snapshot.json"
        SnapshotWriter(path).write(SyncSnapshot(sync_time=1.0, sync_count=1))
        assert not SnapshotReader(path).is_healthy(max_age_seconds=60)

    def test_is_healthy_missing(self, temp_dir):
        assert not SnapshotReader(temp_dir / "nope.json").is_healthy()


class TestDefaultPathsSync:
    def test_sync_paths_exist(self):
        paths = get_default_paths()
        assert isinstance(paths.sync_state, Path)
        assert isinstance(paths.sync_pid, Path)
        assert isinstance(paths.sync_log, Path)
        assert "sync" in str(paths.sync_state)
        assert "sync" in str(paths.sync_pid)
        assert "sync" in str(paths.sync_log)


class TestSyftBgConfigSync:
    def test_sync_config_present(self, sample_config):
        config = SyftBgConfig.from_path(sample_config)
        assert isinstance(config.sync, SyncConfig)
        assert config.sync.interval == 10

    def test_sync_inherits_common_fields(self, sample_config):
        config = SyftBgConfig.from_path(sample_config)
        assert config.sync.do_email == config.do_email
        assert config.sync.do_email == "test@example.com"

    def test_sync_inherits_syftbox_root(self, sample_config):
        config = SyftBgConfig.from_path(sample_config)
        assert config.sync.syftbox_root == Path(config.syftbox_root)
