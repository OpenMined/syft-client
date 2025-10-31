from syft_process_manager.runners.base import ProcessRunner
from syft_process_manager.runners.subprocess import SubprocessRunner


def get_runner(name: str) -> ProcessRunner:
    """Factory to get runner by name"""
    runners = {
        "subprocess": SubprocessRunner,
    }

    runner_cls = runners.get(name)
    if runner_cls is None:
        raise ValueError(f"Unknown runner: {name}. Available: {list(runners.keys())}")

    return runner_cls()


__all__ = ["ProcessRunner", "SubprocessRunner", "get_runner"]
