from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class KeySortedDict(dict):
    """Dict where the items are sorted by key str, like files on a filesystem (possible)"""

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        # Re-sort after each insertion
        sorted_items = sorted(self.items())
        self.clear()
        self.update(sorted_items)


class CacheFileConnection(BaseModel, Generic[T]):
    class Config:
        arbitrary_types_allowed = True


class InMemoryCacheFileConnection(CacheFileConnection[T]):
    sorted_files: KeySortedDict[str, T] = Field(default_factory=KeySortedDict)

    def write_file(self, path: str, content: T):
        self.sorted_files[path] = content

    def read_file(self, path: str) -> T:
        return self.sorted_files[path]

    def __len__(self) -> int:
        return len(self.sorted_files)

    def __getitem__(self, idx: int) -> T:
        if not isinstance(idx, int):
            raise TypeError(f"Key must be an integer, got {type(idx)}")
        return list(self.sorted_files.values())[idx]

    def get_latest(self) -> T:
        return list(self.sorted_files.values())[-1]
