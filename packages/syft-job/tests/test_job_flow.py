"""End-to-end unit test for the syft-job package lifecycle."""

from pathlib import Path

from syft_job.client import JobClient
from syft_job.config import SyftJobConfig
from syft_job.job_runner import SyftJobRunner
from syft_perm import SyftPermContext


DO_EMAIL = "do@test.org"
DS_EMAIL = "ds@test.org"

MAIN_PY = """\
import os

print("hello from job")
os.makedirs("outputs", exist_ok=True)
with open("outputs/result.txt", "w") as f:
    f.write("done")
"""


def test_full_job_lifecycle(tmp_path: Path):
    syftbox = tmp_path / "SyftBox"
    syftbox.mkdir()

    # Write a trivial main.py for the DS to submit
    code_file = tmp_path / "main.py"
    code_file.write_text(MAIN_PY)

    # Both configs share the same syftbox folder
    do_config = SyftJobConfig(syftbox_folder=syftbox, email=DO_EMAIL)
    ds_config = SyftJobConfig(syftbox_folder=syftbox, email=DS_EMAIL)

    ds_client = JobClient(config=ds_config)
    do_client = JobClient(config=do_config)
    do_runner = SyftJobRunner(config=do_config)

    # --- DS submits a python job to DO ---
    job_dir = ds_client.submit_python_job(
        user=DO_EMAIL,
        code_path=str(code_file),
        job_name="test.job",
    )
    assert job_dir.exists()
    assert (job_dir / "run.sh").exists()
    assert (job_dir / "config.yaml").exists()
    assert (job_dir / "main.py").exists()

    # Job dir should be under the DS email subdirectory
    expected_parent = ds_config.get_job_dir(DO_EMAIL) / DS_EMAIL
    assert job_dir.parent == expected_parent

    # --- DO lists jobs and sees it as inbox ---
    jobs = do_client.jobs
    assert len(jobs) == 1
    job = jobs[0]
    assert job.name == "test.job"
    assert job.status == "inbox"
    assert job.submitted_by == DS_EMAIL

    # --- DO approves the job ---
    job.approve()
    assert job.status == "approved"
    assert (job_dir / "approved").exists()

    # --- DO runs approved jobs ---
    do_runner.process_approved_jobs(stream_output=False, timeout=120)

    # Re-fetch to get updated status
    job = do_client.jobs[0]
    assert job.status == "done"
    assert (job_dir / "done").exists()

    # --- Check outputs ---
    # output_paths includes syft.pub.yaml created by _prepare_outputs_dir
    output_names = {p.name for p in job.output_paths}
    assert "result.txt" in output_names
    result_file = next(p for p in job.output_paths if p.name == "result.txt")
    assert result_file.read_text().strip() == "done"

    # --- Check stdout / stderr ---
    stdout_path = job_dir / "stdout.txt"
    stderr_path = job_dir / "stderr.txt"
    assert stdout_path.exists()
    assert stderr_path.exists()
    assert "hello from job" in stdout_path.read_text()

    # --- Check returncode ---
    returncode_path = job_dir / "returncode.txt"
    assert returncode_path.exists()
    assert returncode_path.read_text().strip() == "0"

    # --- Before sharing, DS should NOT have read access ---
    ctx = SyftPermContext(datasite=syftbox / DO_EMAIL)
    assert not ctx.open("app_data/job/ds@test.org/test.job/outputs/").has_read_access(
        DS_EMAIL
    )
    assert not ctx.open("app_data/job/ds@test.org/test.job/stdout.txt").has_read_access(
        DS_EMAIL
    )
    assert not ctx.open("app_data/job/ds@test.org/test.job/stderr.txt").has_read_access(
        DS_EMAIL
    )
    assert not ctx.open(
        "app_data/job/ds@test.org/test.job/returncode.txt"
    ).has_read_access(DS_EMAIL)

    # --- Share outputs and logs with DS ---
    job.share_outputs([DS_EMAIL])
    job.share_logs([DS_EMAIL])

    # --- Verify DS has read access via SyftPermContext ---
    ctx = SyftPermContext(datasite=syftbox / DO_EMAIL)

    outputs_folder = ctx.open("app_data/job/ds@test.org/test.job/outputs/")
    assert outputs_folder.has_read_access(DS_EMAIL)

    stdout_file = ctx.open("app_data/job/ds@test.org/test.job/stdout.txt")
    assert stdout_file.has_read_access(DS_EMAIL)

    stderr_file = ctx.open("app_data/job/ds@test.org/test.job/stderr.txt")
    assert stderr_file.has_read_access(DS_EMAIL)

    returncode_file = ctx.open("app_data/job/ds@test.org/test.job/returncode.txt")
    assert returncode_file.has_read_access(DS_EMAIL)


def test_ds_job_folder_permissions(tmp_path: Path):
    """Test that ensure_ds_job_folder creates a folder with correct permissions."""
    syftbox = tmp_path / "SyftBox"
    syftbox.mkdir()

    do_config = SyftJobConfig(syftbox_folder=syftbox, email=DO_EMAIL)
    do_client = JobClient(config=do_config)

    # Create DS job folder with permissions
    ds_folder = do_client.ensure_ds_job_folder(DS_EMAIL)
    assert ds_folder.exists()
    assert ds_folder == do_config.get_job_dir(DO_EMAIL) / DS_EMAIL

    # DS should have write access to their folder
    ctx = SyftPermContext(datasite=syftbox / DO_EMAIL)
    folder = ctx.open(f"app_data/job/{DS_EMAIL}/")
    assert folder.has_write_access(DS_EMAIL)

    # Another user should NOT have write access
    other_email = "other@test.org"
    assert not folder.has_write_access(other_email)
