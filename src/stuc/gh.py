"""Thin wrapper around the gh CLI."""

import json
import subprocess
import sys
from pathlib import Path


def run(args: list[str], capture: bool = True, check: bool = True, cwd: str | Path | None = None) -> str:
    """Run a gh CLI command and return stdout."""
    cmd = ["gh"] + args
    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=False,
        cwd=cwd,
    )
    if check and result.returncode != 0:
        print(f"gh command failed: {' '.join(cmd)}", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        raise SystemExit(1)
    return result.stdout.strip() if capture else ""


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
    output = run(args)
    if not output:
        return []
    return json.loads(output)


def list_org_repos(org: str, limit: int = 1000) -> list[str]:
    """List all repos in an org. Returns list of full repo names (org/repo)."""
    output = run(
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
    output = run(
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
    output = run(["repo", "view", repo, "--json", "defaultBranchRef"])
    data = json.loads(output)
    return data.get("defaultBranchRef", {}).get("name", "main")


def create_issue(repo: str, title: str, body: str) -> str:
    """Create a GitHub issue and return its URL."""
    return run(["issue", "create", "--repo", repo, "--title", title, "--body", body])


def get_issue(issue_url: str) -> dict:
    """Get issue data (body, title, number, url) from a GitHub issue URL."""
    output = run(["issue", "view", issue_url, "--json", "body,title,number,url"])
    return json.loads(output)


def update_issue(issue_url: str, body: str) -> None:
    """Update the body of a GitHub issue."""
    run(["issue", "edit", issue_url, "--body", body])


def file_exists(repo: str, path: str) -> bool:
    """Check if a file exists in a repo via the GitHub API."""
    result = run(["api", f"repos/{repo}/contents/{path}"], check=False)
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
    output = run(args, check=False)
    if not output:
        return []
    return json.loads(output)
