"""Clone, replace, commit, push, create PRs."""

import re
import subprocess
import tempfile
from pathlib import Path

from rich.console import Console
from rich.table import Table

from stuc import gh
from stuc.campaign import Campaign
from stuc.discover import discover_repos, preview_changes
from stuc.issue import format_issue_body, format_pr_body

console = Console()


def apply_campaign(campaign: Campaign, dry_run: bool = False, auto_merge: bool = False) -> None:
    """Apply the campaign: clone repos, make changes, push, create PRs."""
    console.print(f"\n[bold cyan]Applying campaign:[/bold cyan] {campaign.name}")

    hits = discover_repos(campaign)
    changes = preview_changes(campaign, hits)

    if not changes:
        console.print("[yellow]No changes to apply.[/yellow]")
        return

    console.print(f"Found changes in [bold]{len(changes)}[/bold] repos.\n")

    if dry_run:
        console.print("[yellow]Dry run — no changes will be made.[/yellow]")
        _show_summary_table(changes, {})
        return

    # Create tracking issue if issue_repo is set but no issue exists yet
    if campaign.issue_repo and not campaign.issue_url:
        try:
            body = format_issue_body(campaign)
            campaign.issue_url = gh.create_issue(campaign.issue_repo, f"stuc: {campaign.pr_title}", body)
            campaign.save()
            console.print(f"  [green]Tracking issue:[/green] {campaign.issue_url}")
        except SystemExit:
            console.print("[yellow]Warning: could not create tracking issue, continuing without it.[/yellow]")

    results: dict[str, str] = {}  # repo -> pr_url or status

    for repo, files in sorted(changes.items()):
        try:
            pr_url = _apply_to_repo(campaign, repo, files, auto_merge)
            results[repo] = pr_url
            campaign.prs[repo] = pr_url
            console.print(f"  [green]✓[/green] {repo} → {pr_url}")
        except Exception as e:
            results[repo] = f"ERROR: {e}"
            console.print(f"  [red]✗[/red] {repo} → {e}")

    # Save updated campaign with PR URLs
    campaign.save()

    # Update tracking issue with PR links
    if campaign.issue_url:
        try:
            updated_body = format_issue_body(campaign)
            gh.update_issue(campaign.issue_url, body=updated_body)
        except SystemExit:
            console.print("[yellow]Warning: could not update tracking issue.[/yellow]")

    console.print()
    _show_summary_table(changes, results)


def _apply_to_repo(campaign: Campaign, repo: str, files: list[dict], auto_merge: bool) -> str:
    """Apply changes to a single repo. Returns PR URL."""
    # Check if PR already exists
    existing_prs = gh.pr_list(repo, head=campaign.branch, state="open")
    if existing_prs:
        pr_url = existing_prs[0]["url"]
        console.print(f"  [dim]PR already exists: {pr_url}[/dim]")
        if auto_merge:
            gh.enable_auto_merge(pr_url)
        return pr_url

    # Get default branch
    default_branch = gh.get_default_branch(repo)

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / repo.split("/")[-1]

        # Clone
        gh.clone_repo(repo, repo_dir)

        # Create branch
        _git(repo_dir, "checkout", "-b", campaign.branch)

        # Apply changes
        changed = False
        if campaign.mode == "llm":
            from stuc.llm import transform_file, validate_output

            context = ""
            if campaign.context_file:
                ctx_path = Path(campaign.context_file)
                if ctx_path.exists():
                    context = ctx_path.read_text()

            for f in files:
                file_path = repo_dir / f["path"]
                if not file_path.exists():
                    continue
                content = file_path.read_text()
                new_content = transform_file(content, campaign.prompt, context=context, file_path=f["path"])
                if new_content.strip() != content.strip():
                    file_path.write_text(new_content)
                    changed = True
                    if campaign.validation:
                        passed, err = validate_output(campaign.validation, f["path"], repo_dir)
                        if not passed:
                            raise RuntimeError(f"Validation failed for {f['path']}: {err}")
        else:
            pattern = re.compile(campaign.find)
            for f in files:
                file_path = repo_dir / f["path"]
                if not file_path.exists():
                    continue
                content = file_path.read_text()
                new_content = pattern.sub(campaign.replace, content)
                if new_content != content:
                    file_path.write_text(new_content)
                    changed = True

        if not changed:
            return "SKIPPED: no changes"

        # Commit
        _git(repo_dir, "add", "-A")
        _git(repo_dir, "commit", "-m", campaign.commit_msg)

        # Push
        _git(repo_dir, "push", "-u", "origin", campaign.branch)

        # Create PR
        body = format_pr_body(campaign.pr_body, issue_url=campaign.issue_url)
        pr_url = gh.create_pr(
            title=campaign.pr_title,
            body=body,
            branch=campaign.branch,
            base=default_branch,
            cwd=repo_dir,
        )

        if auto_merge:
            gh.enable_auto_merge(pr_url)

        return pr_url


def _git(cwd: Path, *args: str) -> str:
    """Run a git command."""
    result = subprocess.run(
        ["git"] + list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _show_summary_table(changes: dict, results: dict) -> None:
    """Show a summary table of results."""
    table = Table(title="Apply Results")
    table.add_column("Repo", style="cyan")
    table.add_column("Files", style="green")
    table.add_column("Result", style="yellow")
    for repo in sorted(changes.keys()):
        status = results.get(repo, "(dry run)")
        table.add_row(repo, str(len(changes[repo])), status)
    console.print(table)
