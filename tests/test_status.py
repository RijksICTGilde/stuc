"""Tests for status module."""

import json
from unittest.mock import MagicMock, call, patch

from stuc.campaign import Campaign
from stuc.status import show_status


def _make_campaign(**overrides):
    defaults = dict(
        name="test",
        orgs=["Org"],
        file_glob="*.yml",
        branch="stuc/test",
        prs={
            "Org/repo1": "https://github.com/Org/repo1/pull/1",
            "Org/repo2": "https://github.com/Org/repo2/pull/2",
        },
        issue_url="https://github.com/Org/ops/issues/9",
    )
    defaults.update(overrides)
    return Campaign(**defaults)


def _mock_pr_status(state):
    return {"state": state, "statusCheckRollup": [], "mergeStateStatus": "UNKNOWN"}


@patch("stuc.status.gh")
def test_closes_issue_when_all_merged(mock_gh):
    mock_gh.pr_status.return_value = _mock_pr_status("MERGED")
    mock_gh.get_issue.return_value = {"body": "<!-- stuc-status-start -->\n<!-- stuc-status-end -->"}

    campaign = _make_campaign()
    show_status(campaign, refresh=True)

    mock_gh.close_issue.assert_called_once_with("https://github.com/Org/ops/issues/9")


@patch("stuc.status.gh")
def test_does_not_close_issue_when_pr_still_open(mock_gh):
    def pr_status_side_effect(repo, branch):
        if repo == "Org/repo1":
            return _mock_pr_status("MERGED")
        return _mock_pr_status("OPEN")

    mock_gh.pr_status.side_effect = pr_status_side_effect
    mock_gh.get_issue.return_value = {"body": "<!-- stuc-status-start -->\n<!-- stuc-status-end -->"}

    campaign = _make_campaign()
    show_status(campaign, refresh=True)

    mock_gh.close_issue.assert_not_called()


@patch("stuc.status.gh")
def test_closes_issue_when_all_closed(mock_gh):
    mock_gh.pr_status.return_value = _mock_pr_status("CLOSED")
    mock_gh.get_issue.return_value = {"body": "<!-- stuc-status-start -->\n<!-- stuc-status-end -->"}

    campaign = _make_campaign()
    show_status(campaign, refresh=True)

    mock_gh.close_issue.assert_called_once()


@patch("stuc.status.gh")
def test_does_not_close_without_issue_url(mock_gh):
    mock_gh.pr_status.return_value = _mock_pr_status("MERGED")

    campaign = _make_campaign(issue_url="")
    show_status(campaign, refresh=True)

    mock_gh.close_issue.assert_not_called()


@patch("stuc.status.gh")
def test_skipped_prs_ignored_for_close_check(mock_gh):
    """ERROR/SKIPPED PRs should not prevent closing the issue."""
    campaign = _make_campaign(
        prs={
            "Org/repo1": "https://github.com/Org/repo1/pull/1",
            "Org/repo2": "SKIPPED: already has branch",
        },
    )
    mock_gh.pr_status.return_value = _mock_pr_status("MERGED")
    mock_gh.get_issue.return_value = {"body": "<!-- stuc-status-start -->\n<!-- stuc-status-end -->"}

    show_status(campaign, refresh=True)

    mock_gh.close_issue.assert_called_once()
