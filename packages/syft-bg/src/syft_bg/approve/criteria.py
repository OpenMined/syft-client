"""Criteria matching for job approval."""

import hashlib
from pathlib import Path

from syft_job.job import JobInfo

from syft_bg.approve.config import JobApprovalConfig

JOB_METADATA_FILES = {"config.yaml", "run.sh"}


def _get_user_files(job: JobInfo) -> list[Path]:
    """Get all user-submitted files from a job (excluding metadata)."""
    user_files = []
    for f in job.files:
        if f.is_file() and f.name not in JOB_METADATA_FILES:
            user_files.append(f)
        elif f.is_dir():
            for subf in f.rglob("*"):
                if subf.is_file():
                    user_files.append(subf)
    return user_files


def _file_hash_matches(file_path: Path, expected_hash: str) -> bool:
    """Check if file content matches expected hash (sha256:abc123...)."""
    try:
        content = file_path.read_text(encoding="utf-8")
        full_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        if expected_hash.startswith("sha256:"):
            expected = expected_hash[7:]  # strip "sha256:" prefix
        else:
            expected = expected_hash

        # Compare using the length of expected (supports short hashes)
        return full_hash[: len(expected)] == expected
    except Exception:
        return False


def _find_file_by_name(job: JobInfo, filename: str) -> Path | None:
    """Find a file in job by name."""
    for f in _get_user_files(job):
        if f.name == filename:
            return f
    return None


def job_matches_criteria(
    job: JobInfo,
    config: JobApprovalConfig,
    approved_peers: list[str] | None = None,
) -> tuple[bool, str]:
    """
    Check if a job matches all approval criteria.

    Returns:
        (True, "ok") if job matches all criteria
        (False, reason) if job doesn't match
    """
    # Only process inbox jobs
    if job.status != "inbox":
        return (False, f"status is {job.status}, not inbox")

    # Check allowed users
    if config.allowed_users and job.submitted_by not in config.allowed_users:
        return (False, f"user {job.submitted_by} not in allowed_users")

    # Check peers filter
    if config.peers_only:
        if approved_peers is None:
            return (False, "peers_only enabled but no approved_peers provided")
        if job.submitted_by not in approved_peers:
            return (False, f"user {job.submitted_by} is not an approved peer")

    # Check required scripts (hash match)
    for filename, expected_hash in config.required_scripts.items():
        file_path = _find_file_by_name(job, filename)
        if file_path is None:
            return (False, f"required script not found: {filename}")
        if not _file_hash_matches(file_path, expected_hash):
            return (False, f"script hash mismatch: {filename}")

    # Check required filenames exist (exact match when specified)
    if config.required_filenames:
        job_filenames = {f.name for f in _get_user_files(job)}
        required_set = set(config.required_filenames)

        missing_files = required_set - job_filenames
        if missing_files:
            return (
                False,
                f"missing required files: {', '.join(sorted(missing_files))}",
            )

        extra_files = job_filenames - required_set
        if extra_files:
            return (False, f"unexpected files: {', '.join(sorted(extra_files))}")

    return (True, "ok")
