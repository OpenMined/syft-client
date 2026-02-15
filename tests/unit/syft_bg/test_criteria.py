"""Tests for job approval criteria matching."""

import hashlib
from pathlib import Path
from unittest.mock import MagicMock


from syft_bg.approve.config import JobApprovalConfig
from syft_bg.approve.criteria import (
    _file_hash_matches,
    _get_user_files,
    job_matches_criteria,
)


def create_mock_job(
    name: str = "test-job",
    status: str = "inbox",
    submitted_by: str = "user@example.com",
    files: list[Path] | None = None,
):
    """Create a mock JobInfo object."""
    job = MagicMock()
    job.name = name
    job.status = status
    job.submitted_by = submitted_by
    job.files = files or []
    return job


class TestFileHashMatches:
    """Tests for _file_hash_matches function."""

    def test_matching_hash(self, temp_dir):
        """Should return True for matching hash."""
        script = temp_dir / "main.py"
        script.write_text('print("hello")\n')

        # Calculate expected hash
        content = script.read_text()
        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

        assert _file_hash_matches(script, f"sha256:{expected}") is True

    def test_non_matching_hash(self, temp_dir):
        """Should return False for non-matching hash."""
        script = temp_dir / "main.py"
        script.write_text('print("hello")\n')

        assert _file_hash_matches(script, "sha256:wronghash12345") is False

    def test_hash_without_prefix(self, temp_dir):
        """Should work without sha256: prefix."""
        script = temp_dir / "main.py"
        script.write_text('print("hello")\n')

        content = script.read_text()
        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

        assert _file_hash_matches(script, expected) is True

    def test_short_hash(self, temp_dir):
        """Should support short hashes."""
        script = temp_dir / "main.py"
        script.write_text('print("hello")\n')

        content = script.read_text()
        full_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        short_hash = full_hash[:8]  # 8 character hash

        assert _file_hash_matches(script, f"sha256:{short_hash}") is True

    def test_nonexistent_file(self, temp_dir):
        """Should return False for non-existent file."""
        script = temp_dir / "nonexistent.py"
        assert _file_hash_matches(script, "sha256:anything") is False


class TestGetUserFiles:
    """Tests for _get_user_files function."""

    def test_excludes_metadata_files(self, temp_dir):
        """Should exclude config.yaml and run.sh."""
        files = [
            temp_dir / "main.py",
            temp_dir / "config.yaml",
            temp_dir / "run.sh",
            temp_dir / "params.json",
        ]
        for f in files:
            f.write_text("content")

        job = create_mock_job(files=files)
        user_files = _get_user_files(job)

        user_filenames = [f.name for f in user_files]
        assert "main.py" in user_filenames
        assert "params.json" in user_filenames
        assert "config.yaml" not in user_filenames
        assert "run.sh" not in user_filenames


class TestJobMatchesCriteria:
    """Tests for job_matches_criteria function."""

    def test_non_inbox_job_rejected(self):
        """Jobs not in inbox status should be rejected."""
        job = create_mock_job(status="approved")
        config = JobApprovalConfig()

        matches, reason = job_matches_criteria(job, config)

        assert matches is False
        assert "status" in reason

    def test_allowed_users_filter(self):
        """Should filter by allowed_users when set."""
        job = create_mock_job(submitted_by="blocked@example.com")
        config = JobApprovalConfig(
            allowed_users=["allowed@example.com"],
            peers_only=False,
        )

        matches, reason = job_matches_criteria(job, config)

        assert matches is False
        assert "allowed_users" in reason

    def test_allowed_users_accepts_valid(self):
        """Should accept users in allowed_users list."""
        job = create_mock_job(submitted_by="allowed@example.com")
        config = JobApprovalConfig(
            allowed_users=["allowed@example.com"],
            peers_only=False,
        )

        matches, reason = job_matches_criteria(job, config)

        assert matches is True

    def test_peers_only_requires_peer_list(self):
        """peers_only should require approved_peers list."""
        job = create_mock_job()
        config = JobApprovalConfig(peers_only=True)

        matches, reason = job_matches_criteria(job, config, approved_peers=None)

        assert matches is False
        assert "peers_only" in reason

    def test_peers_only_filters_non_peers(self):
        """peers_only should reject non-peer submissions."""
        job = create_mock_job(submitted_by="stranger@example.com")
        config = JobApprovalConfig(peers_only=True)

        matches, reason = job_matches_criteria(
            job, config, approved_peers=["friend@example.com"]
        )

        assert matches is False
        assert "not an approved peer" in reason

    def test_peers_only_accepts_peers(self):
        """peers_only should accept approved peers."""
        job = create_mock_job(submitted_by="friend@example.com")
        config = JobApprovalConfig(peers_only=True)

        matches, reason = job_matches_criteria(
            job, config, approved_peers=["friend@example.com"]
        )

        assert matches is True

    def test_required_filenames_exact_match(self, temp_dir):
        """required_filenames should require exact file set."""
        main_py = temp_dir / "main.py"
        params = temp_dir / "params.json"
        main_py.write_text("code")
        params.write_text("{}")

        job = create_mock_job(files=[main_py, params])
        config = JobApprovalConfig(
            peers_only=False,
            required_filenames=["main.py", "params.json"],
        )

        matches, reason = job_matches_criteria(job, config)
        assert matches is True

    def test_required_filenames_missing_file(self, temp_dir):
        """Should reject if required file is missing."""
        main_py = temp_dir / "main.py"
        main_py.write_text("code")

        job = create_mock_job(files=[main_py])
        config = JobApprovalConfig(
            peers_only=False,
            required_filenames=["main.py", "params.json"],
        )

        matches, reason = job_matches_criteria(job, config)
        assert matches is False
        assert "missing required files" in reason

    def test_required_filenames_extra_file(self, temp_dir):
        """Should reject if unexpected extra file present."""
        main_py = temp_dir / "main.py"
        extra = temp_dir / "malicious.py"
        main_py.write_text("code")
        extra.write_text("bad code")

        job = create_mock_job(files=[main_py, extra])
        config = JobApprovalConfig(
            peers_only=False,
            required_filenames=["main.py"],
        )

        matches, reason = job_matches_criteria(job, config)
        assert matches is False
        assert "unexpected files" in reason

    def test_required_scripts_hash_validation(self, temp_dir):
        """Should validate script content hash."""
        main_py = temp_dir / "main.py"
        content = 'print("hello")\n'
        main_py.write_text(content)

        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

        job = create_mock_job(files=[main_py])
        config = JobApprovalConfig(
            peers_only=False,
            required_scripts={"main.py": f"sha256:{expected_hash}"},
        )

        matches, reason = job_matches_criteria(job, config)
        assert matches is True

    def test_required_scripts_hash_mismatch(self, temp_dir):
        """Should reject on hash mismatch."""
        main_py = temp_dir / "main.py"
        main_py.write_text('print("modified")\n')

        job = create_mock_job(files=[main_py])
        config = JobApprovalConfig(
            peers_only=False,
            required_scripts={"main.py": "sha256:wronghash12345"},
        )

        matches, reason = job_matches_criteria(job, config)
        assert matches is False
        assert "hash mismatch" in reason
