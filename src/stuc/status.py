"""PR and CI status tracking."""

from rich.console import Console
from rich.table import Table

from stuc import gh
from stuc.campaign import Campaign

console = Console()

# Status emoji/labels
STATE_LABELS = {
    "OPEN": "[yellow]open[/yellow]",
    "MERGED": "[green]merged[/green]",
    "CLOSED": "[red]closed[/red]",
}

CHECK_LABELS = {
    "SUCCESS": "[green]pass[/green]",
    "FAILURE": "[red]fail[/red]",
    "PENDING": "[yellow]pending[/yellow]",
    "EXPECTED": "[yellow]expected[/yellow]",
    "NEUTRAL": "[dim]neutral[/dim]",
    "ERROR": "[red]error[/red]",
    "UNKNOWN": "[dim]unknown[/dim]",
}


def show_status(campaign: Campaign, refresh: bool = False, auto_merge: bool = False) -> None:
    """Show status of all PRs in a campaign."""
    console.print(f"\n[bold cyan]Campaign:[/bold cyan] {campaign.name}")

    if not campaign.prs:
        console.print("[yellow]No PRs tracked yet. Run 'stuc apply' first.[/yellow]")
        return

    table = Table(title="PR Status")
    table.add_column("Repo", style="cyan")
    table.add_column("PR", style="blue")
    table.add_column("State")
    table.add_column("CI")
    table.add_column("Merge Status", style="dim")

    counts = {"open": 0, "merged": 0, "closed": 0}
    ci_counts = {"pass": 0, "fail": 0, "pending": 0, "other": 0}

    for repo, pr_url in sorted(campaign.prs.items()):
        if pr_url.startswith("ERROR") or pr_url.startswith("SKIPPED"):
            table.add_row(repo, pr_url, "", "", "")
            continue

        if refresh:
            info = gh.pr_status(repo, campaign.branch)
        else:
            # Try to get status from the stored PR URL
            info = gh.pr_status(repo, campaign.branch)

        if info is None:
            table.add_row(repo, pr_url, "[dim]unknown[/dim]", "", "")
            continue

        state = info.get("state", "UNKNOWN")
        state_label = STATE_LABELS.get(state, f"[dim]{state}[/dim]")
        counts[state.lower()] = counts.get(state.lower(), 0) + 1

        # Aggregate CI checks
        checks = info.get("statusCheckRollup", []) or []
        ci_label = _aggregate_checks(checks)

        merge_status = info.get("mergeStateStatus", "")

        # Short PR ref
        pr_short = pr_url.split("/")[-1] if "/" in pr_url else pr_url

        table.add_row(repo, f"#{pr_short}", state_label, ci_label, merge_status)

        # Auto-merge if requested and PR is open + CI green
        if auto_merge and state == "OPEN":
            all_pass = all(
                _check_conclusion(c) == "SUCCESS"
                for c in checks
                if _check_conclusion(c) != "NEUTRAL"
            ) if checks else False
            if all_pass:
                console.print(f"  [dim]Enabling auto-merge on {pr_url}[/dim]")
                gh.enable_auto_merge(pr_url)

    console.print(table)

    # Summary
    summary_parts = []
    if counts.get("merged"):
        summary_parts.append(f"[green]{counts['merged']} merged[/green]")
    if counts.get("open"):
        summary_parts.append(f"[yellow]{counts['open']} open[/yellow]")
    if counts.get("closed"):
        summary_parts.append(f"[red]{counts['closed']} closed[/red]")
    console.print("\n" + ", ".join(summary_parts))


def _check_conclusion(check: dict) -> str:
    """Extract conclusion from a check run."""
    return check.get("conclusion", check.get("state", "UNKNOWN")).upper()


def _aggregate_checks(checks: list[dict]) -> str:
    """Aggregate multiple checks into a single label."""
    if not checks:
        return "[dim]no checks[/dim]"

    conclusions = [_check_conclusion(c) for c in checks]

    if all(c in ("SUCCESS", "NEUTRAL") for c in conclusions):
        return CHECK_LABELS["SUCCESS"]
    if any(c == "FAILURE" for c in conclusions):
        return CHECK_LABELS["FAILURE"]
    if any(c in ("PENDING", "EXPECTED") for c in conclusions):
        return CHECK_LABELS["PENDING"]
    return CHECK_LABELS["UNKNOWN"]
