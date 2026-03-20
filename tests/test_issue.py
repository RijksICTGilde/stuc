"""Tests for issue body formatting and parsing."""

from stuc.campaign import Campaign
from stuc.issue import (
    STATUS_TABLE_END,
    STATUS_TABLE_START,
    STUC_DATA_MARKER,
    extract_campaign_from_issue,
    format_issue_body,
    format_pr_body,
    is_issue_url,
    update_status_table,
)


def _make_campaign(**overrides) -> Campaign:
    defaults = {
        "name": "test-campaign",
        "orgs": ["TestOrg"],
        "file_glob": ".github/workflows/*.yml",
        "find": r"TestOrg/actions@v1",
        "replace": r"TestOrg/actions@v2",
        "branch": "stuc/test",
        "commit_msg": "chore: test",
        "pr_title": "Test migration",
        "pr_body": "Automated test.",
    }
    defaults.update(overrides)
    return Campaign(**defaults)


def test_format_issue_body():
    campaign = _make_campaign()
    body = format_issue_body(campaign)

    # Contains campaign definition table
    assert "| Mode | `regex` |" in body
    assert "| Orgs | TestOrg |" in body
    assert "| Find |" in body
    assert "| Replace |" in body

    # Contains YAML data block
    assert STUC_DATA_MARKER in body

    # Contains status table markers
    assert STATUS_TABLE_START in body
    assert STATUS_TABLE_END in body

    # Contains stuc footer
    assert "stuc" in body


def test_format_issue_body_llm_mode():
    campaign = _make_campaign(mode="llm", find="", replace="", prompt="Add license")
    body = format_issue_body(campaign)

    assert "| Mode | `llm` |" in body
    assert "| Prompt | Add license |" in body
    assert "Find" not in body


def test_format_issue_body_with_prs():
    campaign = _make_campaign(prs={"TestOrg/repo1": "https://github.com/TestOrg/repo1/pull/42"})
    body = format_issue_body(campaign)

    assert "TestOrg/repo1" in body
    assert "TestOrg/repo1#42" in body


def test_format_pr_body_with_issue():
    body = format_pr_body("Original body", issue_url="https://github.com/Org/repo/issues/1")

    assert "Original body" in body
    assert "Part of campaign: https://github.com/Org/repo/issues/1" in body
    assert "stuc" in body


def test_format_pr_body_without_issue():
    body = format_pr_body("Original body")

    assert "Original body" in body
    assert "Part of campaign" not in body
    assert "stuc" in body


def test_extract_campaign_roundtrip():
    original = _make_campaign()
    body = format_issue_body(original)
    extracted = extract_campaign_from_issue(body)

    assert extracted.name == original.name
    assert extracted.orgs == original.orgs
    assert extracted.file_glob == original.file_glob
    assert extracted.find == original.find
    assert extracted.replace == original.replace
    assert extracted.branch == original.branch
    assert extracted.mode == original.mode


def test_extract_campaign_preserves_prs():
    prs = {
        "Org/repo1": "https://github.com/Org/repo1/pull/1",
        "Org/repo2": "https://github.com/Org/repo2/pull/2",
    }
    original = _make_campaign(prs=prs)
    body = format_issue_body(original)
    extracted = extract_campaign_from_issue(body)

    assert extracted.prs == prs


def test_is_issue_url():
    assert is_issue_url("https://github.com/MyOrg/fleet-ops/issues/42")
    assert is_issue_url("https://github.com/org/repo/issues/1")
    assert not is_issue_url("not-a-url")
    assert not is_issue_url("https://github.com/org/repo/pull/1")
    assert not is_issue_url("https://github.com/org/repo/issues/")
    assert not is_issue_url("")


def test_update_status_table():
    campaign = _make_campaign(prs={"Org/repo1": "https://github.com/Org/repo1/pull/1"})
    body = format_issue_body(campaign)

    rows = [
        {"repo": "Org/repo1", "pr_url": "https://github.com/Org/repo1/pull/1", "state": "open", "ci": "pass", "merge": "ready"},
    ]
    updated = update_status_table(body, rows)

    assert "| State | CI | Merge |" in updated
    assert "| open | pass | ready |" in updated
    # Original status table markers still present
    assert STATUS_TABLE_START in updated
    assert STATUS_TABLE_END in updated


def test_update_status_table_empty_rows():
    campaign = _make_campaign()
    body = format_issue_body(campaign)

    updated = update_status_table(body, [])
    assert "_No PRs created yet._" in updated


def test_update_status_table_no_markers():
    """Body without markers is returned unchanged."""
    body = "Some random issue body"
    result = update_status_table(body, [{"repo": "x", "pr_url": "y", "state": "z", "ci": "a", "merge": "b"}])
    assert result == body
