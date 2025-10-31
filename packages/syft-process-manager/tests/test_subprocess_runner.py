import time

import psutil
import pytest
from syft_process_manager.models import ProcessState
from syft_process_manager.process_manager import ProcessManager


def test_subprocess_lifecycle(process_manager: ProcessManager) -> None:
    """Test start, verify running, terminate, verify stopped."""
    handle = process_manager.create_and_run(
        name="test-process",
        cmd=["python", "-c", "import time; time.sleep(60)"],
    )

    assert handle.is_running()
    assert handle.status == "running"
    assert handle.pid is not None

    handle.terminate()

    assert not handle.is_running()
    assert handle.status == "stopped"
    assert handle.pid is None


def test_stdout_stderr_logs(process_manager: ProcessManager) -> None:
    """Test capturing and reading stdout/stderr logs."""
    handle = process_manager.create_and_run(
        name="log-process",
        cmd=[
            "python",
            "-c",
            "import sys; print('stdout message'); print('stderr message', file=sys.stderr); import time; time.sleep(0.5)",
        ],
    )

    time.sleep(1)

    stdout = handle.stdout.tail(10)
    stderr = handle.stderr.tail(10)

    assert "stdout message" in stdout
    assert "stderr message" in stderr

    handle.terminate()


def test_custom_environment_variables(process_manager: ProcessManager) -> None:
    """Test custom environment variables passed to subprocess."""
    handle = process_manager.create_and_run(
        name="env-process",
        cmd=[
            "python",
            "-c",
            "import os; print(f'CUSTOM_VAR={os.environ.get(\"CUSTOM_VAR\")}'); import time; time.sleep(0.5)",
        ],
        env={"CUSTOM_VAR": "test_value"},
    )

    time.sleep(1)

    stdout = handle.stdout.tail(10)
    assert "CUSTOM_VAR=test_value" in stdout

    handle.terminate()


def test_process_overwrite(process_manager: ProcessManager) -> None:
    """Test replacing existing process with same name."""
    handle1 = process_manager.create_and_run(
        name="overwrite-test",
        cmd=["python", "-c", "import time; time.sleep(60)"],
    )
    pid1 = handle1.pid
    assert handle1.is_running()

    with pytest.raises(ValueError, match="already exists"):
        process_manager.create_and_run(
            name="overwrite-test",
            cmd=["python", "-c", "import time; time.sleep(60)"],
            overwrite=False,
        )

    handle2 = process_manager.create_and_run(
        name="overwrite-test",
        cmd=["python", "-c", "import time; time.sleep(60)"],
        overwrite=True,
    )
    pid2 = handle2.pid

    assert handle2.is_running()
    assert pid2 != pid1

    assert (
        not psutil.pid_exists(pid1)
        or psutil.Process(pid1).status() == psutil.STATUS_ZOMBIE
    )

    handle2.terminate()


def test_handle_process_death_and_refresh(process_manager: ProcessManager) -> None:
    """Test refresh correctly updates state when process dies or becomes zombie."""
    handle = process_manager.create_and_run(
        name="short-lived",
        cmd=["sh", "-c", "sleep 0.2 && exit 0"],
    )

    pid = handle.pid
    assert pid is not None
    assert handle.is_running()

    time.sleep(0.5)

    try:
        proc = psutil.Process(pid)
        assert proc.status() == psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        pass

    handle.refresh()
    assert not handle.is_running()
    assert handle.status == "stopped"
    assert handle.pid is None


def test_pid_reuse_protection(process_manager: ProcessManager) -> None:
    """Test that PID reuse is detected via creation timestamp."""
    handle = process_manager.create_and_run(
        name="pid-test",
        cmd=["python", "-c", "import time; time.sleep(60)"],
    )

    original_pid = handle.pid
    assert handle.is_running()

    fake_state = ProcessState(
        pid=original_pid,
        process_create_time=999999.0,
    )
    handle.config.process_state_path.write_text(fake_state.model_dump_json(indent=2))

    assert not handle.is_running()

    handle.terminate()
