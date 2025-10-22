from abc import ABC, abstractmethod
from pathlib import Path


class ProcessRunner(ABC):
    @abstractmethod
    def start(
        self,
        cmd: list[str],
        stdout_path: Path,
        stderr_path: Path,
        env: dict[str, str] | None = None,
        copy_env: bool = True,
    ) -> int:
        pass

    @abstractmethod
    def is_running(self, pid: int) -> bool:
        pass

    @abstractmethod
    def is_running_matching_create_time(
        self, pid: int, process_create_time: float
    ) -> bool:
        """Check if process is running AND matches the expected creation time (PID reuse detection)"""
        pass

    @abstractmethod
    def terminate(self, pid: int) -> None:
        pass
