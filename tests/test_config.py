"""Tests for global config."""

from unittest.mock import patch

from stuc import config


def test_load_defaults(tmp_path):
    with patch("stuc.config.CONFIG_PATH", tmp_path / "config.yml"):
        data = config.load()
        assert data["issue_repo"] == ""
        assert data["pr_body"] == ""


def test_set_and_get(tmp_path):
    cfg_path = tmp_path / "config.yml"
    with patch("stuc.config.CONFIG_PATH", cfg_path):
        config.set_value("issue_repo", "Org/fleet-ops")
        assert config.get("issue_repo") == "Org/fleet-ops"
        assert cfg_path.exists()


def test_save_and_load_roundtrip(tmp_path):
    with patch("stuc.config.CONFIG_PATH", tmp_path / "config.yml"):
        config.set_value("issue_repo", "Org/ops")
        config.set_value("pr_body", "Custom body")

        data = config.load()
        assert data["issue_repo"] == "Org/ops"
        assert data["pr_body"] == "Custom body"


def test_get_missing_key(tmp_path):
    with patch("stuc.config.CONFIG_PATH", tmp_path / "config.yml"):
        assert config.get("issue_repo") == ""
        assert config.get("nonexistent") == ""


def test_load_partial_config(tmp_path):
    """Config file with only some keys still returns defaults for the rest."""
    cfg_path = tmp_path / "config.yml"
    cfg_path.write_text("issue_repo: Org/repo\n")
    with patch("stuc.config.CONFIG_PATH", cfg_path):
        data = config.load()
        assert data["issue_repo"] == "Org/repo"
        assert data["pr_body"] == ""
