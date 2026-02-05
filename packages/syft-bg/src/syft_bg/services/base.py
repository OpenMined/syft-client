"""Base service definition for background services."""

import os
import signal
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class ServiceStatus(Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class ServiceInfo:
    status: ServiceStatus
    pid: Optional[int] = None
    uptime: Optional[str] = None
    last_activity: Optional[str] = None


class Service:
    """A background service that runs as a subprocess."""

    def __init__(
        self,
        name: str,
        description: str,
        pid_file: Path,
        log_file: Path,
    ):
        self.name = name
        self.description = description
        self.pid_file = pid_file
        self.log_file = log_file

    def get_pid(self) -> Optional[int]:
        """Get the PID from the pid file."""
        if not self.pid_file.exists():
            return None
        try:
            return int(self.pid_file.read_text().strip())
        except (ValueError, OSError):
            return None

    def is_running(self) -> bool:
        """Check if the service is running."""
        pid = self.get_pid()
        if not pid:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def get_status(self) -> ServiceInfo:
        """Get the current service status."""
        pid = self.get_pid()
        if pid and self.is_running():
            return ServiceInfo(
                status=ServiceStatus.RUNNING,
                pid=pid,
            )
        return ServiceInfo(status=ServiceStatus.STOPPED)

    def start(self) -> tuple[bool, str]:
        """Start the service as a background subprocess."""
        if self.is_running():
            return (False, f"{self.name} is already running")

        try:
            # Ensure directories exist
            self.pid_file.parent.mkdir(parents=True, exist_ok=True)
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

            # Open log file for output
            log_fd = open(self.log_file, "a")

            # Spawn syft-bg run --service <name> as a daemon
            process = subprocess.Popen(
                [sys.executable, "-m", "syft_bg", "run", "--service", self.name],
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # Detach from parent process group
            )

            # Write PID file
            self.pid_file.write_text(str(process.pid))

            return (True, f"{self.name} started (PID {process.pid})")

        except Exception as e:
            return (False, str(e))

    def stop(self) -> tuple[bool, str]:
        """Stop the service."""
        if not self.is_running():
            # Clean up stale PID file
            if self.pid_file.exists():
                self.pid_file.unlink()
            return (False, f"{self.name} is not running")

        pid = self.get_pid()
        if not pid:
            return (False, "Could not get PID")

        try:
            # Send SIGTERM for graceful shutdown
            os.kill(pid, signal.SIGTERM)

            # Wait briefly for process to terminate
            import time

            for _ in range(10):  # Wait up to 1 second
                time.sleep(0.1)
                try:
                    os.kill(pid, 0)
                except OSError:
                    break  # Process terminated
            else:
                # Force kill if still running
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass

            # Clean up PID file
            if self.pid_file.exists():
                self.pid_file.unlink()

            return (True, f"{self.name} stopped")

        except OSError as e:
            return (False, f"Failed to stop: {e}")

    def restart(self) -> tuple[bool, str]:
        """Restart the service."""
        if self.is_running():
            success, msg = self.stop()
            if not success:
                return (False, f"Failed to stop: {msg}")

        return self.start()

    def get_logs(self, lines: int = 50) -> list[str]:
        """Get recent log lines."""
        if not self.log_file.exists():
            return []
        try:
            all_lines = self.log_file.read_text().strip().split("\n")
            return all_lines[-lines:]
        except Exception:
            return []
