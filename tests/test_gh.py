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


def test_search_code_empty():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="",
        )
        results = gh.search_code("nothing", owner="Org")
        assert results == []
