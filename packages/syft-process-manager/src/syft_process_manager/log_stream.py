"""
Simplified log stream access for server stdout and stderr
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class LogStream:
    """Access to a server's log stream (stdout or stderr)"""

    def __init__(self, log_path: Path, stream_type: str = "stdout"):
        self.log_path = log_path
        self.stream_type = stream_type

    def read_lines(self) -> list[str]:
        """Read all lines from log file"""
        if not self.log_path.exists():
            return []
        try:
            content = self.log_path.read_text(encoding="utf-8", errors="ignore")
            return content.splitlines() if content else []
        except Exception as e:
            logger.warning(f"Failed to read {self.log_path}: {e}")
            return []

    def tail(self, n: int = 10) -> str:
        """Return last n lines"""
        lines = self.read_lines()
        return "\n".join(lines[-n:]) if lines else ""

    def head(self, n: int = 10) -> str:
        """Return first n lines"""
        lines = self.read_lines()
        return "\n".join(lines[:n]) if lines else ""

    def __repr__(self) -> str:
        """Show recent log entries"""
        recent = self.tail(5)
        if recent:
            return f"<LogStream {self.stream_type}>\n{recent}"
        else:
            return f"<LogStream {self.stream_type}: empty>"
