import time

from syft_process_manager import run_function
from syft_process_manager.process_manager import ProcessManager


def test_function_execution_with_ttl_and_health(
    process_manager: ProcessManager,
) -> None:
    """Test running Python function with TTL and automatic health checks."""

    def long_running_task(iterations: int) -> None:
        for i in range(iterations):
            print(f"Iteration {i}", flush=True)
            time.sleep(0.5)

    handle = run_function(
        long_running_task,
        iterations=20,
        name="test-worker",
        ttl_seconds=2,
        process_manager=process_manager,
    )

    assert handle.is_running()
    assert handle.pid is not None

    time.sleep(1)

    health = handle.health
    assert health is not None
    assert health.status == "healthy"

    stdout = handle.stdout.tail(10)
    assert "Iteration 0" in stdout

    time.sleep(2)

    handle.refresh()
    assert not handle.is_running()
    assert handle.pid is None
    assert handle.status == "stopped"
