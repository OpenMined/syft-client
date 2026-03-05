"""Test for job auto-approval utility."""

import json
import tempfile
from pathlib import Path

from syft_client.job_auto_approval import auto_approve_and_run_jobs
from syft_client.sync.syftbox_manager import SyftboxManager


def test_auto_approve_and_run_jobs():
    """
    End-to-end test for auto_approve_and_run_jobs.

    Scenario: A job is submitted with a Python script and a JSON data file.
    The utility should only approve and run jobs that have:
    - The exact Python script content (newline agnostic)
    - Exactly the required files (no more, no less)
    """
    ds_manager, do_manager = SyftboxManager.pair_with_mock_drive_service_connection(
        use_in_memory_cache=False,
        sync_automatically=False,
    )

    # The expected script content (with \n newlines)
    expected_script = """import json
with open("outputs/result.json", "w") as f:
    f.write(json.dumps({"result": 42}))
"""

    # The same script but with \r\n newlines (Windows style) and extra blank lines
    script_with_crlf = 'import json\r\n\r\nwith open("outputs/result.json", "w") as f:\r\n    f.write(json.dumps({"result": 42}))\r\n'

    # Create a project folder with script and data file
    project_dir = Path(tempfile.mkdtemp(prefix="test_auto_approve_"))

    # Create main.py with CRLF newlines (simulating Windows file)
    main_path = project_dir / "main.py"
    main_path.write_text(script_with_crlf)

    # Create data.json
    data_path = project_dir / "data.json"
    data_path.write_text(json.dumps({"input": "test"}))

    # Submit job from DS to DO (folder submission)
    ds_manager.submit_python_job(
        user=do_manager.email,
        code_path=str(project_dir),
        job_name="test_auto_approve.job",
        entrypoint="main.py",
    )

    # Sync to DO
    do_manager.sync()

    # Verify job is in inbox
    assert len(do_manager.jobs) == 1
    assert do_manager.jobs[0].status == "inbox"

    # Call auto_approve_and_run_jobs - must specify ALL files including the .py file
    approved = auto_approve_and_run_jobs(
        do_manager,
        required_scripts={"main.py": expected_script},
        required_filenames=["main.py", "data.json"],
        verbose=False,
    )

    # Verify job was approved and run
    assert len(approved) == 1

    # Before sharing: DS should not see outputs
    do_manager.sync()
    ds_manager.sync()
    assert len(ds_manager.jobs[-1].output_paths) == 0

    # After sharing: DS should see outputs
    do_manager.job_runner.share_job_results(
        "test_auto_approve.job", share_outputs=True, share_logs=False
    )
    do_manager.sync()
    ds_manager.sync()

    # Verify output
    output_path = ds_manager.jobs[-1].output_paths[0]
    with open(output_path, "r") as f:
        result = json.loads(f.read())

    assert result["result"] == 42
