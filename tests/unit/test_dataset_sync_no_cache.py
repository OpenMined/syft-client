import sys
import types
import importlib.util
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict


# ============================================================
# STUB ALL EXTERNAL DEPENDENCIES BEFORE IMPORTING TARGET FILE
# ============================================================

# ---- cache_file_writer_connection ----
mock_cache_module = types.ModuleType(
    "syft_client.sync.sync.caches.cache_file_writer_connection"
)

class FakeCacheFileConnection:
    def __init__(self, *args, **kwargs):
        pass

class FakeInMemoryCacheFileConnection(FakeCacheFileConnection):
    pass

class FakeFSFileConnection(FakeCacheFileConnection):
    pass

mock_cache_module.CacheFileConnection = FakeCacheFileConnection
mock_cache_module.InMemoryCacheFileConnection = FakeInMemoryCacheFileConnection
mock_cache_module.FSFileConnection = FakeFSFileConnection

sys.modules[
    "syft_client.sync.sync.caches.cache_file_writer_connection"
] = mock_cache_module


# ---- base_connection ----
mock_base_connection = types.ModuleType(
    "syft_client.sync.connections.base_connection"
)

class FakeConnectionConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

mock_base_connection.ConnectionConfig = FakeConnectionConfig

sys.modules[
    "syft_client.sync.connections.base_connection"
] = mock_base_connection


# ---- connection_router ----
mock_router = types.ModuleType(
    "syft_client.sync.connections.connection_router"
)

class FakeConnectionRouter:
    @classmethod
    def from_configs(cls, *args, **kwargs):
        return cls()

mock_router.ConnectionRouter = FakeConnectionRouter

sys.modules[
    "syft_client.sync.connections.connection_router"
] = mock_router


# ---- file_change_event ----
mock_events = types.ModuleType(
    "syft_client.sync.events.file_change_event"
)

class FakeFileChangeEvent:
    pass

class FakeFileChangeEventsMessage:
    pass

mock_events.FileChangeEvent = FakeFileChangeEvent
mock_events.FileChangeEventsMessage = FakeFileChangeEventsMessage

sys.modules[
    "syft_client.sync.events.file_change_event"
] = mock_events


# ============================================================
# Helper: load module directly from file path
# ============================================================

def load_module_directly(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore
    return module


# ============================================================
# ACTUAL TEST
# ============================================================

def test_dataset_cache_is_not_used_when_disabled():
    """
    When use_in_memory_cache=False, the watcher cache should NOT
    reuse cached dataset state between syncs.
    """

    module_path = Path(
        "syft_client/sync/sync/caches/datasite_watcher_cache.py"
    ).resolve()

    cache_module = load_module_directly(
        module_path,
        "datasite_watcher_cache",
    )

    DataSiteWatcherCacheConfig = cache_module.DataSiteWatcherCacheConfig
    DataSiteWatcherCache = cache_module.DataSiteWatcherCache

    # Valid non-in-memory config
    config = DataSiteWatcherCacheConfig(
        use_in_memory_cache=False,
        syftbox_folder=Path("/tmp/syftbox"),
        collection_subpath=Path("datasets"),
        connection_configs=[],
    )

    cache = DataSiteWatcherCache.from_config(config)

    peer_email = "peer@test.com"

    # Inject stale cached state manually
    cache._datasets_by_peer = {
        peer_email: ["old_dataset"]
    }

    datasets = cache.get_datasets_for_peer(peer_email)

    # Cache must NOT reuse old in-memory state
    assert datasets != ["old_dataset"]
