"""Tests for campaign CRUD."""

from unittest.mock import patch

from stuc.campaign import Campaign


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


def test_campaign_llm_roundtrip(tmp_path):
    """LLM campaign data survives a save/load cycle."""
    with patch("stuc.campaign.CAMPAIGNS_DIR", tmp_path):
        original = Campaign(
            name="llm-test",
            mode="llm",
            orgs=["OrgA"],
            file_glob="*.md",
            prompt="Add a license section",
            search_term="README",
            context_file="/tmp/context.md",
            validation="markdownlint $FILE",
            branch="stuc/llm-test",
            commit_msg="docs: add license",
            pr_title="Add license",
            pr_body="LLM-generated.",
        )
        original.save()

        loaded = Campaign.load("llm-test")
        assert loaded.mode == "llm"
        assert loaded.prompt == "Add a license section"
        assert loaded.search_term == "README"
        assert loaded.context_file == "/tmp/context.md"
        assert loaded.validation == "markdownlint $FILE"
        assert loaded.find == ""
        assert loaded.replace == ""


def test_campaign_create_roundtrip(tmp_path):
    """Create-mode campaign data survives a save/load cycle."""
    with patch("stuc.campaign.CAMPAIGNS_DIR", tmp_path):
        original = Campaign(
            name="create-test",
            mode="create",
            orgs=["OrgA"],
            file_glob=".github/dependabot.yml",
            prompt="Create a Dependabot config",
            branch="stuc/create-test",
            commit_msg="ci: add dependabot",
            pr_title="Add Dependabot",
            pr_body="Automated.",
        )
        original.save()

        loaded = Campaign.load("create-test")
        assert loaded.mode == "create"
        assert loaded.prompt == "Create a Dependabot config"
        assert loaded.file_glob == ".github/dependabot.yml"
        assert loaded.find == ""
        assert loaded.replace == ""


def test_campaign_backward_compat(tmp_path):
    """Old YAML files without mode field load as regex mode."""
    import yaml

    with patch("stuc.campaign.CAMPAIGNS_DIR", tmp_path):
        # Write a YAML file without mode/prompt/search_term fields
        data = {
            "name": "old-style",
            "orgs": ["Org"],
            "file_glob": "*.yml",
            "find": "foo",
            "replace": "bar",
            "branch": "stuc/old",
            "commit_msg": "chore",
            "pr_title": "Old",
            "pr_body": "",
        }
        (tmp_path / "old-style.yml").write_text(yaml.dump(data))

        loaded = Campaign.load("old-style")
        assert loaded.mode == "regex"
        assert loaded.prompt == ""
        assert loaded.search_term == ""
        assert loaded.context_file == ""
        assert loaded.validation == ""


def test_campaign_issue_fields_roundtrip(tmp_path):
    """issue_repo and issue_url survive a save/load cycle."""
    with patch("stuc.campaign.CAMPAIGNS_DIR", tmp_path):
        original = Campaign(
            name="issue-test",
            orgs=["Org"],
            file_glob="*.yml",
            find="foo",
            replace="bar",
            branch="stuc/issue",
            commit_msg="chore",
            pr_title="Test",
            pr_body="",
            issue_repo="Org/fleet-ops",
            issue_url="https://github.com/Org/fleet-ops/issues/42",
        )
        original.save()

        loaded = Campaign.load("issue-test")
        assert loaded.issue_repo == "Org/fleet-ops"
        assert loaded.issue_url == "https://github.com/Org/fleet-ops/issues/42"


def test_campaign_issue_fields_backward_compat(tmp_path):
    """Old YAML without issue fields loads with empty defaults."""
    import yaml

    with patch("stuc.campaign.CAMPAIGNS_DIR", tmp_path):
        data = {
            "name": "no-issue",
            "orgs": ["Org"],
            "file_glob": "*.yml",
            "find": "foo",
            "replace": "bar",
            "branch": "stuc/old",
            "commit_msg": "chore",
            "pr_title": "Old",
            "pr_body": "",
        }
        (tmp_path / "no-issue.yml").write_text(yaml.dump(data))

        loaded = Campaign.load("no-issue")
        assert loaded.issue_repo == ""
        assert loaded.issue_url == ""


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
