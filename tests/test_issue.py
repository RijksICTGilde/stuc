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

    assert "| Mode | `regex` |" in body
    assert "| Orgs | TestOrg |" in body
    assert "| Find |" in body
    assert "| Replace |" in body
    assert STUC_DATA_MARKER in body
    assert STATUS_TABLE_START in body
    assert STATUS_TABLE_END in body
    assert "stuc" in body


def test_format_issue_body_llm_mode():
    campaign = _make_campaign(mode="llm", find="", replace="", prompt="Add license")
    body = format_issue_body(campaign)

    assert "| Mode | `llm` |" in body
    assert "| Prompt | Add license |" in body
    assert "Find" not in body


def test_format_issue_body_create_mode():
    campaign = _make_campaign(mode="create", find="", replace="", prompt="Create a Dependabot config")
    body = format_issue_body(campaign)

    assert "| Mode | `create` |" in body
    assert "| File glob |" in body
    assert "| Prompt | Create a Dependabot config |" in body
    assert "Find" not in body
    assert "Replace" not in body


def test_format_issue_body_with_prs():
    campaign = _make_campaign(prs={"TestOrg/repo1": "https://github.com/TestOrg/repo1/pull/42"})
    body = format_issue_body(campaign)

    assert "TestOrg/repo1" in body
    assert "TestOrg/repo1#42" in body


def test_format_issue_body_escapes_pipes():
    """Pipe characters in regex patterns don't break the markdown table."""
    campaign = _make_campaign(find=r"(foo|bar)", replace=r"(baz|qux)")
    body = format_issue_body(campaign)

    # Pipes should be escaped in the table
    assert r"\|" in body
    # But the YAML block should have the original unescaped values
    extracted = extract_campaign_from_issue(body)
    assert extracted.find == r"(foo|bar)"
    assert extracted.replace == r"(baz|qux)"


def test_format_issue_body_with_error_prs():
    """ERROR/SKIPPED PR values don't produce broken markdown links."""
    campaign = _make_campaign(
        prs={
            "Org/ok": "https://github.com/Org/ok/pull/1",
            "Org/err": "ERROR: clone failed",
            "Org/skip": "SKIPPED: no changes",
        }
    )
    body = format_issue_body(campaign)

    # Real PR gets a link
    assert "[Org/ok#1]" in body
    # Error/skip get plain text, no broken links
    assert "](ERROR" not in body
    assert "](SKIPPED" not in body


def test_format_issue_body_includes_issue_repo():
    """issue_repo is included in the YAML block for roundtripping."""
    campaign = _make_campaign(issue_repo="Org/fleet-ops")
    body = format_issue_body(campaign)
    extracted = extract_campaign_from_issue(body)
    assert extracted.issue_repo == "Org/fleet-ops"


def test_format_issue_body_status_table_has_five_columns():
    """Initial status table uses the same 5-column format as updates."""
    campaign = _make_campaign(prs={"Org/repo1": "https://github.com/Org/repo1/pull/1"})
    body = format_issue_body(campaign)
    assert "| State | CI | Merge |" in body


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


def test_format_pr_body_idempotent():
    """Calling format_pr_body on an already-branded body doesn't double the footer."""
    first = format_pr_body("Original body", issue_url="https://github.com/Org/repo/issues/1")
    second = format_pr_body(first, issue_url="https://github.com/Org/repo/issues/1")
    assert first == second


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


def test_extract_campaign_missing_fields():
    """Gracefully handles missing fields with defaults."""
    minimal_body = f"```yaml\n{STUC_DATA_MARKER}\nname: minimal\nfile_glob: '*.txt'\n```"
    campaign = extract_campaign_from_issue(minimal_body)
    assert campaign.name == "minimal"
    assert campaign.orgs == []
    assert campaign.find == ""


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
        {
            "repo": "Org/repo1",
            "pr_url": "https://github.com/Org/repo1/pull/1",
            "state": "open",
            "ci": "pass",
            "merge": "ready",
        },
    ]
    updated = update_status_table(body, rows)

    assert "| State | CI | Merge |" in updated
    assert "| open | pass | ready |" in updated
    assert STATUS_TABLE_START in updated
    assert STATUS_TABLE_END in updated


def test_update_status_table_with_error_rows():
    """ERROR/SKIPPED rows don't produce broken markdown links."""
    campaign = _make_campaign(prs={"Org/err": "ERROR: failed"})
    body = format_issue_body(campaign)

    rows = [{"repo": "Org/err", "pr_url": "ERROR: failed", "state": "-", "ci": "-", "merge": "-"}]
    updated = update_status_table(body, rows)

    assert "](ERROR" not in updated


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
