"""
Unified test suite for notification system (all phases).

Run all: python3 test_notifications.py
Run specific phase: python3 test_notifications.py --phase=1
"""

import sys
import json
import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import importlib.util
import types

base_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(base_path))


def load_module_directly(module_name, file_path):
    """Load Python module directly from file path"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


notifications_base = load_module_directly(
    "notifications_base", base_path / "syft_client/notifications/base.py"
)

fake_package = types.ModuleType("fake_package")
fake_package.base = notifications_base
sys.modules[".base"] = notifications_base
sys.modules["base"] = notifications_base

gmail_auth = load_module_directly(
    "gmail_auth", base_path / "syft_client/notifications/gmail_auth.py"
)
gmail_sender_module = load_module_directly(
    "gmail_sender", base_path / "syft_client/notifications/gmail_sender.py"
)
json_state_manager_module = load_module_directly(
    "json_state_manager", base_path / "syft_client/notifications/json_state_manager.py"
)

GmailSender = gmail_sender_module.GmailSender
JsonStateManager = json_state_manager_module.JsonStateManager


class Phase3Tests:
    """Phase 3: Notification State Manager"""

    @staticmethod
    def test_state_init_creates_file():
        """State file creation with proper structure"""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"

            JsonStateManager(state_file)

            assert state_file.exists()

            with open(state_file, "r") as f:
                data = json.load(f)
                assert "notified_jobs" in data
                assert data["notified_jobs"] == {}

            return True

    @staticmethod
    def test_mark_and_check_notified():
        """Track job notification types"""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"

            state = JsonStateManager(state_file)

            state.mark_notified("job_123", "new")

            assert state.was_notified("job_123", "new") is True
            assert state.was_notified("job_123", "approved") is False
            assert state.was_notified("job_456", "new") is False

            return True

    @staticmethod
    def test_state_persistence():
        """State survives restart"""
        load_module_directly(
            "json_state_manager",
            base_path / "syft_client/notifications/json_state_manager.py",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"

            state1 = JsonStateManager(state_file)
            state1.mark_notified("job_abc", "new")
            state1.mark_notified("job_xyz", "approved")

            state2 = JsonStateManager(state_file)

            assert state2.was_notified("job_abc", "new") is True
            assert state2.was_notified("job_xyz", "approved") is True

            return True

    @staticmethod
    def test_multiple_notification_types():
        """Track multiple event types per job"""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"

            state = JsonStateManager(state_file)

            state.mark_notified("job_123", "new")
            state.mark_notified("job_123", "approved")
            state.mark_notified("job_123", "executed")

            assert state.was_notified("job_123", "new") is True
            assert state.was_notified("job_123", "approved") is True
            assert state.was_notified("job_123", "executed") is True

            return True


class Phase2Tests:
    """Phase 2: Gmail Sender"""

    @staticmethod
    def test_send_email_creates_message_and_calls_api():
        """Should create MIME message and call Gmail API"""
        mock_creds = MagicMock()

        with patch("gmail_sender.build") as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            mock_service.users().messages().send().execute.return_value = {
                "id": "msg123"
            }

            sender = GmailSender(mock_creds)
            result = sender.send_email(
                to_email="test@example.com", subject="Test", body="Test body"
            )

            assert result is True
            assert mock_service.users().messages().send.call_count >= 1
            return True

    @staticmethod
    def test_send_email_handles_api_error():
        """Should return False on API error, not crash"""
        mock_creds = MagicMock()

        with patch("gmail_sender.build") as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            mock_service.users().messages().send().execute.side_effect = Exception(
                "API Error"
            )

            sender = GmailSender(mock_creds)
            result = sender.send_email(
                to_email="test@example.com", subject="Test", body="Test body"
            )

            assert result is False
            return True

    @staticmethod
    def test_notify_new_job_creates_correct_message():
        """Job notification should contain job name and submitter"""
        mock_creds = MagicMock()

        with patch("gmail_sender.build") as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            mock_service.users().messages().send().execute.return_value = {
                "id": "msg123"
            }

            sender = GmailSender(mock_creds)
            sender.notify_new_job(
                do_email="do@example.com",
                job_name="test_job_123",
                submitter="scientist@example.com",
            )

            call_args = mock_service.users().messages().send.call_args
            sent_message = call_args[1]["body"]

            import base64

            raw_message = base64.urlsafe_b64decode(sent_message["raw"]).decode("utf-8")

            assert "test_job_123" in raw_message
            assert "scientist@example.com" in raw_message
            return True

    @staticmethod
    def test_notify_new_job_sends_to_correct_recipient():
        """Notification should be sent to DO email"""
        mock_creds = MagicMock()

        with patch("gmail_sender.build") as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            mock_service.users().messages().send().execute.return_value = {
                "id": "msg123"
            }

            sender = GmailSender(mock_creds)
            sender.notify_new_job(
                do_email="dataowner@example.com",
                job_name="test_job",
                submitter="scientist@example.com",
            )

            call_args = mock_service.users().messages().send.call_args
            sent_message = call_args[1]["body"]

            import base64

            raw_message = base64.urlsafe_b64decode(sent_message["raw"]).decode("utf-8")

            assert "dataowner@example.com" in raw_message
            return True


class Phase1Tests:
    """Phase 1: Gmail OAuth Authentication"""

    @staticmethod
    def test_setup_oauth_returns_credentials():
        """OAuth setup should return valid credentials object"""
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = Path(tmpdir) / "token.json"

            with patch("gmail_auth.InstalledAppFlow") as mock_flow:
                mock_creds = MagicMock()
                mock_creds.to_json.return_value = '{"token": "test"}'
                mock_flow.from_client_secrets_file.return_value.run_local_server.return_value = mock_creds

                creds = gmail_auth.setup_gmail_oauth(token_path)

            assert creds is not None
            assert creds == mock_creds
            return True

    @staticmethod
    def test_setup_oauth_saves_credentials_to_file():
        """OAuth setup should save credentials to specified path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = Path(tmpdir) / "test_token.json"

            with patch("gmail_auth.InstalledAppFlow") as mock_flow:
                mock_creds = MagicMock()
                mock_creds.to_json.return_value = '{"token": "test"}'
                mock_flow.from_client_secrets_file.return_value.run_local_server.return_value = mock_creds

                gmail_auth.setup_gmail_oauth(token_path)

                assert token_path.exists(), "Token file should exist"
                return True

    @staticmethod
    def test_load_credentials_from_file():
        """Should load existing credentials from file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = Path(tmpdir) / "token.json"
            token_data = {
                "token": "test_token",
                "refresh_token": "refresh",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "client_id",
                "client_secret": "secret",
                "scopes": ["https://www.googleapis.com/auth/gmail.send"],
            }
            token_path.write_text(json.dumps(token_data))

            with patch("gmail_auth.Credentials") as mock_creds_class:
                mock_creds = MagicMock()
                mock_creds.expired = False
                mock_creds_class.from_authorized_user_file.return_value = mock_creds

                creds = gmail_auth.load_gmail_credentials(token_path)

                assert creds is not None
                mock_creds_class.from_authorized_user_file.assert_called_once()
                return True

    @staticmethod
    def test_load_credentials_refreshes_if_expired():
        """Should auto-refresh expired credentials"""
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = Path(tmpdir) / "token.json"
            token_data = {
                "token": "test_token",
                "refresh_token": "refresh",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "client_id",
                "client_secret": "secret",
                "scopes": ["https://www.googleapis.com/auth/gmail.send"],
            }
            token_path.write_text(json.dumps(token_data))

            with patch("gmail_auth.Credentials") as mock_creds_class:
                mock_creds = MagicMock()
                mock_creds.expired = True
                mock_creds.refresh_token = "refresh"
                mock_creds.to_json.return_value = json.dumps(token_data)
                mock_creds_class.from_authorized_user_file.return_value = mock_creds

                with patch("gmail_auth.Request"):
                    gmail_auth.load_gmail_credentials(token_path)
                    mock_creds.refresh.assert_called_once()
                    return True


def run_phase_tests(phase_class, phase_name):
    """Run all tests for a phase"""
    print(f"\n{'=' * 60}")
    print(f"{phase_name}")
    print(f"{'=' * 60}\n")

    test_methods = [
        method
        for method in dir(phase_class)
        if method.startswith("test_") and callable(getattr(phase_class, method))
    ]

    results = []
    for test_name in test_methods:
        test_method = getattr(phase_class, test_name)
        try:
            result = test_method()
            if result:
                print(f"✅ {test_name}")
                results.append(True)
            else:
                print(f"❌ {test_name} returned False")
                results.append(False)
        except AssertionError as e:
            print(f"❌ {test_name} FAILED: {e}")
            results.append(False)
        except Exception as e:
            print(f"❌ {test_name} ERROR: {e}")
            results.append(False)

    passed = sum(results)
    total = len(results)

    print(f"\n{'=' * 60}")
    if passed == total:
        print(f"✅ {phase_name}: ALL {total} TESTS PASSED")
    else:
        print(f"⚠️  {phase_name}: {passed}/{total} tests passed")
    print(f"{'=' * 60}")

    return passed, total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase", type=int, choices=[1, 2, 3, 4, 5], help="Run specific phase"
    )
    args = parser.parse_args()

    phases = {
        1: (Phase1Tests, "Phase 1: Gmail OAuth Authentication"),
        2: (Phase2Tests, "Phase 2: Gmail Sender"),
        3: (Phase3Tests, "Phase 3: Notification State Manager"),
    }

    if args.phase:
        if args.phase in phases:
            phase_class, phase_name = phases[args.phase]
            passed, total = run_phase_tests(phase_class, phase_name)
            sys.exit(0 if passed == total else 1)
        else:
            print(f"Phase {args.phase} not implemented yet")
            sys.exit(1)
    else:
        total_passed = 0
        total_tests = 0

        for phase_num in sorted(phases.keys()):
            phase_class, phase_name = phases[phase_num]
            passed, total = run_phase_tests(phase_class, phase_name)
            total_passed += passed
            total_tests += total

        print(f"\n{'=' * 60}")
        print("OVERALL RESULTS")
        print(f"{'=' * 60}")
        print(f"Total: {total_passed}/{total_tests} tests passed")
        print(f"{'=' * 60}\n")

        sys.exit(0 if total_passed == total_tests else 1)


if __name__ == "__main__":
    main()
