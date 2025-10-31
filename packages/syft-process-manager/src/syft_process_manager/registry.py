import shutil
from pathlib import Path

from syft_process_manager.models import ProcessConfig


class ProcessRegistry:
    def __init__(self, dir: Path | str):
        self.dir = Path(dir)
        self._setup()

    @property
    def registry_dir(self) -> Path:
        return self.dir / "processes"

    def _setup(self):
        self.dir.mkdir(parents=True, exist_ok=True)

    def get_process_dir(self, name: str) -> Path:
        return self.registry_dir / name

    def get_config_path(self, name: str) -> Path:
        return self.get_process_dir(name) / "config.json"

    def list(self, ignore_validation_errors: bool = True) -> list[ProcessConfig]:
        """List all processes by scanning directories for config.json files."""
        if not self.registry_dir.exists():
            return []
        entries = []
        for process_dir in self.registry_dir.iterdir():
            if not process_dir.is_dir():
                continue
            config_path = process_dir / "config.json"
            if not config_path.exists():
                continue
            try:
                entry = ProcessConfig.load(config_path)
                entries.append(entry)
            except Exception as e:
                if not ignore_validation_errors:
                    raise e
        return entries

    def get_by_name(self, name: str) -> ProcessConfig | None:
        file_path = self.get_process_dir(name) / "config.json"
        if not file_path.is_file():
            return None
        return ProcessConfig.load(file_path)

    def exists(self, name: str) -> bool:
        file_path = self.get_config_path(name)
        return file_path.is_file()

    def save(self, config: ProcessConfig) -> int:
        """Save ProcessConfig to registry. Returns bytes written."""
        self._setup()
        config.process_dir.mkdir(parents=True, exist_ok=True)
        return config.config_path.write_text(config.model_dump_json(indent=2))

    def load(self, path: Path) -> ProcessConfig:
        """Load ProcessConfig from path."""
        return ProcessConfig.load(path)

    def remove(self, name: str, remove_dir: bool = True) -> None:
        """
        Remove ProcessConfig from registry.

        This method will not stop the process; it only removes the config files.
        Removing without stopping the process first may lead to orphaned processes.
        """
        if remove_dir:
            dir = self.get_process_dir(name)
            shutil.rmtree(dir, ignore_errors=True)
        else:
            config_path = self.get_config_path(name)
            if config_path.exists():
                config_path.unlink()
