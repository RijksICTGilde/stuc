"""Tests for discovery module."""

from stuc.discover import _extract_search_term


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
