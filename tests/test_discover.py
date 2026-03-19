"""Tests for discovery module."""

from unittest.mock import patch, MagicMock

from stuc.campaign import Campaign
from stuc.discover import _extract_search_term, discover_repos


def test_extract_search_term_action_ref():
    assert _extract_search_term("RijksICTGilde/zad-actions/([^@]+)@v2") == "RijksICTGilde/zad-actions"


def test_extract_search_term_simple():
    assert _extract_search_term("some-org/some-action@v1") == "some-org/some-action"


def test_extract_search_term_no_version():
    assert _extract_search_term("org/repo/action") == "org/repo/action"


def test_extract_search_term_complex_regex():
    result = _extract_search_term(r"actions/checkout@v\d+")
    assert "actions/checkout" in result


def test_extract_search_term_literal_inside_group():
    """Literal text inside capture groups should be preserved."""
    result = _extract_search_term(r"(RijksICTGilde/zad-actions/[a-z-]+)@v[12]\b")
    assert "RijksICTGilde/zad-actions" in result


def test_extract_search_term_sha_pinned():
    """SHA-pinned action references should extract the org/repo prefix."""
    result = _extract_search_term(
        r"RijksICTGilde/zad-actions/([a-z-]+)@[0-9a-f]{40}\s+#\s*v[12]\.[0-9]+\.[0-9]+"
    )
    assert "RijksICTGilde/zad-actions" in result


def test_extract_search_term_combined_alternation():
    """Combined regex with alternation (tag|sha) should extract clean prefix."""
    result = _extract_search_term(
        r"RijksICTGilde/zad-actions/([a-z-]+)@(v[12](\.[0-9]+\.[0-9]+)?|[0-9a-f]{40}\s+#\s*v[12]\.[0-9]+\.[0-9]+)\b"
    )
    assert result == "RijksICTGilde/zad-actions"


def test_discover_repos_llm_uses_search_term():
    """LLM mode uses campaign.search_term instead of extracting from find pattern."""
    campaign = Campaign(
        name="llm-discover",
        mode="llm",
        orgs=["TestOrg"],
        file_glob="*.md",
        search_term="README",
        prompt="Add license",
        branch="stuc/test",
        commit_msg="test",
        pr_title="test",
        pr_body="test",
    )

    mock_hits = [
        {"repository": {"nameWithOwner": "TestOrg/repo1"}, "path": "README.md"},
    ]

    with patch("stuc.discover.gh.search_code", return_value=mock_hits) as mock_search:
        results = discover_repos(campaign)

    # Verify search was called with the explicit search_term, not extracted from find
    mock_search.assert_called_once_with("README", owner="TestOrg")
    assert len(results) == 1
    assert results[0]["repo"] == "TestOrg/repo1"
