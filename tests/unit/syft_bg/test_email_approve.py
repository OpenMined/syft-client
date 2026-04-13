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
        client = MagicMock()
        handler = EmailApproveHandler(
            client=client,
            state=state,
            notify_state=notify_state,
            do_email="do@example.com",
        )
        return handler, client, state, notify_state

    def test_approve_job(self, tmp_path):
        handler, client, state, notify_state = self._make_handler(tmp_path)

        # Set up thread_id -> job_name mapping in notify state
        notify_state.store_thread_id("test.job", "thread123")

        # Set up a mock job
        mock_job = MagicMock()
        mock_job.name = "test.job"
        mock_job.status = "pending"
        client.jobs = [mock_job]

        handler.handle_reply("thread123", "approve")

        mock_job.approve.assert_called_once()
        client.process_approved_jobs.assert_called_once_with(
            share_outputs_with_submitter=True,
            share_logs_with_submitter=True,
        )
        client.sync.assert_called_once()

    def test_deny_job(self, tmp_path):
        handler, client, state, notify_state = self._make_handler(tmp_path)

        notify_state.store_thread_id("test.job", "thread456")

        mock_job = MagicMock()
        mock_job.name = "test.job"
        mock_job.status = "pending"
        client.jobs = [mock_job]

        handler.handle_reply("thread456", "deny unsafe code")

        mock_job.reject.assert_called_once_with("unsafe code")

    def test_unknown_thread_id(self, tmp_path):
        handler, client, state, notify_state = self._make_handler(tmp_path)

        with pytest.raises(ValueError, match="No job found for thread"):
            handler.handle_reply("unknown_thread", "approve")

    def test_unrecognized_reply(self, tmp_path):
        handler, client, state, notify_state = self._make_handler(tmp_path)

        notify_state.store_thread_id("test.job", "thread789")

        mock_job = MagicMock()
        mock_job.name = "test.job"
        mock_job.status = "pending"
        client.jobs = [mock_job]

        with pytest.raises(ValueError, match="Unrecognized reply"):
            handler.handle_reply("thread789", "maybe later")
        mock_job.approve.assert_not_called()
        mock_job.reject.assert_not_called()

    def test_already_processed_reply(self, tmp_path):
        handler, client, state, notify_state = self._make_handler(tmp_path)

        notify_state.store_thread_id("test.job", "thread_dup")

        mock_job = MagicMock()
        mock_job.name = "test.job"
        mock_job.status = "pending"
        client.jobs = [mock_job]

        # Process once
        handler.handle_reply("thread_dup", "approve")
        mock_job.approve.assert_called_once()

        # Process again — should be skipped
        mock_job.reset_mock()
        handler.handle_reply("thread_dup", "approve")
        mock_job.approve.assert_not_called()

    def test_job_not_pending(self, tmp_path):
        handler, client, state, notify_state = self._make_handler(tmp_path)

        notify_state.store_thread_id("test.job", "thread_done")

        mock_job = MagicMock()
        mock_job.name = "test.job"
        mock_job.status = "approved"
        client.jobs = [mock_job]

        with pytest.raises(ValueError, match="is approved, not pending"):
            handler.handle_reply("thread_done", "approve")
        mock_job.approve.assert_not_called()


# --- State reverse lookup test ---


class TestStateReverseLookup:
    def test_get_job_name_by_thread_id(self, tmp_path):
        state = JsonStateManager(tmp_path / "state.json")
        state.store_thread_id("job_a", "thread_1")
        state.store_thread_id("job_b", "thread_2")

        assert state.get_job_name_by_thread_id("thread_1") == "job_a"
        assert state.get_job_name_by_thread_id("thread_2") == "job_b"
        assert state.get_job_name_by_thread_id("thread_unknown") is None
