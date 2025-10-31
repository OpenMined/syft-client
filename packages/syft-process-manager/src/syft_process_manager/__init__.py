from syft_process_manager.constants import DEFAULT_PROCESS_MANAGER_DIR  # noqa: F401
from syft_process_manager.handle import ProcessHandle  # noqa: F401
from syft_process_manager.managed_process.launcher import run_function  # noqa: F401
from syft_process_manager.managed_process.signals import (
    shutdown_requested,  # noqa: F401
)
from syft_process_manager.process_manager import ProcessManager  # noqa: F401


def run(
    name: str,
    cmd: list[str],
    env: dict[str, str] | None = None,
    runner_type: str = "subprocess",
    overwrite: bool = False,
    process_manager: ProcessManager | None = None,
) -> ProcessHandle:
    process_manager = process_manager or ProcessManager()
    return process_manager.create_and_run(
        name=name,
        cmd=cmd,
        env=env,
        runner_type=runner_type,
        overwrite=overwrite,
    )


def get(
    name: str,
    process_manager: ProcessManager | None = None,
) -> ProcessHandle:
    process_manager = process_manager or ProcessManager()
    return process_manager.get(name)


def list(
    process_manager: ProcessManager | None = None,
) -> list[ProcessHandle]:
    process_manager = process_manager or ProcessManager()
    return process_manager.list()
