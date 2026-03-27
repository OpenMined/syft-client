"""Integration tests for CLI commands."""

import hashlib
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from syft_bg.cli.commands import (
    hash,
    list_scripts,
    main,
    remove_peer,
    remove_script,
    set_script,
    status,
)


class TestHashCommand:
    """Tests for the hash command."""

    def test_hash_file(self, sample_script):
        """Should generate hash for a file."""
        runner = CliRunner()
        result = runner.invoke(hash, [str(sample_script)])

        assert result.exit_code == 0
        assert result.output.startswith("sha256:")
        assert len(result.output.strip()) == 7 + 16  # "sha256:" + 16 chars

    def test_hash_custom_length(self, sample_script):
        """Should support custom hash length."""
        runner = CliRunner()
        result = runner.invoke(hash, [str(sample_script), "--length", "8"])

        assert result.exit_code == 0
        assert result.output.startswith("sha256:")
        assert len(result.output.strip()) == 7 + 8  # "sha256:" + 8 chars

    def test_hash_matches_expected(self, sample_script):
        """Hash should match manual calculation."""
        content = sample_script.read_text()
        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

        runner = CliRunner()
        result = runner.invoke(hash, [str(sample_script)])

        assert result.output.strip() == f"sha256:{expected}"

    def test_hash_nonexistent_file(self, temp_dir):
        """Should error on non-existent file."""
        runner = CliRunner()
        result = runner.invoke(hash, [str(temp_dir / "nonexistent.py")])

        assert result.exit_code != 0


class TestStatusCommand:
    """Tests for the status command."""

    def test_status_shows_services(self):
        """Should show all registered services."""
        runner = CliRunner()
        result = runner.invoke(status)

        assert result.exit_code == 0
        assert "notify" in result.output.lower()
        assert "approve" in result.output.lower()

    def test_status_shows_header(self):
        """Should show header information."""
        runner = CliRunner()
        result = runner.invoke(status)

        assert "SYFT BACKGROUND SERVICES" in result.output
        assert "SERVICE" in result.output
        assert "STATUS" in result.output


class TestMainCommand:
    """Tests for main command group."""

    def test_help_shows_all_commands(self):
        """Help should list all available commands."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "status" in result.output
        assert "start" in result.output
        assert "stop" in result.output
        assert "restart" in result.output
        assert "logs" in result.output
        assert "init" in result.output
        assert "tui" in result.output
        assert "run" in result.output
        assert "hash" in result.output
        assert "set-script" in result.output
        assert "install" in result.output
        assert "uninstall" in result.output
        assert "remove-script" in result.output
        assert "remove-peer" in result.output
        assert "list-scripts" in result.output


class TestSetScriptCommand:
    """Tests for the set-script command."""

    @patch("syft_bg.cli.commands.ServiceManager")
    @patch("syft_bg.approve.config.AutoApproveConfig.load")
    def test_set_script_basic(self, mock_load, mock_svc_mgr, temp_dir, sample_script):
        """Should accept a .py file and a single peer."""
        mock_config = MagicMock()
        mock_config.auto_approvals.objects = {}
        mock_load.return_value = mock_config

        mock_mgr_instance = MagicMock()
        mock_mgr_instance.get_status.return_value.status = "stopped"
        mock_svc_mgr.return_value = mock_mgr_instance

        runner = CliRunner()
        result = runner.invoke(
            set_script, [str(sample_script), "--peers", "alice@test.com"]
        )

        assert result.exit_code == 0
        mock_load.assert_called_once()
        mock_config.save.assert_called_once()

    def test_set_script_non_py_file(self, temp_dir):
        """Should reject a non-.py file."""
        txt_file = temp_dir / "script.txt"
        txt_file.write_text("some content")

        runner = CliRunner()
        result = runner.invoke(set_script, [str(txt_file), "--peers", "alice@test.com"])

        assert result.exit_code != 0

    @patch("syft_bg.cli.commands.ServiceManager")
    @patch("syft_bg.approve.config.AutoApproveConfig.load")
    def test_set_script_multiple_peers(
        self, mock_load, mock_svc_mgr, temp_dir, sample_script
    ):
        """Should accept multiple peers via -p flags."""
        mock_config = MagicMock()
        mock_config.auto_approvals.objects = {}
        mock_load.return_value = mock_config

        mock_mgr_instance = MagicMock()
        mock_mgr_instance.get_status.return_value.status = "stopped"
        mock_svc_mgr.return_value = mock_mgr_instance

        runner = CliRunner()
        result = runner.invoke(
            set_script,
            [str(sample_script), "-p", "alice@test.com", "-p", "bob@test.com"],
        )

        assert result.exit_code == 0
        # The auto-generated name should be the script stem ("main")
        assert "main" in mock_config.auto_approvals.objects
        obj = mock_config.auto_approvals.objects["main"]
        assert "alice@test.com" in obj.peers
        assert "bob@test.com" in obj.peers
        mock_config.save.assert_called_once()

    @patch("syft_bg.cli.commands.ServiceManager")
    @patch("syft_bg.approve.config.AutoApproveConfig.load")
    def test_set_script_multiple_files(self, mock_load, mock_svc_mgr, sample_scripts):
        """Should accept multiple .py files."""
        mock_config = MagicMock()
        mock_config.auto_approvals.objects = {}
        mock_load.return_value = mock_config

        mock_mgr_instance = MagicMock()
        mock_mgr_instance.get_status.return_value.status = "stopped"
        mock_svc_mgr.return_value = mock_mgr_instance

        runner = CliRunner()
        result = runner.invoke(
            set_script,
            [str(sample_scripts[0]), str(sample_scripts[1]), "-p", "alice@test.com"],
        )

        assert result.exit_code == 0
        mock_config.save.assert_called_once()

    @patch("syft_bg.cli.commands.ServiceManager")
    @patch("syft_bg.approve.config.AutoApproveConfig.load")
    def test_set_script_directory(self, mock_load, mock_svc_mgr, temp_dir):
        """Should expand directory to all .py files."""
        subdir = temp_dir / "src"
        subdir.mkdir()
        (subdir / "main.py").write_text('print("a")\n')
        (subdir / "utils.py").write_text('print("b")\n')

        mock_config = MagicMock()
        mock_config.auto_approvals.objects = {}
        mock_load.return_value = mock_config

        mock_mgr_instance = MagicMock()
        mock_mgr_instance.get_status.return_value.status = "stopped"
        mock_svc_mgr.return_value = mock_mgr_instance

        runner = CliRunner()
        result = runner.invoke(set_script, [str(subdir), "-p", "alice@test.com"])

        assert result.exit_code == 0
        assert "main.py" in result.output
        assert "utils.py" in result.output
        mock_config.save.assert_called_once()


class TestRemoveScriptCommand:
    """Tests for the remove-script command."""

    @patch("syft_bg.approve.config.AutoApproveConfig.load")
    def test_remove_script(self, mock_load):
        """Should remove scripts by filename from an auto-approval object."""
        from syft_bg.approve.config import AutoApprovalObj, FileEntry

        obj = AutoApprovalObj(
            file_contents=[
                FileEntry(
                    relative_path="main.py",
                    path="/tmp/auto_approvals/my_analysis/main.py",
                    hash="sha256:aaa",
                ),
                FileEntry(
                    relative_path="utils.py",
                    path="/tmp/auto_approvals/my_analysis/utils.py",
                    hash="sha256:bbb",
                ),
            ],
            peers=["alice@test.com"],
        )
        mock_config = MagicMock()
        mock_config.auto_approvals.objects = {"my_analysis": obj}
        mock_load.return_value = mock_config

        runner = CliRunner()
        result = runner.invoke(remove_script, ["utils.py", "-n", "my_analysis"])

        assert result.exit_code == 0
        assert "Removed 1" in result.output
        assert len(obj.file_contents) == 1
        assert obj.file_contents[0].relative_path == "main.py"

    @patch("syft_bg.approve.config.AutoApproveConfig.load")
    def test_remove_script_unknown_object(self, mock_load):
        """Should error when object name not found."""
        mock_config = MagicMock()
        mock_config.auto_approvals.objects = {}
        mock_load.return_value = mock_config

        runner = CliRunner()
        result = runner.invoke(remove_script, ["main.py", "-n", "nonexistent"])

        assert result.exit_code == 1


class TestRemovePeerCommand:
    """Tests for the remove-peer command."""

    @patch("syft_bg.approve.config.AutoApproveConfig.load")
    def test_remove_peer(self, mock_load):
        """Should remove peer from auto-approval objects."""
        from syft_bg.approve.config import AutoApprovalObj

        mock_config = MagicMock()
        mock_config.auto_approvals.objects = {
            "my_analysis": AutoApprovalObj(peers=["alice@test.com"])
        }
        mock_load.return_value = mock_config

        runner = CliRunner()
        result = runner.invoke(remove_peer, ["alice@test.com"])

        assert result.exit_code == 0
        assert "Removed peer" in result.output
        assert (
            "alice@test.com"
            not in mock_config.auto_approvals.objects["my_analysis"].peers
        )

    @patch("syft_bg.approve.config.AutoApproveConfig.load")
    def test_remove_peer_not_found(self, mock_load):
        """Should error if peer not found."""
        mock_config = MagicMock()
        mock_config.auto_approvals.objects = {}
        mock_load.return_value = mock_config

        runner = CliRunner()
        result = runner.invoke(remove_peer, ["unknown@test.com"])

        assert result.exit_code != 0


class TestListScriptsCommand:
    """Tests for the list-scripts command."""

    @patch("syft_bg.approve.config.AutoApproveConfig.load")
    def test_list_scripts(self, mock_load):
        """Should list all auto-approval objects and their scripts."""
        from syft_bg.approve.config import AutoApprovalObj, FileEntry

        mock_config = MagicMock()
        mock_config.auto_approvals.objects = {
            "analysis_a": AutoApprovalObj(
                file_contents=[
                    FileEntry(
                        relative_path="main.py",
                        path="/tmp/auto_approvals/analysis_a/main.py",
                        hash="sha256:aaa",
                    )
                ],
                peers=["alice@test.com"],
            ),
            "analysis_b": AutoApprovalObj(
                file_contents=[
                    FileEntry(
                        relative_path="train.py",
                        path="/tmp/auto_approvals/analysis_b/train.py",
                        hash="sha256:bbb",
                    )
                ],
                peers=["bob@test.com"],
            ),
        }
        mock_load.return_value = mock_config

        runner = CliRunner()
        result = runner.invoke(list_scripts)

        assert result.exit_code == 0
        assert "alice@test.com" in result.output
        assert "main.py" in result.output
        assert "bob@test.com" in result.output
        assert "train.py" in result.output

    @patch("syft_bg.approve.config.AutoApproveConfig.load")
    def test_list_scripts_single_object(self, mock_load):
        """Should filter to a specific auto-approval object."""
        from syft_bg.approve.config import AutoApprovalObj, FileEntry

        mock_config = MagicMock()
        mock_config.auto_approvals.objects = {
            "analysis_a": AutoApprovalObj(
                file_contents=[
                    FileEntry(
                        relative_path="main.py",
                        path="/tmp/auto_approvals/analysis_a/main.py",
                        hash="sha256:aaa",
                    )
                ],
                peers=["alice@test.com"],
            ),
            "analysis_b": AutoApprovalObj(
                file_contents=[
                    FileEntry(
                        relative_path="train.py",
                        path="/tmp/auto_approvals/analysis_b/train.py",
                        hash="sha256:bbb",
                    )
                ],
                peers=["bob@test.com"],
            ),
        }
        mock_load.return_value = mock_config

        runner = CliRunner()
        result = runner.invoke(list_scripts, ["-n", "analysis_a"])

        assert result.exit_code == 0
        assert "analysis_a" in result.output
        assert "analysis_b" not in result.output

    @patch("syft_bg.approve.config.AutoApproveConfig.load")
    def test_list_scripts_empty(self, mock_load):
        """Should show message when no auto-approval objects configured."""
        mock_config = MagicMock()
        mock_config.auto_approvals.objects = {}
        mock_load.return_value = mock_config

        runner = CliRunner()
        result = runner.invoke(list_scripts)

        assert result.exit_code == 0
        assert "No auto-approval objects configured" in result.output
