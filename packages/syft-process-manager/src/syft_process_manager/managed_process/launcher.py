"""
Launch Python functions as managed processes with TTL and health checks.
"""

import sys
import time
from typing import Any, Callable

import cloudpickle

from syft_process_manager.handle import ProcessHandle
from syft_process_manager.process_manager import ProcessManager


def create_handle_for_function(
    func: Callable,
    *args: Any,
    name: str | None = None,
    env: dict[str, str] | None = None,
    ttl_seconds: int | None = None,
    runner_type: str = "subprocess",
    log_level: str = "INFO",
    process_manager: ProcessManager | None = None,
    overwrite: bool = False,
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

    # Create process manager
    process_manager = process_manager or ProcessManager()

    # Generate name if not provided
    if name is None:
        name = f"{func.__name__}_{int(time.time())}"

    # Command to run the wrapper
    cmd = [sys.executable, "-m", "syft_process_manager.managed_process._main"]

    # Create handle using manager (sets up all paths)
    handle = process_manager.create_handle(
        name=name,
        cmd=cmd,
        env=env,
        ttl_seconds=ttl_seconds,
        log_level=log_level,
        runner_type=runner_type,
        overwrite=overwrite,
    )

    # Serialize function to pickle file in process_dir
    handle.config.process_dir.mkdir(parents=True, exist_ok=True)
    pickle_path = handle.config.process_dir / "function.pkl"
    with open(pickle_path, "wb") as f:
        cloudpickle.dump((func, args, kwargs), f)

    return handle


def launch(
    func: Callable,
    *args: Any,
    name: str | None = None,
    env: dict[str, str] | None = None,
    ttl_seconds: int | None = None,
    runner_type: str = "subprocess",
    log_level: str = "INFO",
    process_manager: ProcessManager | None = None,
    overwrite: bool = False,
    **kwargs: Any,
) -> ProcessHandle:
    # Start the process with custom environment
    handle = create_handle_for_function(
        func,
        *args,
        name=name,
        env=env,
        ttl_seconds=ttl_seconds,
        runner_type=runner_type,
        log_level=log_level,
        process_manager=process_manager,
        overwrite=overwrite,
        **kwargs,
    )
    handle.start()
    return handle
