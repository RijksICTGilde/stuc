"""Tests for discovery module."""

from unittest.mock import patch

from stuc.campaign import Campaign
from stuc.discover import _build_search_query, _extract_search_term, _show_inline_diff, discover_repos, preview_changes


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
    result = _extract_search_term(r"RijksICTGilde/zad-actions/([a-z-]+)@[0-9a-f]{40}\s+#\s*v[12]\.[0-9]+\.[0-9]+")
    assert "RijksICTGilde/zad-actions" in result


def test_extract_search_term_combined_alternation():
    """Combined regex with alternation (tag|sha) should extract clean prefix."""
    result = _extract_search_term(
        r"RijksICTGilde/zad-actions/([a-z-]+)@(v[12](\.[0-9]+\.[0-9]+)?|[0-9a-f]{40}\s+#\s*v[12]\.[0-9]+\.[0-9]+)\b"
    )
    assert result == "RijksICTGilde/zad-actions"


def test_build_search_query_with_dir_and_ext():
    """Adds extension: qualifier from file glob (path: is skipped for reliability)."""
    result = _build_search_query("my-action", ".github/workflows/*.yml")
    assert result == "my-action extension:yml"


def test_build_search_query_no_dir():
    """Glob without directory only adds language."""
    assert _build_search_query("README", "*.md") == "README extension:md"


def test_build_search_query_exact_path():
    """Exact path uses extension: only (path: is skipped for reliability)."""
    assert _build_search_query("dependabot", ".github/dependabot.yml") == "dependabot extension:yml"


def test_build_search_query_no_glob():
    """Empty glob adds no qualifiers."""
    assert _build_search_query("foo", "") == "foo"


def test_build_search_query_slash_in_search_term():
    """Skip path: qualifier when search term contains slashes."""
    result = _build_search_query("aquasecurity/trivy-action", ".github/workflows/*.yml")
    assert result == "aquasecurity/trivy-action extension:yml"


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

    # Verify search was called with the explicit search_term + path qualifiers
    mock_search.assert_called_once_with("README extension:md", owner="TestOrg")
    assert len(results) == 1
    assert results[0]["repo"] == "TestOrg/repo1"


def _make_create_campaign(**overrides):
    defaults = {
        "name": "create-test",
        "mode": "create",
        "orgs": ["TestOrg"],
        "file_glob": ".github/dependabot.yml",
        "prompt": "Create a Dependabot config",
        "branch": "stuc/test",
        "commit_msg": "ci: add dependabot",
        "pr_title": "Add Dependabot",
        "pr_body": "test",
    }
    defaults.update(overrides)
    return Campaign(**defaults)


def test_discover_repos_create_finds_missing():
    """Create mode returns repos where the target file is missing."""
    campaign = _make_create_campaign()

    with (
        patch("stuc.discover.gh.list_org_repos", return_value=["TestOrg/repo1", "TestOrg/repo2"]),
        patch("stuc.discover.gh.file_exists", side_effect=[False, True]),
    ):
        results = discover_repos(campaign)

    assert len(results) == 1
    assert results[0]["repo"] == "TestOrg/repo1"
    assert results[0]["path"] == ".github/dependabot.yml"


def test_discover_repos_create_skips_existing():
    """Create mode skips repos that already have the target file."""
    campaign = _make_create_campaign()

    with (
        patch("stuc.discover.gh.list_org_repos", return_value=["TestOrg/repo1"]),
        patch("stuc.discover.gh.file_exists", return_value=True),
    ):
        results = discover_repos(campaign)

    assert results == []


def test_discover_repos_create_respects_excludes():
    """Create mode respects the exclude_repos list."""
    campaign = _make_create_campaign(exclude_repos=["TestOrg/repo1"])

    with (
        patch("stuc.discover.gh.list_org_repos", return_value=["TestOrg/repo1", "TestOrg/repo2"]),
        patch("stuc.discover.gh.file_exists", return_value=False) as mock_exists,
    ):
        results = discover_repos(campaign)

    # file_exists should only be called for repo2 (repo1 is excluded)
    mock_exists.assert_called_once_with("TestOrg/repo2", ".github/dependabot.yml")
    assert len(results) == 1
    assert results[0]["repo"] == "TestOrg/repo2"


def test_show_inline_diff_new_file():
    """Empty before shows all-green additions, capped at 20 lines."""
    import io

    from rich.console import Console

    content = "\n".join(f"line {i}" for i in range(25))
    buf = io.StringIO()
    with patch("stuc.discover.console", Console(file=buf)):
        _show_inline_diff("", content)
    output = buf.getvalue()
    # Should show first 20 lines as additions, plus "... 5 more lines"
    assert "line 0" in output
    assert "line 19" in output
    assert "line 20" not in output
    assert "5 more lines" in output


def test_preview_changes_create_calls_llm():
    """Create-mode preview calls transform_file with empty content."""
    campaign = _make_create_campaign()
    hits = [{"repo": "TestOrg/repo1", "path": ".github/dependabot.yml"}]

    with patch("stuc.llm.transform_file", return_value="generated: yaml content\n") as mock_tf:
        result = preview_changes(campaign, hits)

    mock_tf.assert_called_once_with("", "Create a Dependabot config", context="", file_path=".github/dependabot.yml")
    assert "TestOrg/repo1" in result
    assert result["TestOrg/repo1"][0]["before"] == ""
    assert "generated" in result["TestOrg/repo1"][0]["after"]
