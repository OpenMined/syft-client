"""
Daemon process manager for syft-notify.

Handles background daemon lifecycle:
- Start/stop/restart/status
- PID file management
- Log file rotation
- Signal handling (SIGTERM, SIGHUP)
"""

import os
import signal
import sys
import time
import logging
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler

import daemon
import daemon.pidfile


class DaemonManager:
    """Manages the syft-notify background daemon process."""

    def __init__(self, config_path: Path):
        """
        Initialize daemon manager.

        Args:
            config_path: Path to daemon.yaml configuration file
        """
        self.config_path = Path(config_path).expanduser()

        # File paths
        creds_dir = Path.home() / ".syft-creds"
        creds_dir.mkdir(parents=True, exist_ok=True)

        self.pid_file = creds_dir / "syft-notify.pid"
        self.log_file = creds_dir / "syft-notify.log"
        self.error_log_file = creds_dir / "syft-notify.error.log"

    def start(self, interval: Optional[int] = None):
        """
        Start daemon in background.

        Args:
            interval: Check interval in seconds (overrides config)
        """
        if self.is_running():
            pid = self.get_pid()
            print(f"❌ Daemon already running (PID {pid})")
            print("   Use 'syft-notify stop' to stop it first")
            return False

        print("🔔 Starting syft-notify daemon...")
        print(f"   Config: {self.config_path}")
        print(f"   PID file: {self.pid_file}")
        print(f"   Logs: {self.log_file}")

        # Setup logging for daemon process
        self._setup_logging()

        # Create daemon context
        context = daemon.DaemonContext(
            working_directory=str(Path.home()),
            pidfile=daemon.pidfile.PIDLockFile(str(self.pid_file)),
            umask=0o002,
            signal_map={
                signal.SIGTERM: self._shutdown_handler,
                signal.SIGHUP: self._reload_handler,
            },
            # Redirect stdout/stderr to log files
            stdout=open(self.log_file, "a"),
            stderr=open(self.error_log_file, "a"),
        )

        # Start daemon
        with context:
            self._run_monitor(interval)

        return True

    def stop(self):
        """Stop running daemon."""
        pid = self.get_pid()
        if not pid:
            print("❌ Daemon not running")
            return False

        print(f"⏹️  Stopping daemon (PID {pid})...")

        try:
            # Send SIGTERM for graceful shutdown
            os.kill(pid, signal.SIGTERM)

            # Wait for process to die (max 10 seconds)
            for i in range(20):
                if not self.is_running():
                    print("✅ Daemon stopped successfully")
                    return True
                time.sleep(0.5)

            # Force kill if still running
            print("⚠️  Daemon didn't stop gracefully, forcing...")
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)

            if not self.is_running():
                print("✅ Daemon force-stopped")
                return True
            else:
                print("❌ Failed to stop daemon")
                return False

        except ProcessLookupError:
            print(f"⚠️  Process {pid} not found (stale PID file)")
            self.pid_file.unlink(missing_ok=True)
            return True
        except PermissionError:
            print("❌ Permission denied (try with sudo?)")
            return False

    def status(self) -> bool:
        """
        Check daemon status.

        Returns:
            True if running, False otherwise
        """
        pid = self.get_pid()

        if pid and self.is_running():
            print("✅ Daemon is running")
            print(f"   PID: {pid}")
            print(f"   Config: {self.config_path}")
            print(f"   Logs: {self.log_file}")
            print(f"   Errors: {self.error_log_file}")

            # Show recent log lines
            if self.log_file.exists():
                print("\n📋 Recent activity (last 5 lines):")
                lines = self.log_file.read_text().strip().split("\n")
                for line in lines[-5:]:
                    print(f"   {line}")

            return True
        else:
            print("❌ Daemon is not running")
            if self.pid_file.exists():
                print(f"   (Stale PID file found: {self.pid_file})")
            return False

    def restart(self, interval: Optional[int] = None):
        """
        Restart daemon.

        Args:
            interval: Check interval in seconds (overrides config)
        """
        print("🔄 Restarting daemon...")
        self.stop()
        time.sleep(2)
        return self.start(interval)

    def logs(self, follow: bool = False, lines: int = 50):
        """
        Show daemon logs.

        Args:
            follow: Follow log output (like tail -f)
            lines: Number of lines to show (if not following)
        """
        if not self.log_file.exists():
            print(f"❌ Log file not found: {self.log_file}")
            return

        if follow:
            print("📋 Following logs (Ctrl+C to stop)...")
            print(f"   {self.log_file}")
            print()

            # Use tail -f for following
            import subprocess

            try:
                subprocess.run(["tail", "-f", str(self.log_file)])
            except KeyboardInterrupt:
                print("\n⏹️  Stopped following logs")
        else:
            print(f"📋 Last {lines} lines from {self.log_file}:")
            print()

            all_lines = self.log_file.read_text().strip().split("\n")
            for line in all_lines[-lines:]:
                print(line)

    def get_pid(self) -> Optional[int]:
        """
        Get daemon PID from PID file.

        Returns:
            Process ID or None if not found
        """
        if not self.pid_file.exists():
            return None

        try:
            pid_str = self.pid_file.read_text().strip()
            return int(pid_str)
        except (ValueError, OSError):
            return None

    def is_running(self) -> bool:
        """
        Check if daemon process is actually running.

        Returns:
            True if process exists and is running
        """
        pid = self.get_pid()
        if not pid:
            return False

        try:
            # Send signal 0 - doesn't kill, just checks if process exists
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _setup_logging(self):
        """Setup rotating log file handler."""
        # This runs in the daemon process, not the parent
        # Configure Python's logging module for use within the monitor
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)

        # Rotating file handler - max 10MB per file, keep 7 files
        handler = RotatingFileHandler(
            self.log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=7,  # Keep 7 old files
        )

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    def _run_monitor(self, interval: Optional[int]):
        """
        Run the notification monitor (called inside daemon context).

        Args:
            interval: Check interval in seconds
        """
        from .monitor import NotificationMonitor

        # This runs in daemon context - stdout/stderr redirected to logs
        print(f"🔔 Daemon started (PID {os.getpid()})")
        print(f"   Config: {self.config_path}")
        print(f"   Interval: {interval or 'from config'}")
        print()

        try:
            monitor = NotificationMonitor.from_config(
                str(self.config_path),
                interval=interval,
            )
            monitor.run()  # Blocks forever
        except Exception as e:
            print(f"❌ Fatal error in daemon: {e}")
            import traceback

            traceback.print_exc()
            raise

    def _shutdown_handler(self, signum, frame):
        """Handle SIGTERM for graceful shutdown."""
        print("\n⏹️  Received SIGTERM, shutting down gracefully...")
        # Clean exit
        sys.exit(0)

    def _reload_handler(self, signum, frame):
        """Handle SIGHUP for config reload (future enhancement)."""
        print("\n🔄 Received SIGHUP (config reload not yet implemented)")
        # TODO: Implement config reload without restart
