import logging
import os
import signal
import subprocess
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from syft_notify.core.config import get_default_paths


class DaemonManager:
    def __init__(self, config_path: Path):
        self.config_path = Path(config_path).expanduser()

        paths = get_default_paths()
        self.pid_file = paths["pid"]
        self.log_file = paths["log"]

        self.pid_file.parent.mkdir(parents=True, exist_ok=True)

    def start(self, interval: Optional[int] = None) -> bool:
        if self.is_running():
            pid = self.get_pid()
            print(f"❌ Daemon already running (PID {pid})")
            return False

        print("🔔 Starting syft-notify daemon...")
        print(f"   Config: {self.config_path}")
        print(f"   Logs: {self.log_file}")

        # Build command - use python -u for unbuffered output
        cmd = [sys.executable, "-u", "-m", "syft_notify.cli.commands", "run"]
        if interval:
            cmd.extend(["--interval", str(interval)])

        # Start process in background with output to log file
        # Note: Don't use context manager - keep file handle open for subprocess
        log_fd = open(self.log_file, "a")
        process = subprocess.Popen(
            cmd,
            stdout=log_fd,
            stderr=log_fd,
            start_new_session=True,  # Detach from terminal
            cwd=str(Path.home()),
        )
        # Don't close log_fd - subprocess needs it

        # Write PID file
        self.pid_file.write_text(str(process.pid))

        # Wait briefly and verify it's running
        time.sleep(1)
        if self.is_running():
            print(f"✅ Daemon started (PID {process.pid})")
            return True
        else:
            print("❌ Daemon failed to start. Check logs:")
            print(f"   {self.log_file}")
            return False

    def stop(self) -> bool:
        pid = self.get_pid()
        if not pid:
            print("❌ Daemon not running")
            return False

        print(f"⏹️  Stopping daemon (PID {pid})...")

        try:
            os.kill(pid, signal.SIGTERM)

            for _ in range(20):
                if not self.is_running():
                    print("✅ Daemon stopped")
                    return True
                time.sleep(0.5)

            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)

            if not self.is_running():
                print("✅ Daemon force-stopped")
                return True

            print("❌ Failed to stop daemon")
            return False

        except ProcessLookupError:
            print(f"⚠️  Process {pid} not found (stale PID file)")
            self.pid_file.unlink(missing_ok=True)
            return True
        except PermissionError:
            print("❌ Permission denied")
            return False

    def status(self) -> bool:
        pid = self.get_pid()

        if pid and self.is_running():
            print("✅ Daemon is running")
            print(f"   PID: {pid}")
            print(f"   Config: {self.config_path}")
            print(f"   Logs: {self.log_file}")

            if self.log_file.exists():
                print("\n📋 Recent activity:")
                lines = self.log_file.read_text().strip().split("\n")
                for line in lines[-5:]:
                    print(f"   {line}")

            return True
        else:
            print("❌ Daemon is not running")
            return False

    def restart(self, interval: Optional[int] = None) -> bool:
        print("🔄 Restarting daemon...")
        self.stop()
        time.sleep(2)
        return self.start(interval)

    def logs(self, follow: bool = False, lines: int = 50):
        if not self.log_file.exists():
            print(f"❌ Log file not found: {self.log_file}")
            return

        if follow:
            import subprocess

            print(f"📋 Following {self.log_file} (Ctrl+C to stop)...")
            try:
                subprocess.run(["tail", "-f", str(self.log_file)])
            except KeyboardInterrupt:
                print("\n⏹️  Stopped")
        else:
            print(f"📋 Last {lines} lines:")
            all_lines = self.log_file.read_text().strip().split("\n")
            for line in all_lines[-lines:]:
                print(line)

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

    def _setup_logging(self):
        import warnings

        warnings.filterwarnings("ignore", module="oauth2client")
        logging.getLogger("oauth2client").setLevel(logging.ERROR)
        logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)

        logger = logging.getLogger()
        logger.setLevel(logging.INFO)

        handler = RotatingFileHandler(
            self.log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=7,
        )

        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    def _run(self, interval: Optional[int]):
        self._setup_logging()

        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(line_buffering=True)
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(line_buffering=True)

        from syft_notify.orchestrator import NotificationOrchestrator

        print(f"🔔 Daemon started (PID {os.getpid()})")
        print(f"   Config: {self.config_path}")

        try:
            orchestrator = NotificationOrchestrator.from_config(
                str(self.config_path),
                interval=interval,
            )
            orchestrator.run()
        except Exception as e:
            print(f"❌ Fatal error: {e}")
            import traceback

            traceback.print_exc()
            raise

    def _shutdown_handler(self, signum, frame):
        print("\n⏹️  Received SIGTERM, shutting down...")
        sys.exit(0)
