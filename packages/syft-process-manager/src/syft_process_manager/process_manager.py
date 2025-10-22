from typing import Self

from syft_process_manager.config import ProcessManagerConfig
from syft_process_manager.handle import ProcessHandle
from syft_process_manager.models import ProcessInfo
from syft_process_manager.registry import ProcessRegistry


class ProcessManager:
    def __init__(self, registry: ProcessRegistry):
        self.registry = registry

    def init_handle(
        self,
        name: str,
        cmd: list[str],
        runner_type: str = "subprocess",
    ) -> ProcessHandle:
        pidfile_path = self.registry.get_process_info_path(name)
        process_dir = self.registry.get_unique_process_dir(name)

        process_info = ProcessInfo(
            name=name,
            pid=-1,
            cmd=cmd,
            info_path=pidfile_path,
            process_dir=process_dir,
            runner_type=runner_type,
        )
        if self.registry.exists(name):
            raise RuntimeError(f"Process with name '{name}' already exists.")

        return ProcessHandle.from_info(process_info)

    def run(
        self,
        name: str,
        cmd: list[str],
        runner_type: str = "subprocess",
    ) -> ProcessHandle:
        handle = self.init_handle(name=name, cmd=cmd, runner_type=runner_type)
        handle.start()
        return handle

    def is_running(self, name: str) -> bool:
        """Check if process with given name is running"""
        info = self.registry.get_by_name(name)
        if info is None:
            return False
        handle = ProcessHandle.from_info(info)
        return handle.is_running_and_valid()

    def refresh_all(self) -> None:
        """Refresh registry state to reflect state of running processes"""
        for info in self.registry.list(ignore_validation_errors=True):
            handle = ProcessHandle.from_info(info)
            handle.refresh()

    @classmethod
    def from_config(cls, config: ProcessManagerConfig) -> Self:
        registry = ProcessRegistry(dir=config.base_dir)
        return cls(registry=registry)
