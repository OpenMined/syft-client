import json
from pathlib import Path

from syft_job.client import JobInfo

from syft_approve.core.config import JobApprovalConfig

JOB_METADATA_FILES = {"config.yaml", "run.sh"}


def _get_non_empty_lines(content: str) -> list[str]:
    return [line for line in content.splitlines() if line.strip()]


def _get_user_files(job: JobInfo) -> list[Path]:
    user_files = []
    for f in job.files:
        if f.is_file() and f.name not in JOB_METADATA_FILES:
            user_files.append(f)
        elif f.is_dir():
            for subf in f.rglob("*"):
                if subf.is_file():
                    user_files.append(subf)
    return user_files


def _file_content_matches(file_path: Path, expected_content: str) -> bool:
    try:
        actual = file_path.read_text(encoding="utf-8")
        return _get_non_empty_lines(actual) == _get_non_empty_lines(expected_content)
    except Exception:
        return False


def _find_file_by_name(job: JobInfo, filename: str) -> Path | None:
    for f in _get_user_files(job):
        if f.name == filename:
            return f
    return None


def _json_has_required_keys(
    file_path: Path, required_keys: list[str]
) -> tuple[bool, list[str]]:
    try:
        with open(file_path) as f:
            data = json.load(f)
        missing = [k for k in required_keys if k not in data]
        return (len(missing) == 0, missing)
    except json.JSONDecodeError:
        return (False, ["<invalid JSON>"])
    except Exception:
        return (False, required_keys)


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

    # Check required scripts (exact content match)
    for filename, expected_content in config.required_scripts.items():
        file_path = _find_file_by_name(job, filename)
        if file_path is None:
            return (False, f"required script not found: {filename}")
        if not _file_content_matches(file_path, expected_content):
            return (False, f"script content mismatch: {filename}")

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

    # Check required JSON keys
    for filename, required_keys in config.required_json_keys.items():
        file_path = _find_file_by_name(job, filename)
        if file_path is None:
            return (False, f"JSON file not found: {filename}")

        has_keys, missing_keys = _json_has_required_keys(file_path, required_keys)
        if not has_keys:
            return (False, f"missing keys in {filename}: {', '.join(missing_keys)}")

    return (True, "ok")
