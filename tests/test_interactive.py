"""Tests for interactive prompts."""

from unittest.mock import MagicMock, patch

from stuc.campaign import Campaign
from stuc.interactive import InitParams, confirm_apply, init_wizard, review_plan


def _mock_ask(return_value):
    """Create a mock that has an .ask() method returning return_value."""
    m = MagicMock()
    m.ask.return_value = return_value
    return m


class TestInitWizard:
    def test_full_regex_flow(self):
        """All prompts answered for regex mode, no orgs from gh."""
        side_effects = [
            _mock_ask("regex"),  # mode select
            _mock_ask("MyOrg"),  # first org
            _mock_ask(""),  # empty to finish orgs
            _mock_ask("*.yml"),  # file_glob
            _mock_ask("foo"),  # find
            _mock_ask("bar"),  # replace
            _mock_ask("stuc/test"),  # branch
            _mock_ask("chore: test"),  # commit_msg
            _mock_ask("Test PR"),  # pr_title
            _mock_ask("Automated migration by stuc."),  # pr_body
            _mock_ask(""),  # exclude repos
            _mock_ask(""),  # issue_repo
        ]

        with (
            patch("stuc.interactive.gh.list_user_orgs", return_value=[]),
            patch("stuc.interactive.questionary.select", return_value=side_effects[0]),
            patch("stuc.interactive.questionary.text", side_effect=side_effects[1:]),
        ):
            result = init_wizard(InitParams(name="test"))

        assert result.mode == "regex"
        assert result.org == ["MyOrg"]
        assert result.file_glob == "*.yml"
        assert result.find == "foo"
        assert result.replace == "bar"
        assert result.branch == "stuc/test"
        assert result.commit_msg == "chore: test"
        assert result.pr_title == "Test PR"

    def test_orgs_from_gh_checkbox(self):
        """When gh returns orgs, show checkbox for selection."""
        text_side_effects = [
            _mock_ask("*.yml"),  # file_glob
            _mock_ask("pattern"),  # find
            _mock_ask("replacement"),  # replace
            _mock_ask("stuc/test"),  # branch
            _mock_ask("msg"),  # commit_msg
            _mock_ask("title"),  # pr_title
            _mock_ask("body"),  # pr_body
            _mock_ask(""),  # exclude repos
            _mock_ask(""),  # issue_repo
        ]

        with (
            patch("stuc.interactive.gh.list_user_orgs", return_value=["OrgA", "OrgB", "OrgC"]),
            patch("stuc.interactive.questionary.checkbox", return_value=_mock_ask(["OrgA", "OrgC"])),
            patch("stuc.interactive.questionary.text", side_effect=text_side_effects),
        ):
            result = init_wizard(InitParams(name="test", mode="regex"))

        assert result.org == ["OrgA", "OrgC"]

    def test_skips_provided_fields(self):
        """Fields already provided are not prompted."""
        side_effects = [
            _mock_ask("*.yml"),  # file_glob
            _mock_ask("pattern"),  # find
            _mock_ask("replacement"),  # replace
            _mock_ask("stuc/test"),  # branch
            _mock_ask("msg"),  # commit_msg
            _mock_ask("title"),  # pr_title
            _mock_ask("body"),  # pr_body
            _mock_ask(""),  # exclude repos
            _mock_ask(""),  # issue_repo
        ]

        with patch("stuc.interactive.questionary.text", side_effect=side_effects):
            result = init_wizard(InitParams(name="test", mode="regex", org=["PresetOrg"]))

        # org was already set, not prompted
        assert result.org == ["PresetOrg"]
        assert result.file_glob == "*.yml"

    def test_llm_mode(self):
        """LLM mode prompts for prompt and search_term."""
        side_effects = [
            _mock_ask("llm"),  # mode select
            _mock_ask("*.md"),  # file_glob
            _mock_ask("Do something"),  # prompt
            _mock_ask("README"),  # search_term
            _mock_ask("stuc/test"),  # branch
            _mock_ask("msg"),  # commit_msg
            _mock_ask("title"),  # pr_title
            _mock_ask("body"),  # pr_body
            _mock_ask(""),  # exclude repos
            _mock_ask(""),  # issue_repo
            _mock_ask(""),  # context_file
            _mock_ask(""),  # validation
        ]

        with (
            patch("stuc.interactive.gh.list_user_orgs", return_value=["MyOrg"]),
            patch("stuc.interactive.questionary.select", return_value=side_effects[0]),
            patch("stuc.interactive.questionary.checkbox", return_value=_mock_ask(["MyOrg"])),
            patch("stuc.interactive.questionary.text", side_effect=side_effects[1:]),
        ):
            result = init_wizard(InitParams(name="test"))

        assert result.mode == "llm"
        assert result.prompt == "Do something"
        assert result.search_term == "README"

    def test_create_mode(self):
        """Create mode prompts for prompt, validates no wildcards."""
        side_effects = [
            _mock_ask("create"),  # mode select
            _mock_ask(".github/dependabot.yml"),  # file_glob (exact path)
            _mock_ask("Create dependabot config"),  # prompt
            _mock_ask("stuc/test"),  # branch
            _mock_ask("msg"),  # commit_msg
            _mock_ask("title"),  # pr_title
            _mock_ask("body"),  # pr_body
            _mock_ask(""),  # exclude repos
            _mock_ask(""),  # issue_repo
            _mock_ask(""),  # context_file
            _mock_ask(""),  # validation
        ]

        with (
            patch("stuc.interactive.gh.list_user_orgs", return_value=["MyOrg"]),
            patch("stuc.interactive.questionary.select", return_value=side_effects[0]),
            patch("stuc.interactive.questionary.checkbox", return_value=_mock_ask(["MyOrg"])),
            patch("stuc.interactive.questionary.text", side_effect=side_effects[1:]),
        ):
            result = init_wizard(InitParams(name="test"))

        assert result.mode == "create"
        assert result.prompt == "Create dependabot config"
        assert result.file_glob == ".github/dependabot.yml"


class TestReviewPlan:
    def test_exclude_repos(self, tmp_path):
        """User selects repos to exclude, campaign is saved."""
        with patch("stuc.campaign.CAMPAIGNS_DIR", tmp_path):
            campaign = Campaign(
                name="review-test",
                orgs=["Org"],
                file_glob="*.yml",
                find="a",
                replace="b",
                branch="b",
                commit_msg="c",
                pr_title="t",
            )
            campaign.save()

            changes = {
                "Org/repo1": [{"path": "f.yml"}],
                "Org/repo2": [{"path": "f.yml"}],
            }

            with (
                patch("stuc.interactive.sys.stdin") as mock_stdin,
                patch("stuc.interactive.questionary.checkbox") as mock_cb,
            ):
                mock_stdin.isatty.return_value = True
                mock_cb.return_value = _mock_ask(["Org/repo2"])
                review_plan(campaign, changes)

            assert "Org/repo2" in campaign.exclude_repos

    def test_no_exclusions(self, tmp_path):
        """User keeps all repos, no save needed."""
        with patch("stuc.campaign.CAMPAIGNS_DIR", tmp_path):
            campaign = Campaign(
                name="review-test2",
                orgs=["Org"],
                file_glob="*.yml",
                find="a",
                replace="b",
                branch="b",
                commit_msg="c",
                pr_title="t",
            )
            campaign.save()

            changes = {"Org/repo1": [{"path": "f.yml"}]}

            with (
                patch("stuc.interactive.sys.stdin") as mock_stdin,
                patch("stuc.interactive.questionary.checkbox") as mock_cb,
            ):
                mock_stdin.isatty.return_value = True
                mock_cb.return_value = _mock_ask([])
                review_plan(campaign, changes)

            assert campaign.exclude_repos == []


class TestConfirmApply:
    def test_confirm_yes(self):
        """User confirms, returns True."""
        campaign = Campaign(
            name="test",
            orgs=["Org"],
            file_glob="*.yml",
            find="a",
            replace="b",
            branch="b",
            commit_msg="c",
            pr_title="t",
        )
        changes = {"Org/repo1": [{"path": "f.yml"}]}

        with patch("stuc.interactive.questionary.confirm") as mock_confirm:
            mock_confirm.return_value = _mock_ask(True)
            result = confirm_apply(campaign, changes)

        assert result is True

    def test_confirm_no(self):
        """User declines, returns False."""
        campaign = Campaign(
            name="test",
            orgs=["Org"],
            file_glob="*.yml",
            find="a",
            replace="b",
            branch="b",
            commit_msg="c",
            pr_title="t",
        )
        changes = {"Org/repo1": [{"path": "f.yml"}]}

        with patch("stuc.interactive.questionary.confirm") as mock_confirm:
            mock_confirm.return_value = _mock_ask(False)
            result = confirm_apply(campaign, changes)

        assert result is False
