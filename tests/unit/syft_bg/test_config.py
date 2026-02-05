"""Tests for configuration loading."""

from pathlib import Path


from syft_bg.approve.config import ApproveConfig, JobApprovalConfig, PeerApprovalConfig
from syft_bg.notify.config import NotifyConfig


class TestApproveConfig:
    """Tests for ApproveConfig."""

    def test_default_config(self):
        """Default config should have sensible defaults."""
        config = ApproveConfig()

        assert config.do_email is None
        assert config.syftbox_root is None
        assert config.interval == 5
        assert config.jobs.enabled is True
        assert config.jobs.peers_only is True
        assert config.peers.enabled is False

    def test_load_from_file(self, sample_config):
        """Should load config from YAML file."""
        config = ApproveConfig.load(sample_config)

        assert config.do_email == "test@example.com"
        assert config.syftbox_root == Path("/tmp/syftbox")
        assert config.interval == 5
        assert config.jobs.enabled is True
        assert config.jobs.peers_only is True
        assert "main.py" in config.jobs.required_scripts
        assert config.jobs.required_filenames == ["main.py", "params.json"]

    def test_load_nonexistent_returns_defaults(self, temp_dir):
        """Loading non-existent file should return defaults."""
        config = ApproveConfig.load(temp_dir / "nonexistent.yaml")

        assert config.do_email is None
        assert config.jobs.enabled is True

    def test_save_config(self, temp_dir):
        """Should save config to YAML file."""
        config_path = temp_dir / "config.yaml"

        config = ApproveConfig(
            do_email="save@example.com",
            syftbox_root=Path("/tmp/saved"),
            interval=10,
        )
        config.jobs.enabled = False
        config.save(config_path)

        # Reload and verify
        loaded = ApproveConfig.load(config_path)
        assert loaded.do_email == "save@example.com"
        assert loaded.interval == 10
        assert loaded.jobs.enabled is False


class TestJobApprovalConfig:
    """Tests for JobApprovalConfig."""

    def test_from_dict(self):
        """Should create config from dictionary."""
        data = {
            "enabled": True,
            "peers_only": False,
            "required_scripts": {"main.py": "sha256:abc"},
            "required_filenames": ["main.py"],
            "allowed_users": ["user@example.com"],
        }

        config = JobApprovalConfig.from_dict(data)

        assert config.enabled is True
        assert config.peers_only is False
        assert config.required_scripts == {"main.py": "sha256:abc"}
        assert config.required_filenames == ["main.py"]
        assert config.allowed_users == ["user@example.com"]

    def test_from_dict_defaults(self):
        """Should use defaults for missing keys."""
        config = JobApprovalConfig.from_dict({})

        assert config.enabled is True
        assert config.peers_only is True
        assert config.required_scripts == {}
        assert config.required_filenames == []
        assert config.allowed_users == []


class TestPeerApprovalConfig:
    """Tests for PeerApprovalConfig."""

    def test_from_dict(self):
        """Should create config from dictionary."""
        data = {
            "enabled": True,
            "approved_domains": ["example.com", "test.org"],
            "auto_share_datasets": ["dataset1"],
        }

        config = PeerApprovalConfig.from_dict(data)

        assert config.enabled is True
        assert config.approved_domains == ["example.com", "test.org"]
        assert config.auto_share_datasets == ["dataset1"]

    def test_from_dict_defaults(self):
        """Should use defaults for missing keys."""
        config = PeerApprovalConfig.from_dict({})

        assert config.enabled is False
        assert config.approved_domains == []
        assert config.auto_share_datasets == []


class TestNotifyConfig:
    """Tests for NotifyConfig."""

    def test_default_config(self):
        """Default config should have sensible defaults."""
        config = NotifyConfig()

        assert config.do_email is None
        assert config.syftbox_root is None
        assert config.interval == 30

    def test_load_from_file(self, sample_config):
        """Should load config from YAML file."""
        config = NotifyConfig.load(sample_config)

        assert config.do_email == "test@example.com"
        assert config.syftbox_root == Path("/tmp/syftbox")
        assert config.interval == 30
