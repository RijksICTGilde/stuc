"""PR and CI status tracking."""

from rich.console import Console
from rich.table import Table

from stuc import gh
from stuc.campaign import Campaign
from stuc.issue import pr_short, update_status_table

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

MERGE_LABELS = {
    "CLEAN": "[green]ready[/green]",
    "BLOCKED": "[red]blocked[/red]",
    "BEHIND": "[yellow]behind[/yellow]",
    "UNSTABLE": "[yellow]unstable[/yellow]",
    "DIRTY": "[red]conflicts[/red]",
    "HAS_HOOKS": "[dim]has hooks[/dim]",
    "UNKNOWN": "[dim]unknown[/dim]",
}

# Plain-text versions for issue body (no rich markup)
PLAIN_STATE = {"OPEN": "open", "MERGED": "merged", "CLOSED": "closed"}
PLAIN_MERGE = {
    "CLEAN": "ready",
    "BLOCKED": "blocked",
    "BEHIND": "behind",
    "UNSTABLE": "unstable",
    "DIRTY": "conflicts",
    "HAS_HOOKS": "has hooks",
    "UNKNOWN": "unknown",
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
    table.add_column("Merge")
    table.add_column("Failing Checks", style="dim")

    counts = {"open": 0, "merged": 0, "closed": 0}
    status_rows: list[dict] = []  # plain-text rows for issue update

    for repo, pr_url in sorted(campaign.prs.items()):
        if pr_url.startswith("ERROR") or pr_url.startswith("SKIPPED"):
            table.add_row(repo, pr_url, "", "", "", "")
            status_rows.append({"repo": repo, "pr_url": pr_url, "state": "-", "ci": "-", "merge": "-"})
            continue

        info = gh.pr_status(repo, campaign.branch)

        if info is None:
            table.add_row(repo, f"[link={pr_url}]{pr_short(pr_url)}[/link]", "[dim]unknown[/dim]", "", "", "")
            status_rows.append({"repo": repo, "pr_url": pr_url, "state": "unknown", "ci": "-", "merge": "-"})
            continue

        state = info.get("state", "UNKNOWN")
        state_label = STATE_LABELS.get(state, f"[dim]{state}[/dim]")
        counts[state.lower()] = counts.get(state.lower(), 0) + 1

        # Aggregate CI checks
        checks = info.get("statusCheckRollup", []) or []
        ci_label = _aggregate_checks(checks)

        # Merge status
        merge_status = info.get("mergeStateStatus", "UNKNOWN")
        merge_label = MERGE_LABELS.get(merge_status, f"[dim]{merge_status}[/dim]")

        # Failing check names
        failing = _failing_check_names(checks)

        table.add_row(
            repo,
            f"[link={pr_url}]{pr_short(pr_url)}[/link]",
            state_label,
            ci_label,
            merge_label,
            failing,
        )

        # Collect plain-text row for issue update
        status_rows.append(
            {
                "repo": repo,
                "pr_url": pr_url,
                "state": PLAIN_STATE.get(state, state.lower()),
                "ci": _aggregate_checks_plain(checks),
                "merge": PLAIN_MERGE.get(merge_status, merge_status.lower()),
            }
        )

        # Auto-merge if requested and PR is open + CI green
        if auto_merge and state == "OPEN":
            all_pass = (
                all(_check_conclusion(c) == "SUCCESS" for c in checks if _check_conclusion(c) != "NEUTRAL")
                if checks
                else False
            )
            if all_pass:
                console.print(f"  [dim]Enabling auto-merge on {pr_url}[/dim]")
                gh.enable_auto_merge(pr_url)

    console.print(table)

    # Update tracking issue if set
    if campaign.issue_url:
        try:
            issue_data = gh.get_issue(campaign.issue_url)
            updated = update_status_table(issue_data["body"], status_rows)
            gh.update_issue(campaign.issue_url, body=updated)
        except SystemExit:
            console.print("[yellow]Warning: could not update tracking issue.[/yellow]")

    # Close tracking issue if all PRs are merged (or closed)
    trackable = [r for r in status_rows if r["state"] not in ("-", "unknown")]
    all_done = trackable and all(r["state"] in ("merged", "closed") for r in trackable)
    if all_done and campaign.issue_url:
        try:
            gh.close_issue(campaign.issue_url)
            console.print(f"[green]All PRs merged — closed tracking issue {campaign.issue_url}[/green]")
        except SystemExit:
            console.print("[yellow]Warning: could not close tracking issue.[/yellow]")

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

    if all(c in ("SUCCESS", "NEUTRAL", "SKIPPED") for c in conclusions):
        return CHECK_LABELS["SUCCESS"]
    if any(c == "FAILURE" for c in conclusions):
        n_fail = sum(1 for c in conclusions if c == "FAILURE")
        n_total = len(conclusions)
        return f"[red]{n_fail}/{n_total} fail[/red]"
    if any(c in ("PENDING", "EXPECTED") for c in conclusions):
        return CHECK_LABELS["PENDING"]
    return CHECK_LABELS["UNKNOWN"]


def _aggregate_checks_plain(checks: list[dict]) -> str:
    """Aggregate checks into a plain-text label (no rich markup)."""
    if not checks:
        return "no checks"
    conclusions = [_check_conclusion(c) for c in checks]
    if all(c in ("SUCCESS", "NEUTRAL", "SKIPPED") for c in conclusions):
        return "pass"
    if any(c == "FAILURE" for c in conclusions):
        n_fail = sum(1 for c in conclusions if c == "FAILURE")
        return f"{n_fail}/{len(conclusions)} fail"
    if any(c in ("PENDING", "EXPECTED") for c in conclusions):
        return "pending"
    return "unknown"


def _failing_check_names(checks: list[dict]) -> str:
    """Return comma-separated names of failing checks."""
    failing = []
    for c in checks:
        if _check_conclusion(c) == "FAILURE":
            name = c.get("name", c.get("context", "?"))
            failing.append(name)
    return ", ".join(failing) if failing else ""
