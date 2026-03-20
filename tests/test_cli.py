"""Tests for CLI argument parsing and init command."""

import subprocess
import sys
from unittest.mock import patch

from stuc.campaign import Campaign


def test_init_creates_campaign(tmp_path):
    with patch("stuc.campaign.CAMPAIGNS_DIR", tmp_path):
        campaign = Campaign(
            name="cli-test",
            orgs=["MyOrg"],
            file_glob=".github/workflows/*.yml",
            find=r"MyOrg/actions@v1",
            replace=r"MyOrg/actions@v2",
            branch="stuc/cli-test",
            commit_msg="chore: cli test",
            pr_title="CLI test",
            pr_body="Test body.",
        )
        path = campaign.save()
        assert path.exists()

        loaded = Campaign.load("cli-test")
        assert loaded.orgs == ["MyOrg"]
        assert loaded.find == r"MyOrg/actions@v1"


def test_init_llm_campaign(tmp_path):
    """LLM campaign can be created and loaded."""
    with patch("stuc.campaign.CAMPAIGNS_DIR", tmp_path):
        campaign = Campaign(
            name="llm-cli-test",
            mode="llm",
            orgs=["MyOrg"],
            file_glob="*.md",
            prompt="Add a license section",
            search_term="README",
            branch="stuc/llm-test",
            commit_msg="docs: add license",
            pr_title="Add license",
            pr_body="Test body.",
        )
        path = campaign.save()
        assert path.exists()

        loaded = Campaign.load("llm-cli-test")
        assert loaded.mode == "llm"
        assert loaded.prompt == "Add a license section"
        assert loaded.search_term == "README"
        assert loaded.find == ""


def test_cli_init_regex_requires_find_replace():
    """Regex mode fails without --find and --replace."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "stuc.cli",
            "init",
            "test",
            "--org",
            "Org",
            "--file-glob",
            "*.yml",
            "--branch",
            "b",
            "--commit-msg",
            "c",
            "--pr-title",
            "t",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "required" in result.stderr.lower() or "find" in result.stderr.lower()


def test_cli_init_llm_requires_prompt():
    """LLM mode fails without --prompt."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "stuc.cli",
            "init",
            "test",
            "--mode",
            "llm",
            "--org",
            "Org",
            "--file-glob",
            "*.yml",
            "--search-term",
            "foo",
            "--branch",
            "b",
            "--commit-msg",
            "c",
            "--pr-title",
            "t",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "prompt" in result.stderr.lower()


def test_cli_init_llm_requires_search_term():
    """LLM mode fails without --search-term."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "stuc.cli",
            "init",
            "test",
            "--mode",
            "llm",
            "--org",
            "Org",
            "--file-glob",
            "*.yml",
            "--prompt",
            "do something",
            "--branch",
            "b",
            "--commit-msg",
            "c",
            "--pr-title",
            "t",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "search-term" in result.stderr.lower()


def test_init_create_campaign(tmp_path):
    """Create-mode campaign can be created and loaded."""
    with patch("stuc.campaign.CAMPAIGNS_DIR", tmp_path):
        campaign = Campaign(
            name="create-cli-test",
            mode="create",
            orgs=["MyOrg"],
            file_glob=".github/dependabot.yml",
            prompt="Create a Dependabot config",
            branch="stuc/create-test",
            commit_msg="ci: add dependabot",
            pr_title="Add Dependabot",
            pr_body="Test body.",
        )
        path = campaign.save()
        assert path.exists()

        loaded = Campaign.load("create-cli-test")
        assert loaded.mode == "create"
        assert loaded.prompt == "Create a Dependabot config"
        assert loaded.file_glob == ".github/dependabot.yml"
        assert loaded.find == ""


def test_cli_init_create_requires_prompt():
    """Create mode fails without --prompt."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "stuc.cli",
            "init",
            "test",
            "--mode",
            "create",
            "--org",
            "Org",
            "--file-glob",
            ".github/dependabot.yml",
            "--branch",
            "b",
            "--commit-msg",
            "c",
            "--pr-title",
            "t",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "prompt" in result.stderr.lower()


def test_cli_init_create_rejects_wildcards():
    """Create mode rejects glob wildcards in --file-glob."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "stuc.cli",
            "init",
            "test",
            "--mode",
            "create",
            "--org",
            "Org",
            "--file-glob",
            "*.yml",
            "--prompt",
            "create something",
            "--branch",
            "b",
            "--commit-msg",
            "c",
            "--pr-title",
            "t",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "wildcard" in result.stderr.lower() or "exact" in result.stderr.lower()


def test_cli_help():
    """CLI --help should exit 0."""
    result = subprocess.run(
        [sys.executable, "-m", "stuc.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "stuc" in result.stdout
