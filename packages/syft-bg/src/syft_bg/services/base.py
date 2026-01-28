from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional
import os
import subprocess


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
    def __init__(
        self,
        name: str,
        command: str,
        description: str,
        pid_file: Path,
        log_file: Path,
    ):
        self.name = name
        self.command = command
        self.description = description
        self.pid_file = pid_file
        self.log_file = log_file

    def get_pid(self) -> Optional[int]:
        if not self.pid_file.exists():
            return None
        try:
            return int(self.pid_file.read_text().strip())
        except (ValueError, OSError):
            return None

    def is_running(self) -> bool:
        pid = self.get_pid()
        if not pid:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def get_status(self) -> ServiceInfo:
        pid = self.get_pid()
        if pid and self.is_running():
            return ServiceInfo(
                status=ServiceStatus.RUNNING,
                pid=pid,
            )
        return ServiceInfo(status=ServiceStatus.STOPPED)

    def start(self) -> tuple[bool, str]:
        if self.is_running():
            return (False, f"{self.name} is already running")

        try:
            result = subprocess.run(
                [self.command, "start"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return (True, f"{self.name} started")
            return (False, result.stderr or result.stdout or "Unknown error")
        except subprocess.TimeoutExpired:
            return (False, "Timeout starting service")
        except FileNotFoundError:
            return (False, f"Command not found: {self.command}")
        except Exception as e:
            return (False, str(e))

    def stop(self) -> tuple[bool, str]:
        if not self.is_running():
            return (False, f"{self.name} is not running")

        try:
            result = subprocess.run(
                [self.command, "stop"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return (True, f"{self.name} stopped")
            return (False, result.stderr or result.stdout or "Unknown error")
        except subprocess.TimeoutExpired:
            return (False, "Timeout stopping service")
        except Exception as e:
            return (False, str(e))

    def restart(self) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                [self.command, "restart"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                return (True, f"{self.name} restarted")
            return (False, result.stderr or result.stdout or "Unknown error")
        except subprocess.TimeoutExpired:
            return (False, "Timeout restarting service")
        except Exception as e:
            return (False, str(e))

    def get_logs(self, lines: int = 50) -> list[str]:
        if not self.log_file.exists():
            return []
        try:
            all_lines = self.log_file.read_text().strip().split("\n")
            return all_lines[-lines:]
        except Exception:
            return []
