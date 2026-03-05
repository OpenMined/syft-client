"""Tests for SyftDatasetManager and JobsList repr and indexing."""

import pytest

from syft_client.sync.syftbox_manager import SyftboxManager
from syft_job.job import JobInfo, JobsList
from tests.unit.utils import create_tmp_dataset_files


def _create_manager_with_dataset():
    """Create a pair of managers and a dataset, return (ds_manager, do_manager, dataset)."""
    ds_manager, do_manager = SyftboxManager.pair_with_mock_drive_service_connection(
        use_in_memory_cache=False,
        sync_automatically=False,
    )
    mock_path, private_path, readme_path = create_tmp_dataset_files()
    dataset = do_manager.create_dataset(
        name="test-dataset",
        mock_path=mock_path,
        private_path=private_path,
        summary="A test dataset",
    )
    return ds_manager, do_manager, dataset


# --- SyftDatasetManager tests ---


def test_dataset_manager_getitem_str():
    _, do_manager, dataset = _create_manager_with_dataset()
    result = do_manager.datasets["test-dataset"]
    assert result.name == "test-dataset"


def test_dataset_manager_getitem_int():
    _, do_manager, dataset = _create_manager_with_dataset()
    result = do_manager.datasets[0]
    assert result.name == "test-dataset"


def test_dataset_manager_getitem_int_out_of_range():
    _, do_manager, _ = _create_manager_with_dataset()
    with pytest.raises(IndexError):
        do_manager.datasets[99]


def test_dataset_manager_len():
    _, do_manager, _ = _create_manager_with_dataset()
    assert len(do_manager.datasets) == 1


def test_dataset_manager_iter():
    _, do_manager, _ = _create_manager_with_dataset()
    datasets = list(do_manager.datasets)
    assert len(datasets) == 1
    assert datasets[0].name == "test-dataset"


def test_dataset_manager_repr():
    _, do_manager, _ = _create_manager_with_dataset()
    r = repr(do_manager.datasets)
    assert "SyftDatasetManager" in r
    assert "1 datasets" in r


def test_dataset_manager_repr_html():
    _, do_manager, _ = _create_manager_with_dataset()
    html = do_manager.datasets._repr_html_()
    assert html is not None


# --- JobsList tests ---


def _make_job_info(name: str, status: str = "inbox") -> JobInfo:
    """Create a minimal JobInfo for testing."""
    from pathlib import Path

    from syft_job.client import JobClient
    from syft_job.config import SyftJobConfig

    config = SyftJobConfig(syftbox_folder=Path("/tmp/fake"), email="test@test.com")
    client = JobClient(config=config)
    return JobInfo(
        name=name,
        datasite_owner_email="test@test.com",
        status=status,
        submitted_by="ds@test.com",
        location=Path("/tmp/fake/job"),
        client=client,
        current_user_email="test@test.com",
    )


def test_jobs_list_getitem_int():
    jobs = JobsList(
        [_make_job_info("job-a"), _make_job_info("job-b")],
        root_email="test@test.com",
    )
    assert jobs[0].name == "job-a"
    assert jobs[1].name == "job-b"


def test_jobs_list_getitem_str():
    jobs = JobsList(
        [_make_job_info("job-a"), _make_job_info("job-b")],
        root_email="test@test.com",
    )
    assert jobs["job-b"].name == "job-b"


def test_jobs_list_getitem_str_not_found():
    jobs = JobsList(
        [_make_job_info("job-a")],
        root_email="test@test.com",
    )
    with pytest.raises(ValueError, match="not found"):
        jobs["nonexistent"]


def test_jobs_list_getitem_invalid_type():
    jobs = JobsList(
        [_make_job_info("job-a")],
        root_email="test@test.com",
    )
    with pytest.raises(TypeError):
        jobs[3.14]
