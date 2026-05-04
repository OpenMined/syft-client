"""Tests for PersistedDict concurrent-write safety.

When two writers share the same on-disk path, the atomic rename in
_save_to_disk must not contend on a shared tmp filename. Otherwise one
writer's rename moves the other's tmp away, causing FileNotFoundError.
"""

import threading
from pathlib import Path

from syft_client.sync.sync.caches.persisted_dict import PersistedDict


def test_concurrent_writes_no_rename_race(tmp_path: Path):
    """Two PersistedDict instances writing to the same path concurrently
    must never raise FileNotFoundError from the atomic rename.
    """
    target = tmp_path / "shared.json"
    a = PersistedDict(path=target)
    b = PersistedDict(path=target)

    errors: list[BaseException] = []
    iterations = 200

    def writer(d: PersistedDict, prefix: str):
        try:
            for i in range(iterations):
                d[f"{prefix}-{i}"] = i
        except BaseException as e:
            errors.append(e)

    t1 = threading.Thread(target=writer, args=(a, "a"))
    t2 = threading.Thread(target=writer, args=(b, "b"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert errors == [], f"Concurrent writes raised: {errors!r}"
    assert target.exists()
    # No leftover tmp files in the target directory.
    leftover = [p.name for p in tmp_path.iterdir() if ".tmp" in p.name]
    assert leftover == [], f"Stale tmp files: {leftover}"
