"""Tests for campaign CRUD."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from stuc.campaign import Campaign, CAMPAIGNS_DIR


def test_campaign_save_and_load(tmp_path):
    with patch.object(Campaign, "path", new_callable=lambda: property(lambda self: tmp_path / f"{self.name}.yml")):
        # Patch CAMPAIGNS_DIR for load
        campaign = Campaign(
            name="test-campaign",
            orgs=["TestOrg"],
            file_glob=".github/workflows/*.yml",
            find=r"TestOrg/actions/([^@]+)@v1",
            replace=r"TestOrg/actions/\1@v2",
            branch="stuc/test",
            commit_msg="chore: test migration",
            pr_title="Test migration",
            pr_body="Automated test.",
        )
        campaign.save()
        assert (tmp_path / "test-campaign.yml").exists()


def test_campaign_roundtrip(tmp_path):
    """Campaign data survives a save/load cycle."""
    campaign_file = tmp_path / "roundtrip.yml"

    with patch("stuc.campaign.CAMPAIGNS_DIR", tmp_path):
        original = Campaign(
            name="roundtrip",
            orgs=["OrgA", "OrgB"],
            file_glob="**/*.yml",
            find=r"foo@v1",
            replace=r"foo@v2",
            branch="stuc/roundtrip",
            commit_msg="chore: roundtrip",
            pr_title="Roundtrip PR",
            pr_body="Body text.",
            exclude_repos=["OrgA/skip-me"],
            prs={"OrgA/repo1": "https://github.com/OrgA/repo1/pull/1"},
        )
        original.save()

        loaded = Campaign.load("roundtrip")
        assert loaded.name == original.name
        assert loaded.orgs == original.orgs
        assert loaded.find == original.find
        assert loaded.replace == original.replace
        assert loaded.exclude_repos == original.exclude_repos
        assert loaded.prs == original.prs


def test_campaign_list_all(tmp_path):
    with patch("stuc.campaign.CAMPAIGNS_DIR", tmp_path):
        assert Campaign.list_all() == []

        (tmp_path / "alpha.yml").write_text("name: alpha\n")
        (tmp_path / "beta.yml").write_text("name: beta\n")
        result = Campaign.list_all()
        assert sorted(result) == ["alpha", "beta"]


def test_campaign_delete(tmp_path):
    with patch("stuc.campaign.CAMPAIGNS_DIR", tmp_path):
        campaign = Campaign(
            name="to-delete",
            orgs=["TestOrg"],
            file_glob="*.yml",
            find="foo",
            replace="bar",
            branch="stuc/delete",
            commit_msg="chore: delete",
            pr_title="Delete",
            pr_body="",
        )
        campaign.save()
        assert (tmp_path / "to-delete.yml").exists()

        campaign.delete()
        assert not (tmp_path / "to-delete.yml").exists()


def test_campaign_delete_not_found(tmp_path):
    import pytest

    with patch("stuc.campaign.CAMPAIGNS_DIR", tmp_path):
        campaign = Campaign(
            name="nonexistent",
            orgs=["TestOrg"],
            file_glob="*.yml",
            find="foo",
            replace="bar",
            branch="stuc/nope",
            commit_msg="chore: nope",
            pr_title="Nope",
            pr_body="",
        )
        with pytest.raises(FileNotFoundError):
            campaign.delete()
