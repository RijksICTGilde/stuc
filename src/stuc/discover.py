"""Repo discovery via gh search code."""

import base64
import fnmatch
import re

from rich.console import Console
from rich.table import Table

from stuc import gh
from stuc.campaign import Campaign

console = Console()


def _extract_search_term(pattern: str) -> str:
    """Extract a literal search term from a regex pattern.

    GitHub code search is literal text, so we strip regex syntax and return
    the most distinctive literal fragment. The approach: strip all regex
    syntax, then pick the longest path-like fragment that remains.
    """
    # Remove character classes (e.g. [a-z], [^@]+) and their quantifiers
    term = re.sub(r"\[[^\]]*\][+*?]?(?:\{[^}]*\})?", "", pattern)
    # Remove group syntax but keep literal content inside groups
    term = re.sub(r"[()]", "", term)
    # Remove regex escape sequences (\s, \d, \b, etc.)
    term = re.sub(r"\\[a-zA-Z]", "", term)
    # Replace metacharacters with spaces (so they act as fragment boundaries)
    term = re.sub(r"[{}^$.*+?\\|@#]+", " ", term)
    # Find the longest path-like fragment (letters, digits, /, -, _, .)
    fragments = re.findall(r"[a-zA-Z0-9/_.-]{3,}", term)
    if not fragments:
        return term.strip()
    term = max(fragments, key=len)
    # Remove trailing version-like fragments (/v2, /v, etc.)
    term = re.sub(r"/v\d*$", "", term)
    return term.strip("/").strip()


def discover_repos(campaign: Campaign) -> list[dict]:
    """Find all repos with files matching the campaign's glob and regex.

    Returns list of {repo, path} dicts.
    """
    results = []

    for org in campaign.orgs:
        console.print(f"[bold]Searching org: {org}[/bold]")

        # GitHub code search is literal text, not regex.
        # Extract a useful search term from the pattern.
        query = _extract_search_term(campaign.find)
        console.print(f"  [dim]Search query: {query}[/dim]")
        try:
            hits = gh.search_code(query, owner=org)
        except SystemExit:
            console.print(f"[yellow]Warning: search failed for {org}[/yellow]")
            hits = []

        for hit in hits:
            # Handle nested repo structure from gh CLI
            repo_field = hit["repository"]
            if isinstance(repo_field, dict):
                repo_name = repo_field.get("nameWithOwner", repo_field.get("fullName", ""))
            else:
                repo_name = repo_field
            file_path = hit["path"]

            # Check if file matches the glob
            if not fnmatch.fnmatch(file_path, campaign.file_glob):
                continue

            # Skip excluded repos
            if repo_name in campaign.exclude_repos:
                continue

            # If campaign has explicit repos list, filter to those
            if campaign.repos and repo_name not in campaign.repos:
                continue

            results.append({
                "repo": repo_name,
                "path": file_path,
            })

    # Deduplicate by (repo, path)
    seen = set()
    unique = []
    for r in results:
        key = (r["repo"], r["path"])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique


def preview_changes(campaign: Campaign, hits: list[dict]) -> dict[str, list[dict]]:
    """Group hits by repo and generate diffs for preview.

    Returns {repo: [{path, before, after}]}.
    """
    pattern = re.compile(campaign.find)
    by_repo: dict[str, list[dict]] = {}

    for hit in hits:
        repo = hit["repo"]
        path = hit["path"]

        # Fetch file content via gh api
        try:
            content = gh.run([
                "api",
                f"repos/{repo}/contents/{path}",
                "--jq", ".content",
            ])
            decoded = base64.b64decode(content).decode("utf-8")
        except Exception:
            console.print(f"[yellow]Could not fetch {repo}/{path}[/yellow]")
            continue

        new_content = pattern.sub(campaign.replace, decoded)
        if new_content == decoded:
            continue  # No actual changes

        if repo not in by_repo:
            by_repo[repo] = []
        by_repo[repo].append({
            "path": path,
            "before": decoded,
            "after": new_content,
        })

    return by_repo


def show_plan(campaign: Campaign) -> dict[str, list[dict]]:
    """Run discovery and show the plan."""
    console.print(f"\n[bold cyan]Campaign:[/bold cyan] {campaign.name}")
    console.print(f"[bold cyan]Pattern:[/bold cyan] {campaign.find} → {campaign.replace}")
    console.print(f"[bold cyan]Files:[/bold cyan] {campaign.file_glob}")
    console.print()

    hits = discover_repos(campaign)
    if not hits:
        console.print("[yellow]No matching files found.[/yellow]")
        return {}

    console.print(f"Found [bold]{len(hits)}[/bold] matching files across repos.\n")

    changes = preview_changes(campaign, hits)
    if not changes:
        console.print("[yellow]No actual changes needed - all files already match the replacement.[/yellow]")
        return {}

    # Show summary table
    table = Table(title="Planned Changes")
    table.add_column("Repo", style="cyan")
    table.add_column("Files", style="green")
    for repo, files in sorted(changes.items()):
        table.add_row(repo, str(len(files)))
    console.print(table)

    # Show diffs
    for repo, files in sorted(changes.items()):
        console.print(f"\n[bold]{repo}[/bold]")
        for f in files:
            console.print(f"  [dim]{f['path']}[/dim]")
            _show_inline_diff(f["before"], f["after"])

    total_files = sum(len(f) for f in changes.values())
    console.print(f"\n[bold green]Total: {len(changes)} repos, {total_files} files[/bold green]")
    return changes


def _show_inline_diff(before: str, after: str) -> None:
    """Show a compact inline diff of changed lines."""
    before_lines = before.splitlines()
    after_lines = after.splitlines()

    for b, a in zip(before_lines, after_lines):
        if b != a:
            console.print(f"    [red]- {b.strip()}[/red]")
            console.print(f"    [green]+ {a.strip()}[/green]")
