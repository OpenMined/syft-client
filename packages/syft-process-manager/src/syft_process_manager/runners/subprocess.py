import os
import signal
import subprocess
import time
from pathlib import Path

from syft_process_manager.runners.base import ProcessRunner


class SubprocessRunner(ProcessRunner):
    def start(
        self,
        cmd: list[str],
        stdout_path: Path,
        stderr_path: Path,
        env: dict[str, str] | None = None,
        copy_env: bool = True,
    ) -> int:
        """Start detached process with stdout/stderr redirected to files"""
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)

        if env is None:
            env = {}
        if copy_env:
            env = {**os.environ, **env}

        with (
            open(stdout_path, "w") as stdout_file,
            open(stderr_path, "w") as stderr_file,
        ):
            process = subprocess.Popen(
                cmd,
                stdout=stdout_file,
                stderr=stderr_file,
                start_new_session=True,  # Detach from parent
                env=env,
            )
        return process.pid

    def is_running(self, pid: int) -> bool:
        """Check if PID is alive"""
        if pid <= 0:  # Invalid PID
            return False
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def terminate(self, pid: int, wait_time: float = 5.0) -> None:
        """Terminate process (SIGTERM then SIGKILL if needed)"""
        if not self.is_running(pid):
            return

        try:
            # Get process group ID for cleanup
            pgid = os.getpgid(pid)

            # Try SIGTERM first
            os.killpg(pgid, signal.SIGTERM)

            # Wait for graceful shutdown
            for _ in range(wait_time * 10):
                time.sleep(0.1)
                if not self.is_running(pid):
                    return

            # Force kill if still alive
            os.killpg(pgid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
