"""LLM-powered file transformation via the claude CLI."""

import shutil
import subprocess
from pathlib import Path


def transform_file(content: str, prompt: str, context: str = "", file_path: str = "") -> str:
    """Transform file content using claude -p.

    Args:
        content: The original file content.
        prompt: The transformation instruction.
        context: Optional context from a context file.
        file_path: Optional file path for context in the prompt.

    Returns:
        The transformed file content.

    Raises:
        FileNotFoundError: If the claude CLI is not on PATH.
        TimeoutError: If the claude CLI call exceeds the timeout.
        RuntimeError: If claude returns empty output or a non-zero exit code.
    """
    if not shutil.which("claude"):
        raise FileNotFoundError(
            "The 'claude' CLI is not installed or not on PATH. "
            "Install it from https://claude.ai/code"
        )

    parts = [
        "You are a code transformation tool. Output ONLY the complete transformed file content.",
        "No explanations, no markdown code fences, no commentary.",
    ]
    if file_path:
        parts.append(f"\nFile: {file_path}")
    parts.append(f"\n<file>\n{content}\n</file>")
    if context:
        parts.append(f"\n<context>\n{context}\n</context>")
    parts.append(f"\nInstruction: {prompt}")

    full_prompt = "\n".join(parts)

    result = subprocess.run(
        ["claude", "-p", full_prompt],
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed (exit {result.returncode}): {result.stderr.strip()}")

    output = result.stdout
    if not output.strip():
        raise RuntimeError("claude -p returned empty output")

    return output


def validate_output(validation_cmd: str, file_path: str, repo_dir: Path) -> tuple[bool, str]:
    """Run a validation shell command in the repo directory.

    Args:
        validation_cmd: Shell command to run.
        file_path: Path to the file being validated (available as $FILE in the command).
        repo_dir: Working directory for the command.

    Returns:
        Tuple of (passed, error_message).
    """
    result = subprocess.run(
        validation_cmd,
        shell=True,
        cwd=repo_dir,
        capture_output=True,
        text=True,
        timeout=60,
        env={"FILE": file_path},
    )
    if result.returncode == 0:
        return True, ""
    return False, result.stderr.strip() or result.stdout.strip()
