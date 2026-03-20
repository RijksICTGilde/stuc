"""Tests for gh wrapper — unit tests that mock subprocess."""

from unittest.mock import MagicMock, patch

import pytest

from stuc import gh


def test_run_success():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="hello\n",
            stderr="",
        )
        result = gh.run(["version"])
        assert result == "hello"
        mock_run.assert_called_once()


def test_run_failure_exits():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="not found",
        )
        with pytest.raises(SystemExit):
            gh.run(["nonexistent"])


def test_search_code_parses_json():
    json_output = '[{"repository": "Org/repo1", "path": ".github/workflows/deploy.yml"}]'
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json_output,
            stderr="",
        )
        results = gh.search_code("pattern", owner="Org")
        assert len(results) == 1
        assert results[0]["repository"] == "Org/repo1"


def test_create_issue():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="https://github.com/Org/repo/issues/99\n",
            stderr="",
        )
        url = gh.create_issue("Org/repo", "Title", "Body text")
        assert url == "https://github.com/Org/repo/issues/99"
        cmd = mock_run.call_args[0][0]
        assert cmd[:2] == ["gh", "issue"]
        assert "create" in cmd


def test_get_issue():
    import json as json_mod

    issue_data = {"body": "hello", "title": "T", "number": 1, "url": "https://github.com/Org/repo/issues/1"}
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json_mod.dumps(issue_data),
            stderr="",
        )
        result = gh.get_issue("https://github.com/Org/repo/issues/1")
        assert result["body"] == "hello"
        assert result["number"] == 1


def test_update_issue():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="",
        )
        gh.update_issue("https://github.com/Org/repo/issues/1", "new body")
        cmd = mock_run.call_args[0][0]
        assert "edit" in cmd
        assert "--body" in cmd


def test_file_exists_true():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"name": "dependabot.yml", "content": "..."}',
            stderr="",
        )
        assert gh.file_exists("Org/repo", ".github/dependabot.yml") is True


def test_file_exists_false():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Not Found",
        )
        assert gh.file_exists("Org/repo", ".github/dependabot.yml") is False


def test_search_code_empty():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="",
        )
        results = gh.search_code("nothing", owner="Org")
        assert results == []
