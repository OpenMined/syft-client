from datetime import datetime
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
        process = psutil.Process(pid)
        state = ProcessState(pid=pid, process_create_time=process.create_time())
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
        """Check if process is alive AND valid (PID reuse check via creation time)"""
        pid = self.pid
        if pid is None:
            return False

        state = self.process_state
        if state is None:
            return False

        return self._runner.is_running_matching_create_time(
            pid, state.process_create_time
        )

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

    @property
    def status(self) -> str:
        """Process status (running/stopped/failed)"""
        if not self.is_running():
            return "stopped"

        # Check health if available
        health = self.health
        if health and health.status != "healthy":
            return "unhealthy"

        return "running"

    @property
    def uptime(self) -> str:
        """Human-readable uptime"""
        state = self.process_state
        if not self.is_running() or state is None:
            return "-"

        from syft_process_manager.display.formatting import format_uptime

        delta = datetime.now(state.created_at.tzinfo) - state.created_at
        total_seconds = int(delta.total_seconds())
        return format_uptime(total_seconds)

    def info(self) -> dict:
        """Return process information as a dictionary"""
        return {
            "name": self.name,
            "status": self.status,
            "uptime": self.uptime,
            "pid": self.pid,
            "cmd": self.config.cmd,
            "runner_type": self.config.runner_type,
            "process_dir": str(self.config.process_dir),
        }

    def __repr__(self) -> str:
        """Console representation"""
        info = self.info()
        lines = [f"ProcessHandle: {info['name']}"]

        for key, value in info.items():
            if key == "name":
                continue
            display_value = value if value else "-"
            lines.append(f"  {key}: {display_value}")

        return "\n".join(lines)

    def _repr_html_(self) -> str:
        """Jupyter notebook representation"""
        from syft_process_manager.display.backend_app import ensure_app_is_running
        from syft_process_manager.display.widget import render_process_widget

        # Ensure backend is running and get port
        port = ensure_app_is_running()
        backend_url = f"http://localhost:{port}"

        info = self.info()

        return render_process_widget(
            name=info["name"],
            status=info["status"],
            pid=info["pid"],
            uptime=info["uptime"],
            backend_url=backend_url,
            stdout_path=str(self.config.stdout_path),
            stderr_path=str(self.config.stderr_path),
        )
