from pathlib import Path

from syft_process_manager.constants import DEFAULT_PROCESS_MANAGER_DIR
from syft_process_manager.handle import ProcessHandle
from syft_process_manager.models import ProcessConfig
from syft_process_manager.registry import ProcessRegistry


class ProcessManager:
    def __init__(
        self,
        dir: Path | str = DEFAULT_PROCESS_MANAGER_DIR,
    ):
        self.registry = ProcessRegistry(dir=dir)

    def create_handle(
        self,
        name: str,
        cmd: list[str],
        env: dict[str, str] | None = None,
        ttl_seconds: int | None = None,
        log_level: str = "INFO",
        runner_type: str = "subprocess",
        overwrite: bool = False,
    ) -> ProcessHandle:
        if self.registry.exists(name):
            if overwrite:
                self._terminate_and_remove(name)
            else:
                raise ValueError(f"Process with name '{name}' already exists.")

        process_dir = self.registry.get_process_dir(name)
        process_config = ProcessConfig(
            name=name,
            cmd=cmd,
            env=env if env is not None else {},
            process_dir=process_dir,
            runner_type=runner_type,
            ttl_seconds=ttl_seconds,
            log_level=log_level,
        )
        self.registry.save(process_config)
        return ProcessHandle.from_config(process_config)

    def create_and_run(
        self,
        name: str,
        cmd: list[str],
        env: dict[str, str] | None = None,
        runner_type: str = "subprocess",
        overwrite: bool = False,
    ) -> ProcessHandle:
        handle = self.create_handle(
            name=name,
            cmd=cmd,
            env=env,
            runner_type=runner_type,
            overwrite=overwrite,
        )
        handle.start()
        return handle

    def get_all(self) -> list[ProcessHandle]:
        handles = []
        for process_config in self.registry.list(ignore_validation_errors=True):
            handle = ProcessHandle.from_config(process_config)
            handles.append(handle)
        return handles

    def get(self, name: str) -> ProcessHandle | None:
        if not self.registry.exists(name):
            return None
        process_config = self.registry.get_by_name(name)
        if process_config is None:
            return None
        return ProcessHandle.from_config(process_config)

    def exists(self, name: str) -> bool:
        return self.registry.exists(name)

    def is_running(self, name: str) -> bool:
        """Check if process with given name is running"""
        handle = self.get(name)
        if handle is None:
            return False
        return handle.is_running()

    def refresh_all(self) -> None:
        """Refresh registry state to reflect state of running processes"""
        for handle in self.get_all():
            handle.refresh()

    def _terminate_and_remove(self, process: str | ProcessHandle) -> None:
        if isinstance(process, str):
            handle = self.get(process)
            if handle is None:
                return
        else:
            handle = process

        handle.terminate()
        self.registry.remove(handle.name, remove_dir=True)

    def terminate_all(self) -> None:
        """Terminate all managed processes"""
        for handle in self.get_all():
            handle.terminate()

    def remove_all(self) -> None:
        """Remove all managed processes from registry (after terminating them)"""
        for handle in self.get_all():
            self._terminate_and_remove(handle)
