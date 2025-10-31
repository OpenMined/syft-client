import os
import subprocess
from pathlib import Path

import psutil

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

        stdout_stream = open(stdout_path, "a")
        stderr_stream = open(stderr_path, "a")
        process = subprocess.Popen(
            cmd,
            stdout=stdout_stream,
            stderr=stderr_stream,
            start_new_session=True,  # Detach from parent
            env=env,
        )
        stdout_stream.close()
        stderr_stream.close()
        return process.pid

    def is_running(self, pid: int) -> bool:
        """Check if PID is alive"""
        if pid is None or pid <= 0:
            return False
        try:
            proc = psutil.Process(pid)
            # Ignore zombie processes, they are reaped later
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False

    def is_running_matching_create_time(
        self,
        pid: int,
        process_create_time: float,
    ) -> bool:
        """Check if process is running AND matches the expected creation time (PID reuse detection)"""
        if pid is None or pid <= 0:
            return False

        try:
            proc = psutil.Process(pid)
            if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
                return False

            # Verify creation time matches (detect PID reuse)
            # Use small tolerance for potential JSON serialization precision loss
            return abs(proc.create_time() - process_create_time) < 0.01
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
        except Exception:
            return False

    def terminate(self, pid: int, wait_time: float = 5.0) -> None:
        """Terminate process and its children"""
        if pid is None:
            return
        try:
            proc = psutil.Process(pid)
            if proc.status == psutil.STATUS_ZOMBIE:
                # Already terminated, waiting to be reaped
                return

            # Terminate process tree (children first)
            children = proc.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass

            proc.terminate()

            # Wait for graceful shutdown
            try:
                proc.wait(timeout=wait_time)
            except psutil.TimeoutExpired:
                # Force kill if still alive
                for child in children:
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
                proc.kill()

        except psutil.NoSuchProcess:
            pass
