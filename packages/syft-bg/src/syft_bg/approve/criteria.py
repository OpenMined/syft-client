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


def _validate_against_object(job: JobInfo, obj: AutoApprovalObj) -> tuple[bool, str]:
    """Validate a job against a single AutoApprovalObj.

    Two-step validation for each .py file:
    1. Hash must match a script entry in the object
    2. Content must match the stored copy

    Non-.py files are checked against file_names allowlist.

    Returns:
        (True, "ok") if all files pass
        (False, reason) if any file fails
    """
    py_files = _get_python_files(job)

    if len(py_files) == 0:
        return (False, "no Python files found in submission")

    # Build lookup: filename → ScriptEntry
    approved = {entry.name: entry for entry in obj.scripts}

    for py_file in py_files:
        if py_file.name not in approved:
            return (False, f"unapproved file: {py_file.name}")

        actual_hash = _compute_file_hash(py_file)
        if actual_hash is None:
            return (False, f"could not read file: {py_file.name}")

        script_entry = approved[py_file.name]

        if not _hash_matches(actual_hash, script_entry.hash):
            return (
                False,
                f"script hash mismatch for {py_file.name}: "
                f"expected {script_entry.hash}, got sha256:{actual_hash}",
            )

        if not _content_matches(py_file, script_entry.path):
            return (
                False,
                f"script content mismatch for {py_file.name} against stored copy",
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
        matches, reason = _validate_against_object(job, obj)
        if matches:
            return (True, "ok")
        last_reason = f"[{name}] {reason}"

    return (False, last_reason)
