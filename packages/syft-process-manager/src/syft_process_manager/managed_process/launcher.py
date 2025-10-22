"""
Launch Python functions as managed processes with TTL and health checks.
"""

import sys
import time
from typing import Any, Callable

import cloudpickle

from syft_process_manager.config import ProcessManagerConfig
from syft_process_manager.handle import ProcessHandle
from syft_process_manager.managed_process.env import create_env_dict
from syft_process_manager.process_manager import ProcessManager


def launch_function(
    func: Callable,
    *args: Any,
    name: str | None = None,
    ttl: float | None = None,
    health_check: bool = True,
    log_level: str = "INFO",
    config: ProcessManagerConfig | None = None,
    **kwargs: Any,
) -> ProcessHandle:
    """
    Launch a Python function as a managed detached process.

    Args:
        func: The function to execute
        *args: Positional arguments for the function
        name: Process name (auto-generated if not provided)
        ttl: Time-to-live in seconds (process auto-exits after this time)
        health_check: Enable periodic health check file writing
        log_level: Logging level for the subprocess
        config: ProcessManagerConfig (uses default if not provided)
        **kwargs: Keyword arguments for the function

    Returns:
        ProcessHandle for the launched process
    """
    # Use default config if not provided
    if config is None:
        config = ProcessManagerConfig()

    # Create process manager
    manager = ProcessManager.from_config(config)

    # Generate name if not provided
    if name is None:
        name = f"{func.__name__}_{int(time.time())}"

    # Command to run the wrapper
    cmd = [sys.executable, "-m", "syft_process_manager.managed_process._main"]

    # Create handle using manager (sets up all paths)
    handle = manager.init_handle(name=name, cmd=cmd)

    # Serialize function to pickle file in process_dir
    handle.info.process_dir.mkdir(parents=True, exist_ok=True)
    pickle_path = handle.info.process_dir / "function.pkl"
    pickle_path.write_bytes(cloudpickle.dumps((func, args, kwargs)))

    # Setup health check path if enabled
    health_path = handle.info.health_path if health_check else None

    # Calculate stop_at from ttl
    stop_at = time.time() + ttl if ttl else None

    # Create environment variables for the subprocess
    env = create_env_dict(
        pickle_path=pickle_path,
        health_path=health_path,
        stop_at=stop_at,
        log_level=log_level,
    )

    # Start the process with custom environment
    handle.start(env=env)

    return handle
