"""
Environment variable handling for managed processes.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProcessSettings:
    """Configuration from environment variables"""

    pickle_path: Path
    health_path: Path | None
    stop_at: float | None
    log_level: str


def get_process_settings() -> ProcessSettings:
    """Read all SYFTPM environment variables"""
    pickle_path = Path(os.environ["SYFTPM_PICKLE_PATH"])
    health_path_str = os.environ.get("SYFTPM_HEALTH_PATH")
    health_path = Path(health_path_str) if health_path_str else None
    stop_at_str = os.environ.get("SYFTPM_STOP_AT")
    stop_at = float(stop_at_str) if stop_at_str else None
    log_level = os.environ.get("SYFTPM_LOG_LEVEL", "INFO")

    return ProcessSettings(
        pickle_path=pickle_path,
        health_path=health_path,
        stop_at=stop_at,
        log_level=log_level,
    )


def create_env_dict(
    pickle_path: Path,
    health_path: Path | None = None,
    stop_at: float | None = None,
    log_level: str = "INFO",
) -> dict[str, str]:
    """Create environment variable dict for subprocess"""
    env = {
        "SYFTPM_PICKLE_PATH": str(pickle_path),
        "SYFTPM_LOG_LEVEL": log_level,
    }

    if health_path:
        env["SYFTPM_HEALTH_PATH"] = str(health_path)

    if stop_at:
        env["SYFTPM_STOP_AT"] = str(stop_at)

    return env
