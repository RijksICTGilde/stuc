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
