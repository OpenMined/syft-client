"""Tests for configuration loading."""

from pathlib import Path

from syft_bg.approve.config import (
    ApproveConfig,
    JobApprovalConfig,
    PeerApprovalConfig,
    PeerApprovalEntry,
    ScriptRule,
)
from syft_bg.notify.config import NotifyConfig


class TestScriptRule:
    """Tests for ScriptRule."""

    def test_from_dict(self):
        rule = ScriptRule.model_validate({"name": "train.py", "hash": "sha256:aaa"})
        assert rule.name == "train.py"
        assert rule.hash == "sha256:aaa"

    def test_model_dump(self):
        rule = ScriptRule(name="main.py", hash="sha256:bbb")
        d = rule.model_dump()
        assert d == {"name": "main.py", "hash": "sha256:bbb"}


class TestPeerApprovalEntry:
    """Tests for PeerApprovalEntry."""

    def test_from_dict(self):
        config = PeerApprovalEntry.model_validate(
            {
                "mode": "strict",
                "scripts": [{"name": "train.py", "hash": "sha256:aaa"}],
            }
        )
        assert config.mode == "strict"
        assert len(config.scripts) == 1
        assert config.scripts[0].name == "train.py"
        assert config.scripts[0].hash == "sha256:aaa"

    def test_defaults(self):
        config = PeerApprovalEntry()
        assert config.mode == "strict"
        assert config.scripts == []

    def test_model_dump(self):
        config = PeerApprovalEntry(
            mode="strict",
            scripts=[ScriptRule(name="main.py", hash="sha256:bbb")],
        )
        d = config.model_dump()
        assert d == {
            "mode": "strict",
            "scripts": [{"name": "main.py", "hash": "sha256:bbb"}],
        }

    def test_multiple_scripts(self):
        config = PeerApprovalEntry(
            mode="strict",
            scripts=[
                ScriptRule(name="main.py", hash="sha256:aaa"),
                ScriptRule(name="utils.py", hash="sha256:bbb"),
            ],
        )
        assert len(config.scripts) == 2
        assert config.scripts[0].name == "main.py"
        assert config.scripts[1].name == "utils.py"


class TestApproveConfig:
    """Tests for ApproveConfig."""

    def test_default_config(self):
        config = ApproveConfig()
        assert config.do_email is None
        assert config.syftbox_root is None
        assert config.interval == 5
        assert config.jobs.enabled is True
        assert config.jobs.peers == {}
        assert config.peers.enabled is False

    def test_load_from_file(self, sample_config):
        config = ApproveConfig.load(sample_config)
        assert config.do_email == "test@example.com"
        assert config.syftbox_root == Path("/tmp/syftbox")
        assert config.interval == 5
        assert config.jobs.enabled is True
        assert "alice@uni.edu" in config.jobs.peers
        assert "bob@co.com" in config.jobs.peers
        alice = config.jobs.peers["alice@uni.edu"]
        assert alice.mode == "strict"
        assert len(alice.scripts) == 1
        assert alice.scripts[0].name == "main.py"
        assert alice.scripts[0].hash == "sha256:abc123"

    def test_load_nonexistent_returns_defaults(self, temp_dir):
        config = ApproveConfig.load(temp_dir / "nonexistent.yaml")
        assert config.do_email is None
        assert config.jobs.enabled is True

    def test_save_config(self, temp_dir):
        config_path = temp_dir / "config.yaml"
        config = ApproveConfig(
            do_email="save@example.com",
            syftbox_root=Path("/tmp/saved"),
            interval=10,
        )
        config.jobs.enabled = False
        config.jobs.peers["alice@test.com"] = PeerApprovalEntry(
            mode="strict",
            scripts=[ScriptRule(name="main.py", hash="sha256:xyz")],
        )
        config.save(config_path)

        loaded = ApproveConfig.load(config_path)
        assert loaded.do_email == "save@example.com"
        assert loaded.interval == 10
        assert loaded.jobs.enabled is False
        assert "alice@test.com" in loaded.jobs.peers
        assert loaded.jobs.peers["alice@test.com"].scripts[0].hash == "sha256:xyz"

    def test_save_reload_multi_script_roundtrip(self, temp_dir):
        config_path = temp_dir / "config.yaml"
        config = ApproveConfig(do_email="rt@test.com")
        config.jobs.peers["ds@test.com"] = PeerApprovalEntry(
            mode="strict",
            scripts=[
                ScriptRule(name="main.py", hash="sha256:aaa"),
                ScriptRule(name="utils.py", hash="sha256:bbb"),
            ],
        )
        config.save(config_path)

        loaded = ApproveConfig.load(config_path)
        peer = loaded.jobs.peers["ds@test.com"]
        assert len(peer.scripts) == 2
        assert peer.scripts[0].name == "main.py"
        assert peer.scripts[1].name == "utils.py"

    def test_load_empty_peers(self, temp_dir):
        config_path = temp_dir / "config.yaml"
        config_path.write_text("""
do_email: test@example.com
approve:
  jobs:
    enabled: true
    peers: {}
""")
        config = ApproveConfig.load(config_path)
        assert config.jobs.peers == {}


class TestJobApprovalConfig:
    """Tests for JobApprovalConfig."""

    def test_from_dict_with_peers(self):
        config = JobApprovalConfig.model_validate(
            {
                "enabled": True,
                "peers": {
                    "alice@test.com": {
                        "mode": "strict",
                        "scripts": [{"name": "main.py", "hash": "sha256:abc"}],
                    },
                },
            }
        )
        assert config.enabled is True
        assert "alice@test.com" in config.peers
        assert config.peers["alice@test.com"].scripts[0].name == "main.py"

    def test_defaults(self):
        config = JobApprovalConfig()
        assert config.enabled is True
        assert config.peers == {}


class TestPeerApprovalConfig:
    """Tests for PeerApprovalConfig."""

    def test_from_dict(self):
        config = PeerApprovalConfig.model_validate(
            {
                "enabled": True,
                "approved_domains": ["example.com", "test.org"],
                "auto_share_datasets": ["dataset1"],
            }
        )
        assert config.enabled is True
        assert config.approved_domains == ["example.com", "test.org"]
        assert config.auto_share_datasets == ["dataset1"]

    def test_defaults(self):
        config = PeerApprovalConfig()
        assert config.enabled is False
        assert config.approved_domains == []
        assert config.auto_share_datasets == []


class TestNotifyConfig:
    """Tests for NotifyConfig."""

    def test_default_config(self):
        config = NotifyConfig()
        assert config.do_email is None
        assert config.syftbox_root is None
        assert config.interval == 30

    def test_load_from_file(self, sample_config):
        config = NotifyConfig.load(sample_config)
        assert config.do_email == "test@example.com"
        assert config.syftbox_root == Path("/tmp/syftbox")
        assert config.interval == 30
