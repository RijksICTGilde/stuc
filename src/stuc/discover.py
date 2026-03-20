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
    if campaign.mode == "create":
        return _discover_repos_create(campaign)

    results = []

    for org in campaign.orgs:
        console.print(f"[bold]Searching org: {org}[/bold]")

        # GitHub code search is literal text, not regex.
        # For LLM mode, use the explicit search term; for regex, extract from pattern.
        query = campaign.search_term if campaign.mode == "llm" else _extract_search_term(campaign.find)
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

            results.append(
                {
                    "repo": repo_name,
                    "path": file_path,
                }
            )

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
    if campaign.mode == "create":
        return _preview_changes_create(campaign, hits)

    if campaign.mode == "llm":
        return _preview_changes_llm(campaign, hits)

    pattern = re.compile(campaign.find)
    by_repo: dict[str, list[dict]] = {}

    for hit in hits:
        repo = hit["repo"]
        path = hit["path"]

        # Fetch file content via gh api
        try:
            content = gh.run(
                [
                    "api",
                    f"repos/{repo}/contents/{path}",
                    "--jq",
                    ".content",
                ]
            )
            decoded = base64.b64decode(content).decode("utf-8")
        except Exception:
            console.print(f"[yellow]Could not fetch {repo}/{path}[/yellow]")
            continue

        new_content = pattern.sub(campaign.replace, decoded)
        if new_content == decoded:
            continue  # No actual changes

        if repo not in by_repo:
            by_repo[repo] = []
        by_repo[repo].append(
            {
                "path": path,
                "before": decoded,
                "after": new_content,
            }
        )

    return by_repo


def _preview_changes_llm(campaign: Campaign, hits: list[dict]) -> dict[str, list[dict]]:
    """Preview changes using LLM transformation."""
    from stuc.llm import transform_file

    context = ""
    if campaign.context_file:
        from pathlib import Path

        ctx_path = Path(campaign.context_file)
        if ctx_path.exists():
            context = ctx_path.read_text()

    console.print(f"[bold]Transforming {len(hits)} files via LLM...[/bold]")
    by_repo: dict[str, list[dict]] = {}

    for i, hit in enumerate(hits, 1):
        repo = hit["repo"]
        path = hit["path"]
        console.print(f"  [{i}/{len(hits)}] {repo}/{path}")

        try:
            content = gh.run(
                [
                    "api",
                    f"repos/{repo}/contents/{path}",
                    "--jq",
                    ".content",
                ]
            )
            decoded = base64.b64decode(content).decode("utf-8")
        except Exception:
            console.print(f"[yellow]Could not fetch {repo}/{path}[/yellow]")
            continue

        try:
            new_content = transform_file(decoded, campaign.prompt, context=context, file_path=path)
        except Exception as e:
            console.print(f"[red]LLM transform failed for {repo}/{path}: {e}[/red]")
            continue

        if new_content.strip() == decoded.strip():
            continue

        if repo not in by_repo:
            by_repo[repo] = []
        by_repo[repo].append(
            {
                "path": path,
                "before": decoded,
                "after": new_content,
            }
        )

    return by_repo


def show_plan(campaign: Campaign) -> dict[str, list[dict]]:
    """Run discovery and show the plan."""
    console.print(f"\n[bold cyan]Campaign:[/bold cyan] {campaign.name}")
    if campaign.mode == "create":
        console.print("[bold cyan]Mode:[/bold cyan] create")
        console.print(f"[bold cyan]Target file:[/bold cyan] {campaign.file_glob}")
        console.print(f"[bold cyan]Prompt:[/bold cyan] {campaign.prompt}")
    elif campaign.mode == "llm":
        console.print("[bold cyan]Mode:[/bold cyan] llm")
        console.print(f"[bold cyan]Prompt:[/bold cyan] {campaign.prompt}")
        console.print(f"[bold cyan]Search term:[/bold cyan] {campaign.search_term}")
    else:
        console.print(f"[bold cyan]Pattern:[/bold cyan] {campaign.find} → {campaign.replace}")
    console.print(f"[bold cyan]Files:[/bold cyan] {campaign.file_glob}")
    console.print()

    hits = discover_repos(campaign)
    if not hits:
        if campaign.mode == "create":
            console.print("[yellow]No repos missing the target file.[/yellow]")
        else:
            console.print("[yellow]No matching files found.[/yellow]")
        return {}

    if campaign.mode == "create":
        console.print(f"Found [bold]{len(hits)}[/bold] repos missing the target file.\n")
    else:
        console.print(f"Found [bold]{len(hits)}[/bold] matching files across repos.\n")

    changes = preview_changes(campaign, hits)
    if not changes:
        if campaign.mode == "create":
            console.print("[yellow]No file content could be generated.[/yellow]")
        else:
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
    if not before:
        # New file: show all lines as additions, cap at 20 lines
        after_lines = after.splitlines()
        shown = after_lines[:20]
        for line in shown:
            console.print(f"    [green]+ {line}[/green]")
        remaining = len(after_lines) - len(shown)
        if remaining > 0:
            console.print(f"    [dim]... {remaining} more lines[/dim]")
        return

    before_lines = before.splitlines()
    after_lines = after.splitlines()

    for b, a in zip(before_lines, after_lines, strict=False):
        if b != a:
            console.print(f"    [red]- {b.strip()}[/red]")
            console.print(f"    [green]+ {a.strip()}[/green]")


def _discover_repos_create(campaign: Campaign) -> list[dict]:
    """Find repos that are missing the target file."""
    results = []

    for org in campaign.orgs:
        console.print(f"[bold]Listing repos in org: {org}[/bold]")
        try:
            repos = gh.list_org_repos(org)
        except SystemExit:
            console.print(f"[yellow]Warning: could not list repos for {org}[/yellow]")
            continue

        for repo in repos:
            if repo in campaign.exclude_repos:
                continue
            if campaign.repos and repo not in campaign.repos:
                continue

            console.print(f"  [dim]Checking {repo}...[/dim]")
            if not gh.file_exists(repo, campaign.file_glob):
                results.append({"repo": repo, "path": campaign.file_glob})

    return results


def _preview_changes_create(campaign: Campaign, hits: list[dict]) -> dict[str, list[dict]]:
    """Preview file content to be created using LLM generation."""
    from stuc.llm import transform_file

    context = ""
    if campaign.context_file:
        from pathlib import Path

        ctx_path = Path(campaign.context_file)
        if ctx_path.exists():
            context = ctx_path.read_text()

    console.print(f"[bold]Generating content for {len(hits)} repos via LLM...[/bold]")
    by_repo: dict[str, list[dict]] = {}

    for i, hit in enumerate(hits, 1):
        repo = hit["repo"]
        path = hit["path"]
        console.print(f"  [{i}/{len(hits)}] {repo}/{path}")

        try:
            new_content = transform_file("", campaign.prompt, context=context, file_path=path)
        except Exception as e:
            console.print(f"[red]LLM generation failed for {repo}/{path}: {e}[/red]")
            continue

        if not new_content.strip():
            continue

        if repo not in by_repo:
            by_repo[repo] = []
        by_repo[repo].append(
            {
                "path": path,
                "before": "",
                "after": new_content,
            }
        )

    return by_repo
