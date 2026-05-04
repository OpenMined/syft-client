"""A dict subclass that transparently persists to a JSON file.

Reads always reload from disk (sees other process's writes). Writes always
save to disk immediately. Designed for cross-process consistency when paired
with the sync file lock.

Usage:
    file_hashes = PersistedDict(
        path=syftbox_folder / ".cache" / "owner_file_hashes.json",
        key_serializer=str,           # convert keys to JSON-safe form
        key_deserializer=Path,        # convert back on load
    )
    file_hashes["foo.txt"] = "hash"   # auto-saved
    file_hashes.get("foo.txt")        # reads latest from disk
"""

import json
import os
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4


class PersistedDict(dict):
    """Dict that persists to a JSON file. With path=None it's a plain in-memory dict."""

    def __init__(
        self,
        path: Path | None = None,
        key_serializer: Callable[[Any], str] = str,
        key_deserializer: Callable[[str], Any] = lambda s: s,
    ):
        super().__init__()
        self._path = path
        self._key_serializer = key_serializer
        self._key_deserializer = key_deserializer
        # Load existing state on construction (no-op if path is None)
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        if self._path is None:
            return  # in-memory mode
        super().clear()
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            for k, v in data.items():
                super().__setitem__(self._key_deserializer(k), v)
        except (json.JSONDecodeError, OSError):
            pass

    def _save_to_disk(self) -> None:
        if self._path is None:
            return  # in-memory mode
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Per-process unique tmp path: two writers must never share a tmp file,
        # otherwise one process's rename moves the other's tmp away mid-flight.
        tmp = self._path.with_suffix(f".tmp.{os.getpid()}.{uuid4().hex}")
        serialized = {self._key_serializer(k): v for k, v in super().items()}
        try:
            tmp.write_text(json.dumps(serialized))
            tmp.replace(self._path)
        finally:
            tmp.unlink(missing_ok=True)

    # --- read overrides: reload from disk before returning ---

    def __getitem__(self, key):
        self._load_from_disk()
        return super().__getitem__(key)

    def __contains__(self, key):
        self._load_from_disk()
        return super().__contains__(key)

    def __iter__(self):
        self._load_from_disk()
        return super().__iter__()

    def __len__(self):
        self._load_from_disk()
        return super().__len__()

    def get(self, key, default=None):
        self._load_from_disk()
        return super().get(key, default)

    def keys(self):
        self._load_from_disk()
        return super().keys()

    def values(self):
        self._load_from_disk()
        return super().values()

    def items(self):
        self._load_from_disk()
        return super().items()

    # --- write overrides: load, mutate, save ---

    def __setitem__(self, key, value):
        self._load_from_disk()
        super().__setitem__(key, value)
        self._save_to_disk()

    def __delitem__(self, key):
        self._load_from_disk()
        super().__delitem__(key)
        self._save_to_disk()

    def pop(self, key, *args):
        self._load_from_disk()
        result = super().pop(key, *args)
        self._save_to_disk()
        return result

    def update(self, *args, **kwargs):
        self._load_from_disk()
        super().update(*args, **kwargs)
        self._save_to_disk()

    def clear(self):
        super().clear()
        self._save_to_disk()
