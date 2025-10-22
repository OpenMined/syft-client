import secrets
from pathlib import Path

from syft_process_manager.models import ProcessInfo


class ProcessRegistry:
    def __init__(self, dir: Path):
        self.dir = dir

    def get_process_info_path(self, name: str) -> Path:
        return self.dir / "registry" / f"{name}.json"

    def get_unique_process_dir(self, name: str) -> Path:
        return self.dir / "processes" / f"{name}_{secrets.token_hex(4)}"

    def _setup(self):
        self.dir.mkdir(parents=True, exist_ok=True)

    def list(self, ignore_validation_errors: bool = True) -> list[ProcessInfo]:
        registry_dir = self.dir / "registry"
        if not registry_dir.exists():
            return []
        entries = []
        for file_path in registry_dir.glob("*.json"):
            try:
                entry = ProcessInfo.load(file_path)
                entries.append(entry)
            except Exception as e:
                if not ignore_validation_errors:
                    raise e
        return entries

    def get_by_name(self, name: str) -> ProcessInfo | None:
        file_path = self.get_process_info_path(name)
        if not file_path.is_file():
            return None
        return ProcessInfo.load(file_path)

    def exists(self, name: str) -> bool:
        file_path = self.get_process_info_path(name)
        return file_path.is_file()
