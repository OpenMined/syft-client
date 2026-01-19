"""Test for truncated logs when jobs have exceptions."""

import tempfile
from pathlib import Path
from syft_job.job_runner import SyftJobRunner
from syft_job.config import SyftJobConfig


def test_exception_logs_not_truncated():
    """Test that exception tracebacks are fully captured in stderr."""

    with tempfile.TemporaryDirectory() as tmpdir:
        syftbox_folder = Path(tmpdir) / "SyftBox"
        syftbox_folder.mkdir(parents=True)
        email = "test@example.com"

        config = SyftJobConfig.from_syftbox_folder(str(syftbox_folder), email)

        job_name = "test_exception_job"
        job_dir = config.get_job_dir(email) / job_name
        job_dir.mkdir(parents=True)

        (job_dir / "config.yaml").write_text("name: test_exception_job\n")

        python_script = """
import sys
print("Starting job...", flush=True)
print("Line 2", flush=True)
print("Line 3", flush=True)

def func_a():
    func_b()

def func_b():
    func_c()

def func_c():
    func_d()

def func_d():
    raise ValueError("This is a test error with details: " + "x" * 50)

func_a()
"""
        (job_dir / "script.py").write_text(python_script)
        (job_dir / "run.sh").write_text("#!/bin/bash\npython script.py\n")

        config.create_approved_marker(job_dir)

        runner = SyftJobRunner(config)
        runner._execute_job(job_name, stream_output=True, timeout=30)

        stdout_content = (job_dir / "stdout.txt").read_text()
        stderr_content = (job_dir / "stderr.txt").read_text()

        # Check stdout has all print statements
        assert "Starting job..." in stdout_content
        assert "Line 2" in stdout_content
        assert "Line 3" in stdout_content

        # Check stderr has full traceback
        assert "Traceback (most recent call last)" in stderr_content
        assert "func_a" in stderr_content
        assert "func_d" in stderr_content
        assert "ValueError" in stderr_content
        assert "This is a test error" in stderr_content
