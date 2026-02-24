"""
Job auto-approval utilities for automatically approving jobs that match specific criteria.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from syft_job.job import JobInfo

if TYPE_CHECKING:
    from syft_client.sync.syftbox_manager import SyftboxManager


def _get_non_empty_lines(content: str) -> list[str]:
    """Get non-empty lines from content."""
    return [line for line in content.splitlines() if line.strip()]


def _file_content_matches(file_path: Path, expected_content: str) -> bool:
    """
    Check if file content matches expected content (comparing non-empty lines only).

    Args:
        file_path: Path to the file to check
        expected_content: Expected file content

    Returns:
        True if content matches, False otherwise
    """
    try:
        actual = file_path.read_text(encoding="utf-8")
        return _get_non_empty_lines(actual) == _get_non_empty_lines(expected_content)
    except Exception:
        return False


JOB_METADATA_FILES = {"config.yaml", "run.sh"}


def _get_user_files(job: JobInfo) -> list[Path]:
    """
    Get user-submitted files in job folder, excluding job metadata files.

    Args:
        job: JobInfo object

    Returns:
        List of user file paths
    """
    user_files = []
    for f in job.files:
        if f.is_file() and f.name not in JOB_METADATA_FILES:
            user_files.append(f)
        elif f.is_dir():
            for subf in f.rglob("*"):
                if subf.is_file():
                    user_files.append(subf)
    return user_files


def _has_file_with_name(job: JobInfo, filename: str) -> bool:
    """
    Check if job folder contains a file with the given name (recursive).

    Args:
        job: JobInfo object
        filename: Name of file to look for

    Returns:
        True if file exists, False otherwise
    """
    return any(f.name == filename for f in _get_user_files(job))


def _script_matches(job: JobInfo, filename: str, expected_content: str) -> bool:
    """
    Check if job contains a file with the given name and matching content (recursive).

    Args:
        job: JobInfo object
        filename: Name of the script file to check
        expected_content: Expected script content

    Returns:
        True if file exists and content matches, False otherwise
    """
    for f in _get_user_files(job):
        if f.name == filename:
            return _file_content_matches(f, expected_content)
    return False


def job_matches_criteria(
    job: JobInfo,
    required_scripts: Dict[str, str],
    required_filenames: List[str],
    allowed_users: Optional[List[str]] = None,
    peers_only: bool = False,
    approved_peers: Optional[List[str]] = None,
) -> bool:
    """
    Check if a job matches all the auto-approval criteria.

    Args:
        job: JobInfo object to check
        required_scripts: Dict mapping filename to expected content
        required_filenames: List of filenames that must exist
        allowed_users: Optional list of allowed user emails
        peers_only: If True, only approve jobs from approved peers
        approved_peers: List of approved peer emails (required when peers_only=True)

    Returns:
        True if job matches all criteria, False otherwise
    """
    # Check status - only process inbox jobs
    if job.status != "inbox":
        return False

    # Check allowed users filter
    if allowed_users is not None and job.submitted_by not in allowed_users:
        return False

    # Check peers filter
    if peers_only:
        if approved_peers is None:
            return False
        if job.submitted_by not in approved_peers:
            return False

    # Check for all required scripts with exact content match
    for filename, expected_content in required_scripts.items():
        if not _script_matches(job, filename, expected_content):
            return False

    # Check that job contains exactly the required files (no more, no less)
    job_filenames = {f.name for f in _get_user_files(job)}
    required_set = set(required_filenames)
    if job_filenames != required_set:
        return False

    return True


def auto_approve_and_run_jobs(
    client: SyftboxManager,
    *,
    required_scripts: Dict[str, str],
    required_filenames: List[str],
    allowed_users: Optional[List[str]] = None,
    peers_only: bool = False,
    on_approve: Optional[Callable[[JobInfo], None]] = None,
    verbose: bool = True,
) -> List[JobInfo]:
    """
    Auto-approve and run jobs that match specific criteria.

    This function scans through jobs, approves those that match, and runs them.
    It approves jobs that:
    1. Are in "inbox" status
    2. Contain all specified script files with exact content match
    3. Contain all required files (by filename)
    4. (Optional) Were submitted by an allowed user
    5. (Optional) Were submitted by an approved peer

    Args:
        client: SyftboxManager instance
        required_scripts: Dict mapping filename to expected content.
                         Content is compared after stripping trailing whitespace.
                         Example: {"main.py": "print('hello')"}
        required_filenames: List of filenames that must exist in job folder.
                           Example: ["config.json", "data.csv"]
        allowed_users: Optional list of email addresses allowed to submit jobs.
                      If None, any user is allowed (subject to peers_only).
        peers_only: If True, only approve jobs from approved peers.
        on_approve: Optional callback invoked for each approved job.
        verbose: If True, print status messages during approval.

    Returns:
        List of JobInfo objects that were approved.

    Example:
        >>> from syft_client.sync.syftbox_manager import SyftboxManager
        >>> client = SyftboxManager.for_jupyter(email="me@example.com", ...)
        >>> approved = auto_approve_and_run_jobs(
        ...     client,
        ...     required_scripts={"main.py": EXPECTED_SCRIPT},
        ...     required_filenames=["params.json"],
        ...     peers_only=True,
        ... )
    """
    # Get approved peers if filtering by peers
    approved_peers = None
    if peers_only:
        client.load_peers()
        approved_peers = [p.email for p in client._approved_peers]

    approved_jobs = []
    jobs = client.jobs

    for job in jobs:
        if job_matches_criteria(
            job,
            required_scripts=required_scripts,
            required_filenames=required_filenames,
            allowed_users=allowed_users,
            peers_only=peers_only,
            approved_peers=approved_peers,
        ):
            try:
                job.approve()
                approved_jobs.append(job)

                if on_approve is not None:
                    on_approve(job)

            except Exception as e:
                if verbose:
                    print(f"Failed to approve job '{job.name}': {e}")

    # Run all approved jobs
    if approved_jobs:
        client.process_approved_jobs(stream_output=verbose)

    return approved_jobs
