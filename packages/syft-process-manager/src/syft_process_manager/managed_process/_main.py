"""
Main entry point for wrapped function processes.
Launched as subprocess with environment variables for configuration.
"""

import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Callable

import cloudpickle

from syft_process_manager.models import ProcessConfig, ProcessHealth

logger = logging.getLogger(__name__)

# Global flag for shutdown
_shutdown_requested = threading.Event()


def set_process_title(title: str):
    """Set the process title for easier identification."""
    try:
        import setproctitle

        setproctitle.setproctitle(title)
    except ImportError:
        logger.warning("setproctitle module not found, process title not set")
    except Exception as e:
        logger.error(f"Failed to set process title: {e}")


def setup_logging(log_level: str):
    """Setup basic logging to stderr"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )


def load_process_config() -> ProcessConfig:
    process_dir = os.environ.get("SYFTPM_PROCESS_DIR", None)
    if process_dir is None:
        raise ValueError("SYFTPM_PROCESS_DIR environment variable not set")
    process_dir = Path(process_dir)
    return ProcessConfig.load(process_dir)


def write_health(health_path):
    """Write health check status to file."""
    try:
        health_str = ProcessHealth().model_dump_json(indent=2)
        health_path.write_text(health_str)
        logger.debug("Health check written to %s", health_path)
    except Exception:
        logger.error("Failed to write health check", exc_info=True)


def load_user_function(config: ProcessConfig) -> tuple[Callable, tuple, dict]:
    pickle_path = config.process_dir / "function.pkl"
    with open(pickle_path, "rb") as f:
        func, args, kwargs = cloudpickle.load(f)
    return func, args, kwargs


def run_user_function(
    func: Callable,
    args: tuple,
    kwargs: dict,
    result_container: dict,
):
    """Execute user function in separate thread"""
    try:
        logger.info("Starting function execution")
        func(*args, **kwargs)
        result_container["completed"] = True
        logger.info("Function completed successfully")
    except Exception as e:
        result_container["exception"] = e
        logger.error(f"Function failed: {e}", exc_info=True)
    finally:
        logger.debug("Function execution thread exiting")


def handle_shutdown_signal(signum, frame):
    """Handle SIGTERM/SIGINT for shutdown"""
    sig_name = signal.Signals(signum).name
    logger.info(f"Received {sig_name}, initiating shutdown...")
    _shutdown_requested.set()


def start_user_function(process_config: ProcessConfig) -> tuple[threading.Thread, dict]:
    """Load and start the user function in a separate thread"""
    logger.info("Initializing managed process")
    func, args, kwargs = load_user_function(process_config)

    result = {"exception": None, "completed": False}
    func_thread = threading.Thread(
        target=run_user_function,
        args=(func, args, kwargs, result),
        daemon=True,
    )
    func_thread.start()
    return func_thread, result


def handle_exit(func_thread: threading.Thread, result: dict):
    """Handle different exit scenarios"""
    if _shutdown_requested.is_set():
        func_thread.join(timeout=1.0)
        if func_thread.is_alive():
            logger.warning("Worker thread still running after 2s, forcing exit")
        else:
            logger.debug("Worker thread finished cleanly")
        logger.info("Shutdown completed")
        sys.exit(0)

    if result["exception"]:
        logger.error(f"Function raised an exception: {result['exception']}")
        sys.exit(1)

    logger.info("Managed process exiting successfully - function completed")
    sys.exit(0)


def main():
    """Run the wrapped function with health checks and TTL"""
    start_time = time.time()
    try:
        process_config = load_process_config()
    except Exception as e:
        logger.error(f"Failed to read process config: {e}", exc_info=True)
        sys.exit(1)

    setup_logging(process_config.log_level)
    set_process_title(f"syftpm - {process_config.name}")
    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    signal.signal(signal.SIGINT, handle_shutdown_signal)

    func_thread, result = start_user_function(process_config)

    # Monitor TTL and write health checks
    last_health_write = 0
    while func_thread.is_alive() and not _shutdown_requested.is_set():
        if process_config.ttl_seconds:
            now = time.time()
            stop_at = start_time + process_config.ttl_seconds
            if now >= stop_at:
                logger.info("TTL reached, exiting process...")
                sys.exit(0)

        if time.time() - last_health_write >= 5:
            write_health(process_config.health_path)
            last_health_write = time.time()

        time.sleep(1)

    handle_exit(func_thread, result)


if __name__ == "__main__":
    main()
