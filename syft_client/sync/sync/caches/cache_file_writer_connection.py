from typing import Generic, List, TypeVar
from pydantic import BaseModel, Field
from pathlib import Path
import shutil

T = TypeVar("T")


def _serialize(self, content: T) -> bytes:
    if isinstance(content, bytes):
        return content
    elif isinstance(content, str):
        return content.encode("utf-8")
    elif isinstance(content, BaseModel):
        return content.model_dump_json().encode("utf-8")
    else:
        raise TypeError(f"Unsupported content type: {type(content)}")


def _deserialize(self, data: bytes, content_type: type[T]) -> T:
    if content_type is bytes:
        return data
    elif content_type is str:
        return data.decode("utf-8")
    elif issubclass(content_type, BaseModel):
        return content_type.model_validate_json(data.decode("utf-8"))
    else:
        raise TypeError(f"Unsupported content type: {content_type}")


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

    def clear_cache(self):
        self.sorted_files = KeySortedDict()

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

    def get_all(self) -> List[T]:
        return list(self.sorted_files.values())


class FSFileConnection(CacheFileConnection[T]):
    base_dir: Path

    def clear_cache(self):
        for file_or_folder in self.base_dir.iterdir():
            if file_or_folder.is_file():
                file_or_folder.unlink()
            elif file_or_folder.is_dir():
                shutil.rmtree(file_or_folder)

    def model_post_init(self, context):
        super().model_post_init(context)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_full_path(self, path: str) -> Path:
        # Convert to Path and resolve relative to base_dir
        full_path = (self.base_dir / path).resolve()
        base_dir_resolved = self.base_dir.resolve()

        # Ensure the path is within base_dir (prevent path traversal)
        if not full_path.is_relative_to(base_dir_resolved):
            raise ValueError(
                f"Path {path} is outside of the base directory {self.base_dir}"
            )

        return full_path

    def _iter_files(self) -> List[Path]:
        files = [f for f in self.base_dir.rglob("*") if f.is_file()]
        return sorted(files)

    def write_file(self, path: str, content: T) -> None:
        full_path = self._resolve_full_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        data_bytes = _serialize(self, content)
        with open(full_path, "wb") as f:
            f.write(data_bytes)

    def read_file(self, path: str) -> T:
        full_path = self._resolve_full_path(path)
        dtype = self.get_generic_type()
        with open(full_path, "rb") as f:
            res_bytes = f.read()
        res = _deserialize(self, res_bytes, dtype)
        return res

    def __len__(self) -> int:
        return len(self._iter_files())

    def __getitem__(self, idx: int) -> T:
        if not isinstance(idx, int):
            raise TypeError(f"Key must be an integer, got {type(idx)}")
        files = self._iter_files()
        file_path = files[idx]
        return self.read_file(str(file_path.relative_to(self.base_dir)))

    def get_latest(self) -> T:
        files = self._iter_files()
        latest_file = files[-1]
        return self.read_file(str(latest_file.relative_to(self.base_dir)))

    def get_all(self) -> List[T]:
        files = self._iter_files()
        return [self.read_file(str(f.relative_to(self.base_dir))) for f in files]

    def to_dict(self) -> dict[str, T]:
        files = self._iter_files()
        return {
            str(f.relative_to(self.base_dir)): self.read_file(
                str(f.relative_to(self.base_dir))
            )
            for f in files
        }
