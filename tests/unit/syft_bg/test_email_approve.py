"""Tests for email-based job approval: reply parsing, handler, and gmail_watch helpers."""

from unittest.mock import MagicMock

import pytest

from syft_bg.common.state import JsonStateManager
from syft_bg.email_approve.gmail_message import (
    _strip_quoted_reply,
)
from syft_bg.email_approve.handler import (
    EmailAction,
    EmailApprovalResponse,
    EmailApproveHandler,
    parse_reply,
)
from syft_bg.sync.snapshot import PeerVersionInfo, SyncSnapshot


# --- Reply parsing tests ---


class TestParseReply:
    def test_approve(self):
        assert parse_reply("approve") == EmailApprovalResponse(
            action=EmailAction.APPROVE
        )

    def test_approve_case_insensitive(self):
        assert parse_reply("Approve") == EmailApprovalResponse(
            action=EmailAction.APPROVE
        )
        assert parse_reply("APPROVE") == EmailApprovalResponse(
            action=EmailAction.APPROVE
        )

    def test_approve_with_trailing_text(self):
        assert parse_reply("approve please") == EmailApprovalResponse(
            action=EmailAction.APPROVE
        )

    def test_deny_with_reason(self):
        assert parse_reply("deny bad code") == EmailApprovalResponse(
            action=EmailAction.DENY, reason="bad code"
        )

    def test_deny_no_reason(self):
        assert parse_reply("deny") == EmailApprovalResponse(
            action=EmailAction.DENY, reason="No reason provided"
        )

    def test_deny_case_insensitive(self):
        assert parse_reply("Deny the code is unsafe") == EmailApprovalResponse(
            action=EmailAction.DENY, reason="the code is unsafe"
        )

    def test_empty_string(self):
        assert parse_reply("") == EmailApprovalResponse(action=EmailAction.UNKNOWN)

    def test_unrecognized_command(self):
        assert parse_reply("hello world") == EmailApprovalResponse(
            action=EmailAction.UNKNOWN
        )

    def test_leading_blank_lines(self):
        assert parse_reply("\n\napprove") == EmailApprovalResponse(
            action=EmailAction.APPROVE
        )

    def test_deny_with_multiword_reason(self):
        assert parse_reply(
            "deny this code accesses private data"
        ) == EmailApprovalResponse(
            action=EmailAction.DENY, reason="this code accesses private data"
        )

    def test_whitespace_only(self):
        assert parse_reply("   \n  \n  ") == EmailApprovalResponse(
            action=EmailAction.UNKNOWN
        )


# --- Strip quoted reply tests ---


class TestStripQuotedReply:
    def test_strip_angle_bracket_quotes(self):
        text = "approve\n\n> On Mon, Mar 30 wrote:\n> old text"
        assert _strip_quoted_reply(text) == "approve"

    def test_strip_on_wrote_line(self):
        text = (
            "deny bad code\n\nOn Mon, Mar 30, 2026 at 10:00 AM someone wrote:\nquoted"
        )
        assert _strip_quoted_reply(text) == "deny bad code"

    def test_no_quoted_content(self):
        text = "approve"
        assert _strip_quoted_reply(text) == "approve"

    def test_forwarded_message(self):
        text = "approve\n---------- Forwarded message ----------"
        assert _strip_quoted_reply(text) == "approve"


# --- Handler tests ---


class TestEmailApproveHandler:
    def _make_handler(self, tmp_path):
        state = JsonStateManager(tmp_path / "email_approve_state.json")
        notify_state = JsonStateManager(tmp_path / "notify_state.json")
        job_client = MagicMock()
        job_runner = MagicMock()
        snapshot_reader = MagicMock()
        snapshot_reader.read.return_value = None
        handler = EmailApproveHandler(
            job_client=job_client,
            job_runner=job_runner,
            snapshot_reader=snapshot_reader,
            state=state,
            notify_state=notify_state,
            do_email="do@example.com",
        )
        return handler, job_client, job_runner, snapshot_reader, state, notify_state

    def test_approve_job(self, tmp_path):
        handler, job_client, job_runner, _, state, notify_state = self._make_handler(
            tmp_path
        )

        notify_state.store_thread_id("test.job", "thread123")

        mock_job = MagicMock()
        mock_job.name = "test.job"
        mock_job.status = "pending"
        job_client.jobs = [mock_job]

        handler.handle_reply(thread_id="thread123", reply_text="approve")

        mock_job.approve.assert_called_once()
        job_runner.process_approved_jobs.assert_called_once_with(
            share_outputs_with_submitter=True,
            share_logs_with_submitter=True,
            skip_job_names=None,
        )

    def test_deny_job(self, tmp_path):
        handler, job_client, _, _, state, notify_state = self._make_handler(tmp_path)

        notify_state.store_thread_id("test.job", "thread456")

        mock_job = MagicMock()
        mock_job.name = "test.job"
        mock_job.status = "pending"
        job_client.jobs = [mock_job]

        handler.handle_reply(thread_id="thread456", reply_text="deny unsafe code")

        mock_job.reject.assert_called_once_with("unsafe code")

    def test_unknown_thread_id(self, tmp_path):
        handler, *_ = self._make_handler(tmp_path)

        with pytest.raises(ValueError, match="No job found for thread"):
            handler.handle_reply(thread_id="unknown_thread", reply_text="approve")

    def test_unrecognized_reply(self, tmp_path):
        handler, job_client, _, _, state, notify_state = self._make_handler(tmp_path)

        notify_state.store_thread_id("test.job", "thread789")

        mock_job = MagicMock()
        mock_job.name = "test.job"
        mock_job.status = "pending"
        job_client.jobs = [mock_job]

        with pytest.raises(ValueError, match="Unrecognized reply"):
            handler.handle_reply(thread_id="thread789", reply_text="maybe later")
        mock_job.approve.assert_not_called()
        mock_job.reject.assert_not_called()

    def test_already_processed_reply(self, tmp_path):
        handler, job_client, _, _, state, notify_state = self._make_handler(tmp_path)

        notify_state.store_thread_id("test.job", "thread_dup")

        mock_job = MagicMock()
        mock_job.name = "test.job"
        mock_job.status = "pending"
        job_client.jobs = [mock_job]

        # Process once
        handler.handle_reply(thread_id="thread_dup", reply_text="approve")
        mock_job.approve.assert_called_once()

        # Process again — should be skipped
        mock_job.reset_mock()
        handler.handle_reply(thread_id="thread_dup", reply_text="approve")
        mock_job.approve.assert_not_called()

    def test_job_not_pending(self, tmp_path):
        handler, job_client, _, _, state, notify_state = self._make_handler(tmp_path)

        notify_state.store_thread_id("test.job", "thread_done")

        mock_job = MagicMock()
        mock_job.name = "test.job"
        mock_job.status = "approved"
        job_client.jobs = [mock_job]

        with pytest.raises(ValueError, match="is approved, not pending"):
            handler.handle_reply(thread_id="thread_done", reply_text="approve")
        mock_job.approve.assert_not_called()

    def test_approve_skips_incompatible_version(self, tmp_path):
        handler, job_client, job_runner, snapshot_reader, state, notify_state = (
            self._make_handler(tmp_path)
        )

        notify_state.store_thread_id("test.job", "thread_ver")

        mock_job = MagicMock()
        mock_job.name = "test.job"
        mock_job.status = "pending"
        mock_job.submitted_by = "submitter@example.com"
        job_client.jobs = [mock_job]

        snapshot_reader.read.return_value = SyncSnapshot(
            sync_time=0,
            own_version=PeerVersionInfo(
                syft_client_version="0.2.0", protocol_version="1.0.0"
            ),
            peer_versions={
                "submitter@example.com": PeerVersionInfo(
                    syft_client_version="0.1.0", protocol_version="1.0.0"
                )
            },
        )

        def approve_side_effect():
            mock_job.status = "approved"

        mock_job.approve.side_effect = approve_side_effect

        handler.handle_reply(thread_id="thread_ver", reply_text="approve")

        mock_job.approve.assert_called_once()
        job_runner.process_approved_jobs.assert_called_once()
        call_kwargs = job_runner.process_approved_jobs.call_args[1]
        assert call_kwargs.get("skip_job_names") == ["test.job"]

    def test_approve_no_skip_when_versions_match(self, tmp_path):
        handler, job_client, job_runner, snapshot_reader, state, notify_state = (
            self._make_handler(tmp_path)
        )

        notify_state.store_thread_id("test.job", "thread_ok")

        mock_job = MagicMock()
        mock_job.name = "test.job"
        mock_job.status = "pending"
        mock_job.submitted_by = "submitter@example.com"
        job_client.jobs = [mock_job]

        snapshot_reader.read.return_value = SyncSnapshot(
            sync_time=0,
            own_version=PeerVersionInfo(
                syft_client_version="0.1.112", protocol_version="1.0.0"
            ),
            peer_versions={
                "submitter@example.com": PeerVersionInfo(
                    syft_client_version="0.1.112", protocol_version="1.0.0"
                )
            },
        )

        def approve_side_effect():
            mock_job.status = "approved"

        mock_job.approve.side_effect = approve_side_effect

        handler.handle_reply(thread_id="thread_ok", reply_text="approve")

        mock_job.approve.assert_called_once()
        job_runner.process_approved_jobs.assert_called_once_with(
            share_outputs_with_submitter=True,
            share_logs_with_submitter=True,
            skip_job_names=None,
        )


# --- State reverse lookup test ---


class TestStateReverseLookup:
    def test_get_job_name_by_thread_id(self, tmp_path):
        state = JsonStateManager(tmp_path / "state.json")
        state.store_thread_id("job_a", "thread_1")
        state.store_thread_id("job_b", "thread_2")

        assert state.get_job_name_by_thread_id("thread_1") == "job_a"
        assert state.get_job_name_by_thread_id("thread_2") == "job_b"
        assert state.get_job_name_by_thread_id("thread_unknown") is None
