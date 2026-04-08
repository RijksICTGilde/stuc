"""Thin wrapper around the gh CLI."""

import json
import subprocess
import sys
import time
from pathlib import Path

MAX_RETRIES = 3
INITIAL_BACKOFF = 5  # seconds


def _is_rate_limit_error(stderr: str) -> bool:
    """Check if a gh CLI error is a GitHub rate limit (HTTP 403/429)."""
    return "rate limit" in stderr.lower() or "HTTP 429" in stderr


def _exec(args: list[str], capture: bool = True, cwd: str | Path | None = None) -> subprocess.CompletedProcess[str]:
    """Execute a gh CLI command and return the CompletedProcess."""
    return subprocess.run(
        ["gh"] + args,
        capture_output=capture,
        text=True,
        check=False,
        cwd=cwd,
    )


def _check_result(result: subprocess.CompletedProcess[str], args: list[str]) -> None:
    """Raise SystemExit with error details if the command failed."""
    if result.returncode != 0:
        print(f"gh command failed: gh {' '.join(args)}", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        raise SystemExit(1)


def run(args: list[str], capture: bool = True, check: bool = True, cwd: str | Path | None = None) -> str:
    """Run a gh CLI command and return stdout."""
    result = _exec(args, capture=capture, cwd=cwd)
    if check:
        _check_result(result, args)
    return result.stdout.strip() if capture else ""


def _run_with_retry(args: list[str], capture: bool = True, check: bool = True, cwd: str | Path | None = None) -> str:
    """Run a gh CLI command with retry on rate limit errors. Use for read-only operations."""
    for attempt in range(MAX_RETRIES):
        result = _exec(args, capture=capture, cwd=cwd)
        if result.returncode == 0:
            return result.stdout.strip() if capture else ""

        if _is_rate_limit_error(result.stderr):
            wait = INITIAL_BACKOFF * (2**attempt)
            print(
                f"Rate limited by GitHub. Waiting {wait}s before retry ({attempt + 1}/{MAX_RETRIES})...",
                file=sys.stderr,
            )
            time.sleep(wait)
            continue

        if check:
            _check_result(result, args)
        return result.stdout.strip() if capture else ""

    # Exhausted retries
    print(f"gh command failed after {MAX_RETRIES} retries (rate limited): gh {' '.join(args)}", file=sys.stderr)
    raise SystemExit(1)


def run_json(args: list[str], cwd: str | Path | None = None) -> dict | list:
    """Run a gh CLI command and parse JSON output."""
    output = run(args + ["--json"] if "--json" not in args else args, cwd=cwd)
    return json.loads(output)


def search_code(query: str, owner: str, limit: int = 1000) -> list[dict]:
    """Search code across an org. Returns list of {repo, path} dicts."""
    args = [
        "search",
        "code",
        query,
        f"--owner={owner}",
        f"--limit={limit}",
        "--json",
        "repository,path",
    ]
    output = _run_with_retry(args)
    if not output:
        return []
    return json.loads(output)


def list_org_repos(org: str, limit: int = 1000) -> list[str]:
    """List all repos in an org. Returns list of full repo names (org/repo)."""
    output = _run_with_retry(
        [
            "repo",
            "list",
            org,
            "--limit",
            str(limit),
            "--json",
            "nameWithOwner",
            "--no-archived",
        ]
    )
    if not output:
        return []
    repos = json.loads(output)
    return [r["nameWithOwner"] for r in repos]


def list_user_orgs() -> list[str]:
    """List GitHub orgs the authenticated user belongs to. Returns list of org logins."""
    output = run(["org", "list"], check=False)
    if not output:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def clone_repo(repo: str, dest: Path, shallow: bool = True) -> None:
    """Clone a repo to dest."""
    args = ["repo", "clone", repo, str(dest)]
    if shallow:
        args += ["--", "--depth=1"]
    run(args, capture=False)


def create_pr(title: str, body: str, branch: str, base: str = "main", cwd: str | Path | None = None) -> str:
    """Create a PR and return its URL."""
    return run(
        [
            "pr",
            "create",
            "--title",
            title,
            "--body",
            body,
            "--head",
            branch,
            "--base",
            base,
        ],
        cwd=cwd,
    )


def pr_status(repo: str, branch: str) -> dict | None:
    """Get PR status for a branch. Returns dict with state, url, checks or None."""
    output = _run_with_retry(
        ["pr", "view", branch, "--repo", repo, "--json", "state,url,statusCheckRollup,mergeStateStatus"],
        check=False,
    )
    if not output:
        return None
    return json.loads(output)


def enable_auto_merge(pr_url: str) -> None:
    """Enable auto-merge on a PR."""
    run(["pr", "merge", pr_url, "--auto", "--squash"], check=False)


def get_default_branch(repo: str) -> str:
    """Get the default branch name for a repo."""
    output = _run_with_retry(["repo", "view", repo, "--json", "defaultBranchRef"])
    data = json.loads(output)
    return data.get("defaultBranchRef", {}).get("name", "main")


def create_issue(repo: str, title: str, body: str) -> str:
    """Create a GitHub issue and return its URL."""
    return run(["issue", "create", "--repo", repo, "--title", title, "--body", body])


def get_issue(issue_url: str) -> dict:
    """Get issue data (body, title, number, url) from a GitHub issue URL."""
    output = _run_with_retry(["issue", "view", issue_url, "--json", "body,title,number,url"])
    return json.loads(output)


def update_issue(issue_url: str, body: str) -> None:
    """Update the body of a GitHub issue."""
    run(["issue", "edit", issue_url, "--body", body])


def close_issue(issue_url: str) -> None:
    """Close a GitHub issue."""
    run(["issue", "close", issue_url])


def file_exists(repo: str, path: str) -> bool:
    """Check if a file exists in a repo via the GitHub API."""
    result = _run_with_retry(["api", f"repos/{repo}/contents/{path}"], check=False)
    return bool(result)


def pr_list(repo: str, head: str | None = None, state: str = "all") -> list[dict]:
    """List PRs for a repo, optionally filtered by head branch."""
    args = [
        "pr",
        "list",
        "--repo",
        repo,
        "--state",
        state,
        "--json",
        "number,state,url,headRefName,statusCheckRollup,mergeStateStatus",
    ]
    if head:
        args += ["--head", head]
    output = _run_with_retry(args, check=False)
    if not output:
        return []
    return json.loads(output)
