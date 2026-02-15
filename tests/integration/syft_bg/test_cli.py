"""Integration tests for CLI commands."""

import hashlib

from click.testing import CliRunner

from syft_bg.cli.commands import hash, main, status


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
        assert "install" in result.output
        assert "uninstall" in result.output
