import json
from typing import Self

import psutil

from syft_process_manager.log_stream import LogStream
from syft_process_manager.models import ProcessInfo
from syft_process_manager.runners import ProcessRunner, get_runner
from syft_process_manager.utils import _utcnow


class ProcessHandle:
    def __init__(
        self,
        info: ProcessInfo,
        runner: ProcessRunner,
    ):
        self.info = info
        self._runner = runner

    @classmethod
    def from_info(
        cls,
        info: ProcessInfo,
    ) -> Self:
        runner = get_runner(info.runner_type)
        return cls(info=info, runner=runner)

    @property
    def name(self) -> str:
        return self.info.name

    def start(self, env: dict[str, str] | None = None) -> None:
        if self._runner.is_running(self.info.pid):
            raise RuntimeError(
                f"Process {self.info.name} (pid={self.info.pid}) is already running."
            )

        new_pid = self._runner.start(
            cmd=self.info.cmd,
            stdout_path=self.info.stdout_path,
            stderr_path=self.info.stderr_path,
            env=env,
        )
        self.info.pid = new_pid
        self.info.created_at = _utcnow()
        self.info.save()

    def terminate(self) -> None:
        self._runner.terminate(self.info.pid)
        self.info.pid = -1

    def refresh(self) -> None:
        if not self.is_running_and_valid():
            self.info.pid = -1
            self.info.info_path.unlink(missing_ok=True)

    def is_running(self) -> bool:
        """Check if process is alive (doesn't verify it's the right process)"""
        return self._runner.is_running(self.info.pid)

    def is_running_and_valid(self) -> bool:
        """Check if process is alive AND hasn't been replaced (PID reuse check)"""
        if not self.is_running():
            return False

        # Verify cmdline matches (detect PID reuse)
        try:
            cmdline = self._read_cmdline()
            return self._cmdline_matches(cmdline, self.info.cmd)
        except Exception:
            return False

    def _read_cmdline(self) -> list[str]:
        """Read process cmdline using psutil (cross-platform)"""
        try:
            process = psutil.Process(self.info.pid)
            return process.cmdline()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return []
        except Exception:
            return []

    def _cmdline_matches(self, actual: list[str], expected: list[str]) -> bool:
        """Compare cmdlines - check if expected command matches actual"""
        if not actual or not expected:
            return False
        # Simple approach: check if expected is prefix of actual or exact match
        # Handle cases where actual may have additional args
        if len(expected) > len(actual):
            return False
        return actual[: len(expected)] == expected

    @property
    def stdout(self) -> LogStream:
        return LogStream(self.info.stdout_path)

    @property
    def stderr(self) -> LogStream:
        return LogStream(self.info.stderr_path)

    @oroperty
    def health(self) -> dict | None:
        if not self.info.health_path.exists():
            return None
        content = self.info.health_path.read_text()
        return json.loads(content)
