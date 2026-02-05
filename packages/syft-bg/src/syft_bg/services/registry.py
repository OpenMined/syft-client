"""Service registry for background services."""

from syft_bg.common.config import get_default_paths
from syft_bg.services.base import Service


def _create_services() -> dict[str, Service]:
    """Create service definitions using unified paths."""
    paths = get_default_paths()

    return {
        "notify": Service(
            name="notify",
            description="Email notifications for job and peer events",
            pid_file=paths.notify_pid,
            log_file=paths.notify_log,
        ),
        "approve": Service(
            name="approve",
            description="Auto-approve jobs and peer requests",
            pid_file=paths.approve_pid,
            log_file=paths.approve_log,
        ),
    }


SERVICES = _create_services()
