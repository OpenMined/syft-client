# Unified Sync Service for syft-bg

## Context

Sync and Drive calls are scattered across 3 independent service processes. Each creates its own `SyftboxManager` and Drive connection. There's no single place for error recovery, retry logic, or observability.

**Goal:** A single `sync` service process that owns all Drive interactions. Other services consume pre-synced state from the local filesystem and a shared snapshot file.

---

## Architecture

```
SYNC SERVICE (sole owner of Drive)
  │
  ├── SyftboxManager.sync()  →  pulls/pushes files from/to Drive
  ├── DriveInboxScanner       →  scans inbox folders and messages
  └── writes sync_state.json  →  snapshot for consumers

CONSUMERS (never touch Drive)
  ├── approve      →  reads jobs from local fs, writes approval markers
  ├── notify       →  reads snapshot + local fs, sends emails
  └── email_approve →  reads jobs from local fs, processes Gmail replies
```

All consumers set `PRE_SYNC=false` so their `SyftboxManager` never calls `sync()`.

---

## New files

All under `packages/syft-bg/src/syft_bg/sync/`.

### `sync/config.py`

```python
class SyncConfig(BaseModel):
    interval: int = 10
    max_retries: int = 3
    retry_backoff: float = 2.0
    do_email: Optional[str] = None
    syftbox_root: Optional[Path] = None
    drive_token_path: Optional[Path] = None
```

### `sync/snapshot.py`

```python
class InboxMessage(BaseModel):
    job_name: str
    submitter: str
    message_id: str

class SyncSnapshot(BaseModel):
    sync_time: float
    sync_count: int = 0
    sync_error: Optional[str] = None
    sync_duration_ms: int = 0

    job_names: list[str] = []
    approved_peer_emails: list[str] = []

    inbox_messages: list[InboxMessage] = []
    drive_peer_emails: list[str] = []
    drive_approved_peers: list[str] = []
```

### `sync/snapshot_writer.py`

```python
class SnapshotWriter:
    def __init__(self, path: Path): ...
    def write(self, snapshot: SyncSnapshot) -> None: ...
```

### `sync/snapshot_reader.py`

```python
class SnapshotReader:
    def __init__(self, path: Path): ...
    def read(self) -> Optional[SyncSnapshot]: ...
    def is_healthy(self, max_age_seconds: int = 60) -> bool: ...
    def wait_for_first_sync(self, timeout: float = 30) -> bool: ...
```

### `sync/drive_inbox_scanner.py`

Extracted from `notify/monitors/job.py` and `notify/monitors/peer.py`.

```python
class DriveInboxScanner:
    def __init__(self, drive_service, do_email: str): ...
    def scan_inbox_messages(self) -> list[InboxMessage]: ...
    def scan_peer_emails(self) -> list[str]: ...
    def scan_approved_peers(self) -> list[str]: ...
```

### `sync/orchestrator.py`

```python
class SyncOrchestrator:
    def __init__(self, client, inbox_scanner, snapshot_writer, config): ...

    @classmethod
    def from_config(cls, config: SyncConfig) -> SyncOrchestrator: ...

    def run(self) -> None: ...
    def run_once(self) -> None: ...
    def stop(self) -> None: ...

    def _sync_and_snapshot(self) -> None: ...
    def _sync_with_retry(self) -> None: ...
```

---

## Files to modify

### `common/config.py`

Add to `DefaultPaths`: `sync_state`, `sync_pid`, `sync_log`.

### `common/syft_bg_config.py`

Add `sync: SyncConfig` field to `SyftBgConfig`.

### `services/registry.py`

Add sync service entry.

### `services/manager.py`

- `start_all()` → start sync first, then consumers
- `stop_all()` → stop consumers first, then sync

### `services/base.py`

Set `PRE_SYNC=false` for consumer services (approve, notify, email_approve).

### `cli/commands.py`

Add `sync` to `--service` choices in the `run` command.

### `notify/monitors/job.py`

- Remove: all Drive query methods
- Add: accept `SnapshotReader`, read `snapshot.inbox_messages`
- Keep: `_check_local_for_status_changes()` unchanged

### `notify/monitors/peer.py`

- Remove: all Drive query methods
- Add: accept `SnapshotReader`, read `snapshot.drive_peer_emails` and `snapshot.drive_approved_peers`

### `notify/orchestrator.py`

- Accept `SnapshotReader` instead of `drive_token_path`
- Pass reader to monitors

---

## How each service works after the change

### Approve service

No code changes. `PRE_SYNC=false` means:

- `self.client.jobs` reads from local filesystem (sync process keeps it fresh)
- `process_approved_jobs()` executes jobs locally, skips post-execution sync
- Sync process pushes results to Drive on next cycle (~10s)

### Notify service

- Reads `SnapshotReader` for inbox messages and peer data (replaces Drive queries)
- Reads local filesystem for job status markers (`approved`, `done` files) — unchanged
- Sends emails via Gmail API — unchanged (Gmail ≠ Drive)

### Email approve service

No code changes. `PRE_SYNC=false` means:

- `self.client.jobs` reads from local filesystem
- `process_approved_jobs()` skips post-sync
- Gmail Pub/Sub monitoring unchanged

---

## Tradeoffs

1. **~10s delay for result delivery** — After job execution, results wait for the sync process's next cycle to push to Drive. DS sees results within ~10s instead of immediately.

2. **Startup ordering** — Sync must run before consumers. If sync crashes, consumers operate on stale data.

3. **Dual SyftboxManager** — Sync process and consumer processes both have `SyftboxManager` on the same filesystem. Sync calls `.sync()`, consumers only read + mutate locally.

---

## Implementation waves (1 commit each)

### Wave 1: Sync module foundation

Create `sync/` with `__init__.py`, `config.py`, `snapshot.py`, `snapshot_writer.py`, `snapshot_reader.py`.
Add `SyncConfig` to `SyftBgConfig`, sync paths to `DefaultPaths`.

#### Outputs

- `src/syft_bg/sync/__init__.py`
- `src/syft_bg/sync/config.py` — `SyncConfig`
- `src/syft_bg/sync/snapshot.py` — `SyncSnapshot`, `InboxMessage`
- `src/syft_bg/sync/snapshot_writer.py` — `SnapshotWriter`
- `src/syft_bg/sync/snapshot_reader.py` — `SnapshotReader`
- Modified: `common/config.py` — sync paths in `DefaultPaths`
- Modified: `common/syft_bg_config.py` — `sync: SyncConfig` in `SyftBgConfig`

#### Class/method structure

**`SyncConfig`** (`sync/config.py`)

```python
class SyncConfig(BaseModel):
    interval: int = 10
    max_retries: int = 3
    retry_backoff: float = 2.0
    do_email: Optional[str] = None
    syftbox_root: Optional[Path] = None
    drive_token_path: Optional[Path] = None
```

- Consumed by: `SyncOrchestrator.from_config()` (Wave 3)
- Loaded from: `SyftBgConfig.sync` field (YAML config)

**`InboxMessage`** (`sync/snapshot.py`)

```python
class InboxMessage(BaseModel):
    job_name: str
    submitter: str
    message_id: str
```

- Produced by: `DriveInboxScanner.scan_inbox_messages()` (Wave 2)
- Consumed by: `notify/monitors/job.py` (Wave 5)

**`SyncSnapshot`** (`sync/snapshot.py`)

```python
class SyncSnapshot(BaseModel):
    sync_time: float
    sync_count: int = 0
    sync_error: Optional[str] = None
    sync_duration_ms: int = 0
    job_names: list[str] = []
    approved_peer_emails: list[str] = []
    inbox_messages: list[InboxMessage] = []
    drive_peer_emails: list[str] = []
    drive_approved_peers: list[str] = []
```

- Produced by: `SyncOrchestrator._sync_and_snapshot()` (Wave 3)
- Written by: `SnapshotWriter.write()` (this wave)
- Read by: `SnapshotReader.read()` (this wave)
- Consumed by: notify monitors (Wave 5)

**`SnapshotWriter`** (`sync/snapshot_writer.py`)

```python
class SnapshotWriter:
    def __init__(self, path: Path):
        self.path = Path(path).expanduser()
        self._lock_file = self.path.with_suffix(".lock")

    def write(self, snapshot: SyncSnapshot) -> None: ...
```

- Same fcntl locking pattern as `JsonStateManager` at `common/state.py:22-44`
- Consumed by: `SyncOrchestrator` (Wave 3)

**`SnapshotReader`** (`sync/snapshot_reader.py`)

```python
class SnapshotReader:
    def __init__(self, path: Path):
        self.path = Path(path).expanduser()

    def read(self) -> Optional[SyncSnapshot]: ...
    def is_healthy(self, max_age_seconds: int = 60) -> bool: ...
    def wait_for_first_sync(self, timeout: float = 30) -> bool: ...
```

- `read()` returns `None` on missing file or parse error
- `is_healthy()` checks `time.time() - snapshot.sync_time < max_age_seconds`
- `wait_for_first_sync()` polls with `time.sleep(0.5)` until `read()` returns non-None
- Consumed by: notify monitors (Wave 5), `ServiceManager.start_all()` (Wave 4)

**`DefaultPaths` changes** (`common/config.py`)

```python
sync_state=creds / "sync" / "state.json",
sync_pid=creds / "sync" / "daemon.pid",
sync_log=creds / "sync" / "daemon.log",
```

**`SyftBgConfig` changes** (`common/syft_bg_config.py`)

```python
sync: SyncConfig = Field(default_factory=SyncConfig)

# In _merge_common_into_services():
if self.sync.do_email is None:
    self.sync.do_email = self.do_email
if self.sync.syftbox_root is None:
    self.sync.syftbox_root = Path(self.syftbox_root) if self.syftbox_root else None
```

#### Tests — `tests/unit/syft_bg/test_sync_foundation.py`

```python
class TestSyncConfig:
    def test_defaults(self):
        config = SyncConfig()
        assert config.interval == 10
        assert config.max_retries == 3
        assert config.do_email is None

    def test_from_dict(self):
        config = SyncConfig.model_validate({"interval": 20, "do_email": "a@b.com"})
        assert config.interval == 20


class TestInboxMessage:
    def test_roundtrip(self):
        msg = InboxMessage(job_name="j1", submitter="ds@test.com", message_id="abc")
        restored = InboxMessage.model_validate(msg.model_dump())
        assert restored.job_name == "j1"


class TestSyncSnapshot:
    def test_defaults(self):
        snap = SyncSnapshot(sync_time=1000.0)
        assert snap.job_names == []
        assert snap.sync_error is None

    def test_roundtrip(self):
        snap = SyncSnapshot(
            sync_time=1000.0, sync_count=5,
            job_names=["j1"],
            inbox_messages=[InboxMessage(job_name="j1", submitter="ds@t.com", message_id="x")],
        )
        restored = SyncSnapshot.model_validate(snap.model_dump())
        assert restored.sync_count == 5
        assert len(restored.inbox_messages) == 1


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


class TestSyftBgConfigSync:
    def test_sync_config_present(self, sample_config):
        config = SyftBgConfig.from_path(sample_config)
        assert isinstance(config.sync, SyncConfig)
        assert config.sync.interval == 10

    def test_sync_inherits_common_fields(self, sample_config):
        config = SyftBgConfig.from_path(sample_config)
        assert config.sync.do_email == config.do_email
```

#### Reviewer checklist

- [ ] `SyncConfig`, `SyncSnapshot`, `InboxMessage` are plain Pydantic models with no logic
- [ ] `SnapshotWriter` uses fcntl file locking (same pattern as `JsonStateManager`)
- [ ] `SnapshotReader.read()` returns `None` on error, never raises
- [ ] `DefaultPaths` has `sync_state`, `sync_pid`, `sync_log` — all under `creds / "sync" /`
- [ ] `SyftBgConfig._merge_common_into_services()` propagates `do_email` and `syftbox_root` to `sync`
- [ ] All tests pass
- [ ] No new dependencies introduced

---

### Wave 2: DriveInboxScanner

Extract inbox scanning from `notify/monitors/job.py` and peer scanning from `notify/monitors/peer.py` into `sync/drive_inbox_scanner.py`.

#### Outputs

- `src/syft_bg/sync/drive_inbox_scanner.py` — `DriveInboxScanner`

#### What it extracts from

- `notify/monitors/job.py:48-157` — `_find_inbox_folders()`, `_get_pending_messages()`, `_parse_job_from_message()`
- `notify/monitors/peer.py:64-129` — `_load_approved_peers_from_drive()`, `_load_peers_from_drive()`

#### Class/method structure

```python
GDRIVE_OUTBOX_INBOX_FOLDER_PREFIX = "syft_outbox_inbox"
GOOGLE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
SYFT_PEERS_FILE = "SYFT_peers.json"


class DriveInboxScanner:
    def __init__(self, drive_service, do_email: str):
        self._drive = drive_service
        self._do_email = do_email

    def scan_inbox_messages(self) -> list[InboxMessage]: ...
    def scan_peer_emails(self) -> list[str]: ...
    def scan_approved_peers(self) -> list[str]: ...

    def _find_inbox_folders(self) -> list[tuple[str, str]]: ...
    def _get_pending_messages(self, folder_id: str) -> list[dict]: ...
    def _parse_job_from_message(self, file_id: str, ds_email: str) -> Optional[InboxMessage]: ...
```

- Consumed by: `SyncOrchestrator._sync_and_snapshot()` (Wave 3)
- Produces: `list[InboxMessage]`, `list[str]`, `list[str]`
- Depends on: Google Drive service object (from `common/drive.create_drive_service()`)

#### Tests — `tests/unit/syft_bg/test_drive_inbox_scanner.py`

```python
class TestDriveInboxScanner:
    def test_scan_inbox_messages_empty(self):
        drive = MagicMock()
        drive.files().list().execute.return_value = {"files": []}
        scanner = DriveInboxScanner(drive, "do@test.com")
        assert scanner.scan_inbox_messages() == []

    def test_scan_peer_emails_empty(self):
        drive = MagicMock()
        drive.files().list().execute.return_value = {"files": []}
        scanner = DriveInboxScanner(drive, "do@test.com")
        assert scanner.scan_peer_emails() == []

    def test_scan_peer_emails_extracts_senders(self):
        drive = MagicMock()
        drive.files().list().execute.return_value = {
            "files": [{"name": "syft_outbox_inbox_ds@test.com_to_do@test.com", "id": "f1"}]
        }
        scanner = DriveInboxScanner(drive, "do@test.com")
        assert "ds@test.com" in scanner.scan_peer_emails()

    def test_scan_approved_peers_empty(self):
        drive = MagicMock()
        drive.files().list().execute.return_value = {"files": []}
        scanner = DriveInboxScanner(drive, "do@test.com")
        assert scanner.scan_approved_peers() == []

    def test_scan_approved_peers_parses_json(self):
        drive = MagicMock()
        drive.files().list().execute.return_value = {"files": [{"id": "f1"}]}
        peers_json = json.dumps({"ds@test.com": {"state": "accepted"}}).encode()
        drive.files().get_media().execute.return_value = peers_json
        scanner = DriveInboxScanner(drive, "do@test.com")
        assert "ds@test.com" in scanner.scan_approved_peers()

    def test_scan_handles_drive_error(self):
        drive = MagicMock()
        drive.files().list().execute.side_effect = Exception("API error")
        scanner = DriveInboxScanner(drive, "do@test.com")
        assert scanner.scan_inbox_messages() == []
        assert scanner.scan_peer_emails() == []
```

#### Reviewer checklist

- [ ] Logic matches existing implementations in `notify/monitors/job.py:67-157` and `notify/monitors/peer.py:64-129`
- [ ] Each public method catches exceptions and returns empty list (never raises)
- [ ] `_parse_job_from_message()` returns `InboxMessage` (not a dict like the original)
- [ ] `scan_peer_emails()` excludes `do_email` from results (same filter as original)
- [ ] No state tracking in scanner — stateless, just reads Drive
- [ ] Drive service is injected, not created internally

---

### Wave 3: SyncOrchestrator

Create `sync/orchestrator.py`. Wire `SyftboxManager.sync()` + `DriveInboxScanner` + `SnapshotWriter` into a loop with retry.

#### Outputs

- `src/syft_bg/sync/orchestrator.py` — `SyncOrchestrator`

#### Class/method structure

```python
class SyncOrchestrator:
    def __init__(
        self,
        client: SyftboxManager,
        inbox_scanner: Optional[DriveInboxScanner],
        snapshot_writer: SnapshotWriter,
        config: SyncConfig,
    ):
        self.client = client
        self.inbox_scanner = inbox_scanner
        self.snapshot_writer = snapshot_writer
        self.config = config
        self._stop_event = threading.Event()

    @classmethod
    def from_config(cls, config: SyncConfig) -> "SyncOrchestrator": ...

    def run(self) -> None: ...
    def run_once(self) -> None: ...
    def stop(self) -> None: ...

    def _sync_and_snapshot(self) -> None: ...
    def _sync_with_retry(self) -> None: ...
    def _build_snapshot(self, start_time: float, sync_error: Optional[str]) -> SyncSnapshot: ...
    def _read_previous_count(self) -> int: ...
```

- `from_config()` follows same `check_env()` → `for_colab()` / `for_jupyter()` pattern as `approve/orchestrator.py:54-85`
- Consumed by: `cli/commands.py` `run()` command (Wave 4)
- Produces: `sync_state.json` on disk every cycle
- Depends on: `SyftboxManager`, `DriveInboxScanner` (Wave 2), `SnapshotWriter` (Wave 1)

#### Tests — `tests/unit/syft_bg/test_sync_orchestrator.py`

```python
class TestSyncOrchestrator:
    def _make_orchestrator(self, temp_dir):
        client = MagicMock()
        client.job_client.jobs = []
        client.peer_manager.approved_peers = []
        scanner = MagicMock()
        scanner.scan_inbox_messages.return_value = []
        scanner.scan_peer_emails.return_value = []
        scanner.scan_approved_peers.return_value = []
        writer = SnapshotWriter(temp_dir / "snapshot.json")
        config = SyncConfig(interval=1, max_retries=2, retry_backoff=0.1)
        return SyncOrchestrator(client, scanner, writer, config), client, scanner

    def test_run_once_writes_snapshot(self, temp_dir):
        orch, client, _ = self._make_orchestrator(temp_dir)
        orch.run_once()
        client.sync.assert_called_once()
        snap = SnapshotReader(temp_dir / "snapshot.json").read()
        assert snap is not None
        assert snap.sync_count == 1

    def test_run_once_captures_jobs(self, temp_dir):
        orch, client, _ = self._make_orchestrator(temp_dir)
        mock_job = MagicMock()
        mock_job.name = "test_job"
        client.job_client.jobs = [mock_job]
        orch.run_once()
        snap = SnapshotReader(temp_dir / "snapshot.json").read()
        assert "test_job" in snap.job_names

    def test_run_once_captures_peers(self, temp_dir):
        orch, client, _ = self._make_orchestrator(temp_dir)
        mock_peer = MagicMock()
        mock_peer.email = "ds@test.com"
        client.peer_manager.approved_peers = [mock_peer]
        orch.run_once()
        snap = SnapshotReader(temp_dir / "snapshot.json").read()
        assert "ds@test.com" in snap.approved_peer_emails

    def test_run_once_captures_inbox(self, temp_dir):
        orch, _, scanner = self._make_orchestrator(temp_dir)
        scanner.scan_inbox_messages.return_value = [
            InboxMessage(job_name="j1", submitter="ds@t.com", message_id="m1")
        ]
        orch.run_once()
        snap = SnapshotReader(temp_dir / "snapshot.json").read()
        assert len(snap.inbox_messages) == 1
        assert snap.inbox_messages[0].job_name == "j1"

    def test_sync_failure_records_error(self, temp_dir):
        orch, client, _ = self._make_orchestrator(temp_dir)
        client.sync.side_effect = Exception("Drive down")
        orch.run_once()
        snap = SnapshotReader(temp_dir / "snapshot.json").read()
        assert "Drive down" in snap.sync_error

    def test_sync_retries_on_failure(self, temp_dir):
        orch, client, _ = self._make_orchestrator(temp_dir)
        client.sync.side_effect = [Exception("fail"), None]
        orch.run_once()
        assert client.sync.call_count == 2
        snap = SnapshotReader(temp_dir / "snapshot.json").read()
        assert snap.sync_error is None

    def test_sync_count_increments(self, temp_dir):
        orch, _, _ = self._make_orchestrator(temp_dir)
        orch.run_once()
        orch.run_once()
        snap = SnapshotReader(temp_dir / "snapshot.json").read()
        assert snap.sync_count == 2

    def test_no_scanner_still_works(self, temp_dir):
        client = MagicMock()
        client.job_client.jobs = []
        client.peer_manager.approved_peers = []
        writer = SnapshotWriter(temp_dir / "snapshot.json")
        config = SyncConfig(interval=1)
        orch = SyncOrchestrator(client, None, writer, config)
        orch.run_once()
        snap = SnapshotReader(temp_dir / "snapshot.json").read()
        assert snap is not None
        assert snap.inbox_messages == []
```

#### Reviewer checklist

- [ ] `run()` has clean shutdown via `_stop_event` + `KeyboardInterrupt`
- [ ] `_sync_with_retry()` re-raises on final attempt, catches otherwise
- [ ] `_build_snapshot()` never raises — wraps scanner calls safely
- [ ] Snapshot always written, even on sync failure (with `sync_error` set)
- [ ] `from_config()` follows same pattern as `approve/orchestrator.py:68-83`
- [ ] `inbox_scanner` is optional (None) for environments without Drive

---

### Wave 4: Register as a service

Add sync to `services/registry.py`, `cli/commands.py`. Update `services/manager.py` for startup ordering.

#### Outputs

- Modified: `services/registry.py` — add `sync` entry
- Modified: `cli/commands.py` — add `sync` to `run` command
- Modified: `services/manager.py` — startup/shutdown ordering

#### Changes

**`services/registry.py`**

```python
"sync": Service(
    name="sync",
    description="Centralized sync and Drive operations",
    pid_file=paths.sync_pid,
    log_file=paths.sync_log,
),
```

**`cli/commands.py`**

```python
@click.option("--service", "-s",
    type=click.Choice(["notify", "approve", "email_approve", "sync"]), ...)

elif service == "sync":
    from syft_bg.sync import SyncOrchestrator
    orchestrator = SyncOrchestrator.from_config(config.sync)
```

**`services/manager.py`**

```python
def start_all(self) -> dict:
    # Start sync first, then consumers
    ...

def stop_all(self) -> dict:
    # Stop consumers first, then sync
    ...
```

#### Tests — `tests/unit/syft_bg/test_sync_service.py`

```python
class TestSyncServiceRegistry:
    def test_sync_in_registry(self):
        from syft_bg.services.registry import SERVICES
        assert "sync" in SERVICES
        assert SERVICES["sync"].name == "sync"


class TestSyncCLI:
    def test_run_sync_once(self):
        runner = CliRunner()
        with patch("syft_bg.sync.SyncOrchestrator.from_config") as mock_orch_cls:
            mock_orch = MagicMock()
            mock_orch_cls.return_value = mock_orch
            runner.invoke(main, ["run", "--service", "sync", "--once"])
            mock_orch.run_once.assert_called_once()


class TestServiceManagerOrdering:
    def test_start_all_starts_sync_first(self):
        manager = ServiceManager()
        with patch.object(manager, "start_service") as mock_start:
            mock_start.return_value = (True, "started")
            manager.start_all()
            calls = [c.args[0] for c in mock_start.call_args_list]
            assert calls[0] == "sync"

    def test_stop_all_stops_sync_last(self):
        manager = ServiceManager()
        with patch.object(manager, "stop_service") as mock_stop:
            mock_stop.return_value = (True, "stopped")
            manager.stop_all()
            calls = [c.args[0] for c in mock_stop.call_args_list]
            assert calls[-1] == "sync"
```

#### Reviewer checklist

- [ ] `sync` appears in service registry with correct pid/log paths
- [ ] CLI `run --service sync` works with both `--once` and blocking mode
- [ ] `start_all()` starts sync first, `stop_all()` stops sync last
- [ ] Existing services still work — no regressions
- [ ] Service status command shows sync service

---

### Wave 5: Wire consumers

Set `PRE_SYNC=false` for consumer services in `services/base.py`. Update notify monitors to use `SnapshotReader`.

#### Outputs

- Modified: `services/base.py` — `PRE_SYNC=false` for consumer services
- Modified: `notify/monitors/job.py` — remove Drive, use `SnapshotReader`
- Modified: `notify/monitors/peer.py` — remove Drive, use `SnapshotReader`
- Modified: `notify/orchestrator.py` — accept `SnapshotReader`

#### Changes

**`services/base.py`**

```python
env = os.environ.copy()
if self.name != "sync":
    env["PRE_SYNC"] = "false"
```

**`notify/monitors/job.py`**

- Accept `snapshot_reader: Optional[SnapshotReader]` in `__init__`
- Replace `_poll_drive_for_new_jobs()` with reading `snapshot.inbox_messages`
- Keep `_check_local_for_status_changes()` unchanged

**`notify/monitors/peer.py`**

- Accept `snapshot_reader: Optional[SnapshotReader]` in `__init__`
- Replace `_load_peers_from_drive()` / `_load_approved_peers_from_drive()` with reading snapshot
- Fall back to Drive queries if snapshot_reader is None (backward compat)

#### Tests — `tests/unit/syft_bg/test_sync_consumers.py`

```python
class TestNotifyJobMonitorWithSnapshot:
    def test_reads_inbox_from_snapshot(self, temp_dir):
        snapshot_path = temp_dir / "snapshot.json"
        SnapshotWriter(snapshot_path).write(SyncSnapshot(
            sync_time=time.time(),
            inbox_messages=[InboxMessage(job_name="j1", submitter="ds@t.com", message_id="m1")],
        ))
        reader = SnapshotReader(snapshot_path)
        handler = MagicMock()
        handler.on_new_job.return_value = True
        state = JsonStateManager(temp_dir / "state.json")
        monitor = JobMonitor(
            syftbox_root=temp_dir, do_email="do@test.com",
            handler=handler, state=state, snapshot_reader=reader,
        )
        monitor._check_all_entities()
        handler.on_new_job.assert_called_once_with("do@test.com", "j1", "ds@t.com")

    def test_skips_already_notified(self, temp_dir):
        snapshot_path = temp_dir / "snapshot.json"
        SnapshotWriter(snapshot_path).write(SyncSnapshot(
            sync_time=time.time(),
            inbox_messages=[InboxMessage(job_name="j1", submitter="ds@t.com", message_id="m1")],
        ))
        state = JsonStateManager(temp_dir / "state.json")
        state.mark_notified("msg_m1", "processed")
        monitor = JobMonitor(
            syftbox_root=temp_dir, do_email="do@test.com",
            handler=MagicMock(), state=state, snapshot_reader=SnapshotReader(snapshot_path),
        )
        monitor._check_all_entities()
        monitor.handler.on_new_job.assert_not_called()

    def test_missing_snapshot_doesnt_crash(self, temp_dir):
        monitor = JobMonitor(
            syftbox_root=temp_dir, do_email="do@test.com",
            handler=MagicMock(), state=JsonStateManager(temp_dir / "state.json"),
            snapshot_reader=SnapshotReader(temp_dir / "missing.json"),
        )
        monitor._check_all_entities()
        monitor.handler.on_new_job.assert_not_called()


class TestPreSyncDisabled:
    def test_consumer_service_sets_pre_sync_false(self):
        from syft_bg.services.registry import SERVICES
        svc = SERVICES["approve"]
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=1234)
            svc.start()
            env = mock_popen.call_args.kwargs.get("env", {})
            assert env.get("PRE_SYNC") == "false"

    def test_sync_service_does_not_set_pre_sync_false(self):
        from syft_bg.services.registry import SERVICES
        svc = SERVICES["sync"]
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=1234)
            svc.start()
            env = mock_popen.call_args.kwargs.get("env", {})
            assert env.get("PRE_SYNC") != "false"
```

#### Reviewer checklist

- [ ] `PRE_SYNC=false` set ONLY for non-sync services in `services/base.py`
- [ ] `notify/monitors/job.py` no longer imports or uses `create_drive_service`
- [ ] `notify/monitors/peer.py` no longer imports or uses `create_drive_service`
- [ ] Snapshot reader is optional — monitors fall back to Drive queries if None (backward compat)
- [ ] `_check_local_for_status_changes()` is completely unchanged
- [ ] State tracking (`was_notified`/`mark_notified`) still uses same keys

---

### Wave 6: Observability

Log sync timing. Add sync health to status output.

#### Outputs

- Modified: `sync/orchestrator.py` — timing logs per cycle
- Modified: `cli/commands.py` — sync health in `status` command

#### Changes

One log line per cycle:

```
[SyncOrchestrator] Cycle 42 completed in 350ms (3 jobs, 2 peers)
[SyncOrchestrator] Cycle 43 failed in 120ms: Drive timeout
```

Status command reads snapshot and shows health/staleness.

#### Tests — `tests/unit/syft_bg/test_sync_observability.py`

```python
class TestSyncLogging:
    def test_run_once_prints_timing(self, temp_dir, capsys):
        orch, _, _ = self._make_orchestrator(temp_dir)
        orch.run_once()
        output = capsys.readouterr().out
        assert "Cycle" in output
        assert "ms" in output

    def test_failure_prints_error(self, temp_dir, capsys):
        orch, client, _ = self._make_orchestrator(temp_dir)
        client.sync.side_effect = Exception("timeout")
        orch.run_once()
        output = capsys.readouterr().out
        assert "failed" in output.lower()
```

#### Reviewer checklist

- [ ] Every sync cycle logs: cycle number, duration, job/peer counts
- [ ] Failures log the error message
- [ ] Status command reads snapshot and shows health
- [ ] No excessive logging — one line per cycle

---

## Dependency graph

```
Wave 1 produces:  SyncConfig, SyncSnapshot, InboxMessage, SnapshotWriter, SnapshotReader
Wave 2 produces:  DriveInboxScanner (uses InboxMessage from W1)
Wave 3 produces:  SyncOrchestrator (uses SnapshotWriter from W1, DriveInboxScanner from W2)
Wave 4 produces:  Service registration (uses SyncOrchestrator from W3)
Wave 5 produces:  Consumer wiring (uses SnapshotReader from W1)
Wave 6 produces:  Logging and status (uses SnapshotReader from W1)
```

Each wave's tests should pass before moving to the next wave.

---

## Verification

1. `syft-bg run --service sync` — syncs every 10s, writes `sync_state.json`
2. `syft-bg run --service approve` — does not call `sync()`
3. `syft-bg run --service notify` — reads from snapshot, no Drive service created
4. `syft-bg start` — starts sync first, then consumers
5. Kill sync → consumers continue with stale data
6. Sync failure → previous snapshot preserved, retries next cycle
