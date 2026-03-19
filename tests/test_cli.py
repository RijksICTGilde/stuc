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


def test_cli_help():
    """CLI --help should exit 0."""
    result = subprocess.run(
        [sys.executable, "-m", "stuc.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "stuc" in result.stdout
