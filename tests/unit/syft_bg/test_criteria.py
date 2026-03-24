"""Tests for job approval criteria matching."""

import hashlib
from pathlib import Path
from unittest.mock import MagicMock

from syft_bg.approve.config import AutoApprovalObj, AutoApprovalsConfig, ScriptEntry
from syft_bg.approve.criteria import (
    _compute_file_hash,
    _content_matches,
    _get_python_files,
    _hash_matches,
    _validate_against_object,
    resolve_auto_approval,
)


def _make_script_entry(name, content, stored_path):
    """Helper to create a ScriptEntry with correct hash and stored copy."""
    script_hash = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
    # Write stored copy
    Path(stored_path).parent.mkdir(parents=True, exist_ok=True)
    Path(stored_path).write_text(content)
    return ScriptEntry(name=name, path=str(stored_path), hash=script_hash)


def create_mock_job(
    name: str = "test-job",
    status: str = "pending",
    submitted_by: str = "alice@test.com",
    files: list[Path] | None = None,
):
    """Create a mock JobInfo object."""
    job = MagicMock()
    job.name = name
    job.status = status
    job.submitted_by = submitted_by
    job.files = files or []
    return job


class TestGetPythonFiles:
    """Tests for _get_python_files."""

    def test_finds_py_files(self, temp_dir):
        main_py = temp_dir / "main.py"
        main_py.write_text("code")
        config_yaml = temp_dir / "config.yaml"
        config_yaml.write_text("config")
        run_sh = temp_dir / "run.sh"
        run_sh.write_text("#!/bin/bash")
        params = temp_dir / "params.json"
        params.write_text("{}")

        job = create_mock_job(files=[main_py, config_yaml, run_sh, params])
        py_files = _get_python_files(job)

        assert len(py_files) == 1
        assert py_files[0].name == "main.py"

    def test_excludes_non_py(self, temp_dir):
        params = temp_dir / "params.json"
        params.write_text("{}")
        job = create_mock_job(files=[params])
        assert _get_python_files(job) == []

    def test_multiple_py_files(self, temp_dir):
        a = temp_dir / "main.py"
        b = temp_dir / "extra.py"
        a.write_text("a")
        b.write_text("b")
        job = create_mock_job(files=[a, b])
        assert len(_get_python_files(job)) == 2


class TestComputeFileHash:
    """Tests for _compute_file_hash."""

    def test_hash_matches_manual(self, temp_dir):
        script = temp_dir / "main.py"
        content = 'print("hello")\n'
        script.write_text(content)
        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert _compute_file_hash(script) == expected

    def test_nonexistent_file(self, temp_dir):
        assert _compute_file_hash(temp_dir / "nope.py") is None


class TestHashMatches:
    """Tests for _hash_matches."""

    def test_full_hash_match(self):
        h = "abc123def456"
        assert _hash_matches(h, f"sha256:{h}") is True

    def test_full_hash_mismatch(self):
        assert _hash_matches("abc123", "sha256:zzz999") is False

    def test_short_hash(self):
        full = "abc123def456"
        assert _hash_matches(full, "sha256:abc123") is True

    def test_without_prefix(self):
        h = "abc123def456"
        assert _hash_matches(h, h) is True


class TestContentMatches:
    """Tests for _content_matches."""

    def test_matching_content(self, temp_dir):
        content = 'print("hello")\n'
        job_file = temp_dir / "main.py"
        stored = temp_dir / "stored" / "main.py"
        job_file.write_text(content)
        stored.parent.mkdir(parents=True)
        stored.write_text(content)
        assert _content_matches(job_file, str(stored)) is True

    def test_mismatched_content(self, temp_dir):
        job_file = temp_dir / "main.py"
        stored = temp_dir / "stored" / "main.py"
        job_file.write_text('print("a")\n')
        stored.parent.mkdir(parents=True)
        stored.write_text('print("b")\n')
        assert _content_matches(job_file, str(stored)) is False

    def test_missing_stored_file(self, temp_dir):
        job_file = temp_dir / "main.py"
        job_file.write_text("code")
        assert _content_matches(job_file, "/nonexistent/main.py") is False


class TestValidateAgainstObject:
    """Tests for _validate_against_object."""

    def test_single_file_pass(self, temp_dir):
        content = 'print("hello")\n'
        script = temp_dir / "main.py"
        script.write_text(content)
        stored = temp_dir / "stored" / "main.py"
        entry = _make_script_entry("main.py", content, stored)
        obj = AutoApprovalObj(scripts=[entry])
        job = create_mock_job(files=[script])

        ok, reason = _validate_against_object(job, obj)
        assert ok is True
        assert reason == "ok"

    def test_no_py_files(self, temp_dir):
        params = temp_dir / "params.json"
        params.write_text("{}")
        stored = temp_dir / "stored" / "main.py"
        entry = _make_script_entry("main.py", "code", stored)
        obj = AutoApprovalObj(scripts=[entry])
        job = create_mock_job(files=[params])

        ok, reason = _validate_against_object(job, obj)
        assert ok is False
        assert "no Python files" in reason

    def test_multiple_files_all_match(self, temp_dir):
        content_a = 'print("a")\n'
        content_b = 'print("b")\n'
        a = temp_dir / "main.py"
        b = temp_dir / "utils.py"
        a.write_text(content_a)
        b.write_text(content_b)
        stored_a = temp_dir / "stored" / "main.py"
        stored_b = temp_dir / "stored" / "utils.py"
        entry_a = _make_script_entry("main.py", content_a, stored_a)
        entry_b = _make_script_entry("utils.py", content_b, stored_b)
        obj = AutoApprovalObj(scripts=[entry_a, entry_b])
        job = create_mock_job(files=[a, b])

        ok, reason = _validate_against_object(job, obj)
        assert ok is True

    def test_unapproved_file(self, temp_dir):
        content = 'print("a")\n'
        a = temp_dir / "main.py"
        b = temp_dir / "extra.py"
        a.write_text(content)
        b.write_text("extra")
        stored = temp_dir / "stored" / "main.py"
        entry = _make_script_entry("main.py", content, stored)
        obj = AutoApprovalObj(scripts=[entry])
        job = create_mock_job(files=[a, b])

        ok, reason = _validate_against_object(job, obj)
        assert ok is False
        assert "unapproved file" in reason

    def test_hash_mismatch(self, temp_dir):
        a = temp_dir / "main.py"
        a.write_text('print("modified")\n')
        stored = temp_dir / "stored" / "main.py"
        stored.parent.mkdir(parents=True)
        stored.write_text('print("modified")\n')
        entry = ScriptEntry(name="main.py", path=str(stored), hash="sha256:wronghash")
        obj = AutoApprovalObj(scripts=[entry])
        job = create_mock_job(files=[a])

        ok, reason = _validate_against_object(job, obj)
        assert ok is False
        assert "hash mismatch" in reason

    def test_content_mismatch(self, temp_dir):
        content = 'print("hello")\n'
        a = temp_dir / "main.py"
        a.write_text(content)
        # Stored copy has different content but we give the correct hash
        stored = temp_dir / "stored" / "main.py"
        stored.parent.mkdir(parents=True)
        stored.write_text('print("different")\n')
        script_hash = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
        entry = ScriptEntry(name="main.py", path=str(stored), hash=script_hash)
        obj = AutoApprovalObj(scripts=[entry])
        job = create_mock_job(files=[a])

        ok, reason = _validate_against_object(job, obj)
        assert ok is False
        assert "content mismatch" in reason


class TestResolveAutoApproval:
    """Tests for resolve_auto_approval."""

    def test_non_pending_rejected(self):
        job = create_mock_job(status="approved")
        config = AutoApprovalsConfig()
        ok, reason = resolve_auto_approval(job, config)
        assert ok is False
        assert "status" in reason

    def test_no_matching_objects(self):
        job = create_mock_job(submitted_by="unknown@test.com")
        config = AutoApprovalsConfig(
            objects={
                "obj1": AutoApprovalObj(scripts=[], peers=["someone_else@test.com"]),
            }
        )
        ok, reason = resolve_auto_approval(job, config)
        assert ok is False
        assert "no auto-approval objects match peer" in reason

    def test_peer_in_object_passes(self, temp_dir):
        content = 'print("hello")\n'
        script = temp_dir / "main.py"
        script.write_text(content)
        stored = temp_dir / "stored" / "main.py"
        entry = _make_script_entry("main.py", content, stored)
        config = AutoApprovalsConfig(
            objects={
                "analysis": AutoApprovalObj(scripts=[entry], peers=["alice@test.com"]),
            }
        )
        job = create_mock_job(submitted_by="alice@test.com", files=[script])
        ok, reason = resolve_auto_approval(job, config)
        assert ok is True

    def test_empty_peers_matches_any(self, temp_dir):
        content = 'print("hello")\n'
        script = temp_dir / "main.py"
        script.write_text(content)
        stored = temp_dir / "stored" / "main.py"
        entry = _make_script_entry("main.py", content, stored)
        config = AutoApprovalsConfig(
            objects={
                "open": AutoApprovalObj(scripts=[entry], peers=[]),
            }
        )
        job = create_mock_job(submitted_by="anyone@test.com", files=[script])
        ok, reason = resolve_auto_approval(job, config)
        assert ok is True

    def test_filename_mismatch(self, temp_dir):
        script = temp_dir / "train.py"
        script.write_text('print("hello")\n')
        stored = temp_dir / "stored" / "main.py"
        entry = _make_script_entry("main.py", 'print("hello")\n', stored)
        config = AutoApprovalsConfig(
            objects={
                "obj": AutoApprovalObj(scripts=[entry], peers=["alice@test.com"]),
            }
        )
        job = create_mock_job(submitted_by="alice@test.com", files=[script])
        ok, reason = resolve_auto_approval(job, config)
        assert ok is False
        assert "unapproved file" in reason
