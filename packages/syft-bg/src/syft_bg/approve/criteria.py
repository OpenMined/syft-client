"""Criteria matching for job approval."""

import hashlib
from pathlib import Path

from syft_job.job import JobInfo

from syft_bg.approve.config import JobApprovalConfig, PeerApprovalEntry

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


def validate_approved_scripts(
    job: JobInfo, peer_config: PeerApprovalEntry
) -> tuple[bool, str]:
    """Validate that all submitted .py files are approved for this peer.

    Validates every .py file against the peer's approved scripts list:
    - Unapproved filename → reject
    - Hash mismatch → reject
    - Subset of approved scripts → pass

    Returns:
        (True, "ok") if job passes
        (False, reason) if job fails
    """
    if job.status != "inbox":
        return (False, f"status is {job.status}, not inbox")

    py_files = _get_python_files(job)

    if len(py_files) == 0:
        return (False, "no Python files found in submission")

    # Build lookup: filename → expected hash
    approved = {rule.name: rule.hash for rule in peer_config.scripts}

    for py_file in py_files:
        if py_file.name not in approved:
            return (False, f"unapproved file: {py_file.name}")

        actual_hash = _compute_file_hash(py_file)
        if actual_hash is None:
            return (False, f"could not read file: {py_file.name}")

        if not _hash_matches(actual_hash, approved[py_file.name]):
            return (
                False,
                f"script hash mismatch for {py_file.name}: "
                f"expected {approved[py_file.name]}, got sha256:{actual_hash}",
            )

    return (True, "ok")


# Backwards-compatible alias
strict_mode_check = validate_approved_scripts


def resolve_peer_criteria(job: JobInfo, config: JobApprovalConfig) -> tuple[bool, str]:
    """Look up peer config and check job against it.

    Returns:
        (True, "ok") if job passes criteria
        (False, reason) if job fails
    """
    if job.status != "inbox":
        return (False, f"status is {job.status}, not inbox")

    if job.submitted_by not in config.peers:
        return (False, f"unknown peer: {job.submitted_by}")

    peer_config = config.peers[job.submitted_by]

    if peer_config.mode == "strict":
        return validate_approved_scripts(job, peer_config)

    return (False, f"unknown mode: {peer_config.mode}")
