"""
Main entry point for wrapped function processes.
Launched as subprocess with environment variables for configuration.
"""

import logging
import sys
import threading
import time
from typing import Callable

import cloudpickle

from syft_process_manager.managed_process.env import get_process_settings
from syft_process_manager.models import ProcessHealth

logger = logging.getLogger(__name__)


def setup_logging(log_level: str):
    """Setup basic logging to stdout"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def check_ttl(stop_at: float | None):
    """Check if TTL has been reached and exit if so."""
    if stop_at and time.time() >= stop_at:
        logger.info("TTL reached, exiting process")
        sys.exit(0)


def write_health(health_path):
    """Write health check status to file."""
    try:
        health_str = ProcessHealth().model_dump_json(indent=2)
        health_path.write_text(health_str)
    except Exception:
        logger.error("Failed to write health check", exc_info=True)


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


def main():
    """Run the wrapped function with health checks and TTL"""
    # Read configuration from environment
    env = get_process_settings()

    # Setup logging
    setup_logging(env.log_level)

    # Load function
    logger.info("Initializing managed process")
    try:
        func, args, kwargs = cloudpickle.loads(env.pickle_path.read_bytes())
    except Exception as e:
        logger.error(f"Failed to load function: {e}", exc_info=True)
        sys.exit(1)

    # Start function in worker thread (non-daemon so main waits)
    result = {"exception": None, "completed": False}
    func_thread = threading.Thread(
        target=run_user_function,
        args=(func, args, kwargs, result),
        daemon=False,
    )
    func_thread.start()

    # Main thread: monitor TTL and write health checks
    last_health_write = 0

    while func_thread.is_alive():
        # Check TTL
        check_ttl(env.stop_at)

        # Write health check every 5 seconds
        if env.health_path and (time.time() - last_health_write) >= 5:
            write_health(env.health_path)
            last_health_write = time.time()

        time.sleep(1)

    # Function thread completed, handle result
    if result["exception"]:
        sys.exit(1)

    logger.info("Managed process exiting successfully")
    sys.exit(0)


if __name__ == "__main__":
    main()
