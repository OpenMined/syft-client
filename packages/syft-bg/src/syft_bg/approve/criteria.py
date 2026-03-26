"""Criteria matching for job approval."""

import hashlib
from pathlib import Path

from syft_job.job import JobInfo

from syft_bg.approve.config import AutoApprovalObj, AutoApprovalsConfig

JOB_METADATA_FILES = {"config.yaml", "run.sh"}


def _get_python_files(job: JobInfo) -> list[Path]:
    """Get all .py files from a job (excluding metadata)."""
    py_files = []
    for f in job.files:
        if f.is_file() and f.suffix == ".py" and f.name not in JOB_METADATA_FILES:
            py_files.append(f)
        elif f.is_dir():
            for subf in f.rglob("*.py"):
                if subf.is_file():
                    py_files.append(subf)
    return py_files


def _get_content_matched_files(
    job: JobInfo, approved_rel_paths: set[str]
) -> list[Path]:
    """Get job files whose relative paths appear in the approved set."""
    code_dir = job.code_dir
    matched = []
    if code_dir.exists():
        for f in code_dir.rglob("*"):
            if (
                f.is_file()
                and f.name not in JOB_METADATA_FILES
                and str(f.relative_to(code_dir)) in approved_rel_paths
            ):
                matched.append(f)
    return matched


def _compute_file_hash(file_path: Path) -> str | None:
    """Compute SHA256 hash of a file's content."""
    try:
        content = file_path.read_text(encoding="utf-8")
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
    except Exception:
        return None


def _hash_matches(actual_hash: str, expected_hash: str) -> bool:
    """Check if actual hash matches expected (supports sha256: prefix and short hashes)."""
    if expected_hash.startswith("sha256:"):
        expected = expected_hash[7:]
    else:
        expected = expected_hash
    return actual_hash[: len(expected)] == expected


def _content_matches(job_file: Path, stored_path: str) -> bool:
    """Compare file content against stored copy."""
    try:
        stored = Path(stored_path).expanduser()
        if not stored.exists():
            return False
        return job_file.read_text(encoding="utf-8") == stored.read_text(
            encoding="utf-8"
        )
    except Exception:
        return False


def _get_all_job_code_files(job: JobInfo) -> dict[str, Path]:
    """Get all user files from a job as {relative_path: abs_path} (excluding metadata)."""
    code_dir = job.code_dir
    files: dict[str, Path] = {}
    if code_dir.exists():
        for f in code_dir.rglob("*"):
            if f.is_file() and f.name not in JOB_METADATA_FILES:
                files[str(f.relative_to(code_dir))] = f
    return files


def _get_error_message_for_file_mismatch(
    expected_filenames: set[str], actual_filenames: set[str]
) -> str:
    error_msg = ""
    if expected_filenames - actual_filenames:
        error_msg += f"missing files: {expected_filenames - actual_filenames}\n"
    if actual_filenames - expected_filenames:
        error_msg += f"extra files: {actual_filenames - expected_filenames}\n"
    return f"job files do not match expected filenames: {error_msg}"


def _validate_job_against_object(
    job: JobInfo, obj: AutoApprovalObj
) -> tuple[bool, str]:
    """Validate a job against a single AutoApprovalObj.

    Two-step validation for each content-matched file:
    1. Hash must match a file entry in the object
    2. Content must match the stored copy

    All other files must be in the file_names allowlist.

    Returns:
        (True, "ok") if all files pass
        (False, reason) if any file fails
    """
    # Build lookup: relative_path → FileEntry (content-matched files)
    expected_contents = {
        entry.relative_path: entry for entry in obj.file_contents
    }
    expected_names = set(obj.file_names)
    all_expected_paths = set(expected_contents.keys()) | expected_names
    job_code_files = _get_all_job_code_files(job)

    if all_expected_paths != set(job_code_files.keys()):
        error_msg = _get_error_message_for_file_mismatch(
            all_expected_paths, set(job_code_files.keys())
        )
        return (False, error_msg)

    for rel_path, file_entry in expected_contents.items():
        expected_hash = file_entry.hash
        expected_path = file_entry.path
        job_file = job_code_files.get(rel_path)
        if job_file is None:
            return (False, f"unapproved file: {rel_path}")
        submitted_hash = _compute_file_hash(job_file)
        if submitted_hash is None:
            return (False, f"could not read file: {rel_path}")
        if not _hash_matches(submitted_hash, expected_hash):
            return (
                False,
                f"file hash mismatch for {rel_path}: expected {expected_hash}, got sha256:{submitted_hash}",
            )
        if not _content_matches(job_file, expected_path):
            return (
                False,
                f"file content mismatch for {rel_path} against stored copy",
            )

    return (True, "ok")


def resolve_auto_approval(
    job: JobInfo, config: AutoApprovalsConfig
) -> tuple[bool, str]:
    """Find matching auto-approval objects for a job and validate.

    Searches all objects where the peer is listed (or peers is empty = any peer).
    Any matching object wins.

    Returns:
        (True, "ok") if job passes any object's criteria
        (False, reason) if job fails all
    """
    if job.status != "pending":
        return (False, f"status is {job.status}, not pending")

    # Find objects where this peer is allowed
    candidate_objects: list[tuple[str, AutoApprovalObj]] = []
    for name, obj in config.objects.items():
        if not obj.peers or job.submitted_by in obj.peers:
            candidate_objects.append((name, obj))

    if not candidate_objects:
        return (False, f"no auto-approval objects match peer: {job.submitted_by}")

    # Try each candidate — any match wins
    last_reason = ""
    for name, obj in candidate_objects:
        matches, reason = _validate_job_against_object(job, obj)
        if matches:
            return (True, "ok")
        last_reason = f"[{name}] {reason}"

    return (False, last_reason)
