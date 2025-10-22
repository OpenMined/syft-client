from pathlib import Path
from typing import Self

import psutil

from syft_process_manager.log_stream import LogStream
from syft_process_manager.models import (
    ProcessConfig,
    ProcessHealth,
    ProcessState,
)
from syft_process_manager.runners import ProcessRunner, get_runner


class ProcessHandle:
    """
    Layout:
    {process_dir}/
        config.json # static config (name, cmd, env, runner_type, ...)
        process_state.json # runtime state of current process (pid, created_at, ...), managed by syft-process-manager
        health.json # optional health check info, managed by the process itself
        stdout.log
        stderr.log
    """

    def __init__(
        self,
        config: ProcessConfig,
        runner: ProcessRunner,
    ):
        # Config holds static config, re-used across restarts
        # process_state holds process-specific state (pid, created_at, ...)
        self.config = config
        self._runner = runner

    @classmethod
    def from_config(
        cls,
        config: ProcessConfig,
    ) -> Self:
        runner = get_runner(config.runner_type)
        return cls(config=config, runner=runner)

    @classmethod
    def from_dir(
        cls,
        process_dir: Path,
    ) -> Self:
        config = ProcessConfig.load(process_dir)
        return ProcessHandle.from_config(config=config)

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def process_state(self) -> ProcessState | None:
        if not self.config.process_state_path.exists():
            return None
        return ProcessState.load(self.config.process_state_path)

    def _save_process_state(self, pid: int) -> None:
        state = ProcessState(pid=pid)
        self.config.process_state_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.process_state_path.write_text(state.model_dump_json(indent=2))

    def _remove_process_state(self) -> None:
        if self.config.process_state_path.exists():
            self.config.process_state_path.unlink()

    @property
    def pid(self) -> int | None:
        state = self.process_state
        if state is None:
            return None
        return state.pid

    def is_running(self) -> bool:
        """Check if process is alive AND valid (PID reuse check via env var)"""
        pid = self.pid
        if pid is None:
            return False

        try:
            process = psutil.Process(pid)
            # Check if process is running
            if not process.is_running():
                return False
            # Verify env var matches (detect PID reuse)
            env = process.environ()
            return env.get("SYFTPM_PROCESS_NAME") == self.config.name
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
        except Exception:
            return False

    def _get_default_env(self) -> dict[str, str]:
        return {
            "SYFTPM_PROCESS_NAME": self.config.name,
            "SYFTPM_PROCESS_DIR": str(self.config.process_dir),
        }

    def start(self) -> None:
        self.refresh()
        if self.pid is not None:
            raise RuntimeError(
                f"Process {self.name} is already running with PID {self.pid}"
            )

        env = self._get_default_env()
        if self.config.env:
            env = {**env, **self.config.env}
        new_pid = self._runner.start(
            cmd=self.config.cmd,
            stdout_path=self.config.stdout_path,
            stderr_path=self.config.stderr_path,
            env=env,
        )

        self._save_process_state(new_pid)

    def terminate(self) -> None:
        if self.pid is None:
            return
        self._runner.terminate(self.pid)
        self._remove_process_state()

    def refresh(self) -> None:
        if not self.is_running():
            self._remove_process_state()

    @property
    def stdout(self) -> LogStream:
        return LogStream(self.config.stdout_path)

    @property
    def stderr(self) -> LogStream:
        return LogStream(self.config.stderr_path)

    @property
    def health(self) -> ProcessHealth | None:
        if not self.config.health_path.exists():
            return None
        content = self.config.health_path.read_text()
        return ProcessHealth.model_validate_json(content)
