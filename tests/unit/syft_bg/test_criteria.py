"""Tests for job approval criteria matching."""

import hashlib
from pathlib import Path
from unittest.mock import MagicMock

from syft_bg.approve.config import JobApprovalConfig, PeerApprovalEntry, ScriptRule
from syft_bg.approve.criteria import (
    _compute_file_hash,
    _get_python_files,
    _hash_matches,
    resolve_peer_criteria,
    validate_approved_scripts,
)


def create_mock_job(
    name: str = "test-job",
    status: str = "inbox",
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


def _make_script_rule(name="main.py", content='print("hello")\n'):
    """Helper to create a ScriptRule with the correct hash."""
    script_hash = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
    return ScriptRule(name=name, hash=script_hash)


class TestValidateApprovedScripts:
    """Tests for validate_approved_scripts."""

    def _make_peer_config(self, *rules):
        return PeerApprovalEntry(mode="strict", scripts=list(rules))

    def test_single_file_pass(self, temp_dir):
        content = 'print("hello")\n'
        script = temp_dir / "main.py"
        script.write_text(content)
        rule = _make_script_rule("main.py", content)
        peer_config = self._make_peer_config(rule)
        job = create_mock_job(files=[script])

        ok, reason = validate_approved_scripts(job, peer_config)
        assert ok is True
        assert reason == "ok"

    def test_non_inbox_rejected(self, temp_dir):
        script = temp_dir / "main.py"
        script.write_text("code")
        job = create_mock_job(status="approved", files=[script])
        peer_config = self._make_peer_config(_make_script_rule())
        ok, reason = validate_approved_scripts(job, peer_config)
        assert ok is False
        assert "status" in reason

    def test_no_py_files(self, temp_dir):
        params = temp_dir / "params.json"
        params.write_text("{}")
        job = create_mock_job(files=[params])
        peer_config = self._make_peer_config(_make_script_rule())
        ok, reason = validate_approved_scripts(job, peer_config)
        assert ok is False
        assert "no Python files" in reason

    def test_multiple_files_all_match(self, temp_dir):
        content_a = 'print("a")\n'
        content_b = 'print("b")\n'
        a = temp_dir / "main.py"
        b = temp_dir / "utils.py"
        a.write_text(content_a)
        b.write_text(content_b)
        rule_a = _make_script_rule("main.py", content_a)
        rule_b = _make_script_rule("utils.py", content_b)
        peer_config = self._make_peer_config(rule_a, rule_b)
        job = create_mock_job(files=[a, b])

        ok, reason = validate_approved_scripts(job, peer_config)
        assert ok is True
        assert reason == "ok"

    def test_subset_of_approved(self, temp_dir):
        content_a = 'print("a")\n'
        content_b = 'print("b")\n'
        a = temp_dir / "main.py"
        a.write_text(content_a)
        rule_a = _make_script_rule("main.py", content_a)
        rule_b = _make_script_rule("utils.py", content_b)
        peer_config = self._make_peer_config(rule_a, rule_b)
        job = create_mock_job(files=[a])

        ok, reason = validate_approved_scripts(job, peer_config)
        assert ok is True
        assert reason == "ok"

    def test_one_unapproved_file(self, temp_dir):
        content = 'print("a")\n'
        a = temp_dir / "main.py"
        b = temp_dir / "extra.py"
        a.write_text(content)
        b.write_text("extra")
        rule = _make_script_rule("main.py", content)
        peer_config = self._make_peer_config(rule)
        job = create_mock_job(files=[a, b])

        ok, reason = validate_approved_scripts(job, peer_config)
        assert ok is False
        assert "unapproved file" in reason

    def test_one_hash_mismatch(self, temp_dir):
        content_a = 'print("a")\n'
        a = temp_dir / "main.py"
        b = temp_dir / "utils.py"
        a.write_text(content_a)
        b.write_text('print("modified")\n')
        rule_a = _make_script_rule("main.py", content_a)
        rule_b = ScriptRule(name="utils.py", hash="sha256:wronghash")
        peer_config = self._make_peer_config(rule_a, rule_b)
        job = create_mock_job(files=[a, b])

        ok, reason = validate_approved_scripts(job, peer_config)
        assert ok is False
        assert "hash mismatch" in reason

    def test_filename_mismatch(self, temp_dir):
        script = temp_dir / "train.py"
        script.write_text('print("hello")\n')
        job = create_mock_job(files=[script])
        peer_config = self._make_peer_config(_make_script_rule("main.py"))
        ok, reason = validate_approved_scripts(job, peer_config)
        assert ok is False
        assert "unapproved file" in reason

    def test_hash_mismatch_single(self, temp_dir):
        script = temp_dir / "main.py"
        script.write_text('print("modified")\n')
        job = create_mock_job(files=[script])
        peer_config = PeerApprovalEntry(
            mode="strict",
            scripts=[ScriptRule(name="main.py", hash="sha256:wronghash")],
        )
        ok, reason = validate_approved_scripts(job, peer_config)
        assert ok is False
        assert "hash mismatch" in reason


class TestResolvePeerCriteria:
    """Tests for resolve_peer_criteria."""

    def test_unknown_peer(self):
        job = create_mock_job(submitted_by="unknown@test.com")
        config = JobApprovalConfig(peers={})
        ok, reason = resolve_peer_criteria(job, config)
        assert ok is False
        assert "unknown peer" in reason

    def test_non_inbox_rejected(self):
        job = create_mock_job(status="approved")
        config = JobApprovalConfig()
        ok, reason = resolve_peer_criteria(job, config)
        assert ok is False
        assert "status" in reason

    def test_known_peer_strict_pass(self, temp_dir):
        content = 'print("hello")\n'
        script = temp_dir / "main.py"
        script.write_text(content)
        script_hash = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
        peer_config = PeerApprovalEntry(
            mode="strict",
            scripts=[ScriptRule(name="main.py", hash=script_hash)],
        )
        config = JobApprovalConfig(peers={"alice@test.com": peer_config})
        job = create_mock_job(submitted_by="alice@test.com", files=[script])
        ok, reason = resolve_peer_criteria(job, config)
        assert ok is True

    def test_unknown_mode(self):
        peer_config = PeerApprovalEntry(
            mode="unknown_mode",
            scripts=[ScriptRule(name="main.py", hash="x")],
        )
        config = JobApprovalConfig(peers={"alice@test.com": peer_config})
        job = create_mock_job(submitted_by="alice@test.com")
        ok, reason = resolve_peer_criteria(job, config)
        assert ok is False
        assert "unknown mode" in reason
