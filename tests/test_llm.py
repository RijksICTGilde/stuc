"""Tests for the LLM module."""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from stuc.llm import transform_file, validate_output


def test_transform_file_basic():
    """transform_file calls claude -p and returns stdout."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "transformed content"

    with patch("shutil.which", return_value="/usr/bin/claude"), \
         patch("subprocess.run", return_value=mock_result) as mock_run:
        result = transform_file("original", "add a header")

    assert result == "transformed content"
    args = mock_run.call_args
    assert args[0][0][0] == "claude"
    assert args[0][0][1] == "-p"
    assert "original" in args[0][0][2]
    assert "add a header" in args[0][0][2]


def test_transform_file_with_context():
    """Context is included in the prompt when provided."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "output"

    with patch("shutil.which", return_value="/usr/bin/claude"), \
         patch("subprocess.run", return_value=mock_result) as mock_run:
        transform_file("content", "instruction", context="extra context", file_path="test.md")

    prompt = mock_run.call_args[0][0][2]
    assert "<context>" in prompt
    assert "extra context" in prompt
    assert "File: test.md" in prompt


def test_transform_file_no_claude():
    """Raises FileNotFoundError when claude is not on PATH."""
    with patch("shutil.which", return_value=None):
        with pytest.raises(FileNotFoundError, match="claude"):
            transform_file("content", "instruction")


def test_transform_file_nonzero_exit():
    """Raises RuntimeError on non-zero exit code."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "something went wrong"

    with patch("shutil.which", return_value="/usr/bin/claude"), \
         patch("subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="failed"):
            transform_file("content", "instruction")


def test_transform_file_empty_output():
    """Raises RuntimeError on empty output."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "   "

    with patch("shutil.which", return_value="/usr/bin/claude"), \
         patch("subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="empty"):
            transform_file("content", "instruction")


def test_transform_file_timeout():
    """Raises TimeoutError when claude takes too long."""
    with patch("shutil.which", return_value="/usr/bin/claude"), \
         patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=300)):
        with pytest.raises(subprocess.TimeoutExpired):
            transform_file("content", "instruction")


def test_validate_output_pass(tmp_path):
    """Validation passes when command exits 0."""
    passed, err = validate_output("true", "test.py", tmp_path)
    assert passed is True
    assert err == ""


def test_validate_output_fail(tmp_path):
    """Validation fails when command exits non-zero."""
    passed, err = validate_output("false", "test.py", tmp_path)
    assert passed is False
