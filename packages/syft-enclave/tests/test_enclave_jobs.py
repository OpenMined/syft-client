import os
import random
import tempfile
from pathlib import Path

os.environ["PRE_SYNC"] = "false"

from syft_enclaves import SyftEnclaveClient


def create_tmp_dataset_files(prefix=""):
    tmp_dir = (
        Path(tempfile.mkdtemp())
        / f"syft-job-test-{prefix}-{random.randint(1, 1000000)}"
    )
    tmp_dir.mkdir(parents=True, exist_ok=True)
    mock_path = tmp_dir / "mock.txt"
    private_path = tmp_dir / "private.txt"
    mock_path.write_text(f"mock data {prefix}")
    private_path.write_text(f"private data {prefix}")
    return mock_path, private_path


JOB_CODE = """\
import json
import syft_client as sc

data_path_1 = sc.resolve_dataset_file_path("dataset1")
data_path_2 = sc.resolve_dataset_file_path("dataset2")

with open(data_path_1, "r") as f:
    data1 = f.read()

with open(data_path_2, "r") as f:
    data2 = f.read()

result = {"total_length": len(data1) + len(data2)}

with open("outputs/result.json", "w") as f:
    f.write(json.dumps(result))
"""


def create_tmp_code_file():
    tmp_dir = Path(tempfile.mkdtemp()) / f"syft-job-code-{random.randint(1, 1000000)}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    code_path = tmp_dir / "main.py"
    code_path.write_text(JOB_CODE)
    return str(code_path)


def test_enclave_job_distribution():
    """Test full flow: DS submits job to enclave, enclave distributes to DOs."""
    enclave, do1, do2, ds = SyftEnclaveClient.quad_with_mock_drive_service_connection(
        use_in_memory_cache=False,
    )

    # DO1 creates dataset1
    mock1, private1 = create_tmp_dataset_files("ds1")
    do1.create_dataset(
        name="dataset1",
        mock_path=mock1,
        private_path=private1,
        summary="Dataset 1",
        users=[ds.email],
        upload_private=True,
        sync=False,
    )

    # DO2 creates dataset2
    mock2, private2 = create_tmp_dataset_files("ds2")
    do2.create_dataset(
        name="dataset2",
        mock_path=mock2,
        private_path=private2,
        summary="Dataset 2",
        users=[ds.email],
        upload_private=True,
        sync=False,
    )

    # DOs share private datasets with enclave
    do1.share_private_dataset("dataset1", enclave.email)
    do2.share_private_dataset("dataset2", enclave.email)

    # Sync all — DS sees mock datasets
    do1.sync()
    do2.sync()
    ds.sync()
    ds_datasets = ds.datasets.get_all()
    assert len(ds_datasets) == 2

    # DS submits job to enclave
    code_path = create_tmp_code_file()
    ds.submit_python_job(
        enclave.email,
        code_path,
        "test_job",
        datasets={do1.email: ["dataset1"], do2.email: ["dataset2"]},
    )

    # Enclave syncs to receive job files from DS
    enclave.sync()

    # Enclave distributes job to DOs
    enclave.receive_jobs()

    # DOs sync to receive forwarded job files
    do1.sync()
    do2.sync()

    # Assert DOs received the job
    do1_jobs = do1.jobs
    assert len(do1_jobs) >= 1
    do1_job_names = [j.name for j in do1_jobs]
    assert "test_job" in do1_job_names

    do2_jobs = do2.jobs
    assert len(do2_jobs) >= 1
    do2_job_names = [j.name for j in do2_jobs]
    assert "test_job" in do2_job_names


def test_enclave_job_approval_flow():
    """Test: enclave receives job, distributes to DOs, both approve, enclave sees approved."""
    enclave, do1, do2, ds = SyftEnclaveClient.quad_with_mock_drive_service_connection(
        use_in_memory_cache=False,
    )

    # DOs create datasets
    mock1, private1 = create_tmp_dataset_files("do1")
    do1.create_dataset(
        name="dataset1",
        mock_path=mock1,
        private_path=private1,
        summary="Dataset 1",
        users=[ds.email],
        upload_private=True,
        sync=False,
    )
    mock2, private2 = create_tmp_dataset_files("do2")
    do2.create_dataset(
        name="dataset2",
        mock_path=mock2,
        private_path=private2,
        summary="Dataset 2",
        users=[ds.email],
        upload_private=True,
        sync=False,
    )
    do1.share_private_dataset("dataset1", enclave.email)
    do2.share_private_dataset("dataset2", enclave.email)
    do1.sync()
    do2.sync()
    ds.sync()

    # DS submits job to enclave
    code_path = create_tmp_code_file()
    ds.submit_python_job(
        enclave.email,
        code_path,
        "test_job",
        datasets={do1.email: ["dataset1"], do2.email: ["dataset2"]},
    )

    # Enclave receives and distributes
    enclave.sync()
    enclave.receive_jobs()

    # Verify approval files were created on enclave
    enclave_job = enclave.jobs["test_job"]
    review_dir = enclave_job.job_review_path
    assert (review_dir / f"{do1.email}_approval_state.json").exists()
    assert (review_dir / f"{do2.email}_approval_state.json").exists()
    assert enclave_job.status == "pending"
    assert enclave_job.job_headers["job_type"] == "enclave"

    # DOs sync to see the job
    do1.sync()
    do2.sync()

    # DO1 approves
    do1_job = do1.jobs["test_job"]
    assert do1_job.job_headers["job_type"] == "enclave"
    assert do1_job.status == "pending"
    do1.approve_job(do1_job)

    # After DO1 approves but before DO2, enclave still sees pending
    enclave.sync()
    enclave_job = enclave.jobs["test_job"]
    assert enclave_job.status == "pending"

    # DO2 approves
    do2_job = do2.jobs["test_job"]
    do2.approve_job(do2_job)

    # Enclave syncs and sees both approved
    enclave.sync()
    enclave_job = enclave.jobs["test_job"]
    assert enclave_job.status == "approved"
