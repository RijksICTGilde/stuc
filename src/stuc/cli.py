"""CLI entrypoint with subcommands: init, list, plan, apply, status, delete, config."""

import re
import sys
from pathlib import Path
from typing import Annotated

import typer

from stuc.campaign import Campaign

EXAMPLES = """\
workflow:
  1. stuc init <name> ...    Create a campaign definition
  2. stuc plan <name>        Preview which repos/files would change (dry run)
  3. stuc apply <name>       Clone repos, apply regex, push branches, open PRs
  4. stuc status <name>      Check PR state and CI status across all repos

examples:
  # Regex mode: Migrate a GitHub Actions reference from v1 to v2
  stuc init bump-actions \\
    --org MyOrg \\
    --file-glob ".github/workflows/*.yml" \\
    --find "MyOrg/my-action@v1" \\
    --replace "MyOrg/my-action@v2" \\
    --branch "stuc/bump-actions" \\
    --commit-msg "chore: bump my-action to v2" \\
    --pr-title "Bump my-action to v2"

  # LLM mode: Use claude to transform files
  stuc init add-license \\
    --mode llm \\
    --org MyOrg \\
    --file-glob "*.md" \\
    --search-term "README" \\
    --prompt "Add a license section at the end of the file" \\
    --branch "stuc/add-license" \\
    --commit-msg "docs: add license section" \\
    --pr-title "Add license section to README"

  # Create mode: Add a new file to repos that don't have it
  stuc init add-dependabot \\
    --mode create \\
    --org MyOrg \\
    --file-glob ".github/dependabot.yml" \\
    --prompt "Create a Dependabot config ..." \\
    --branch "stuc/add-dependabot" \\
    --commit-msg "ci: add Dependabot config" \\
    --pr-title "Add Dependabot configuration"

prerequisites:
  - The 'gh' CLI must be installed and authenticated (gh auth status)
  - You need push access to target repos (to create branches and PRs)
  - For LLM/create mode: the 'claude' CLI must be installed (claude.ai/code)
"""


def _print_examples() -> None:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    console = Console()
    text = Text.from_ansi(EXAMPLES)
    console.print(Panel(text, title="Examples & Workflow", border_style="dim", expand=False))


_CONVENTIONAL_PREFIXES = re.compile(r"^(fix|feat|chore|docs|style|refactor|perf|test|build|ci|revert)(\(.+\))?!?:")


def _validate_campaign(
    mode: str,
    file_glob: str,
    find: str,
    replace: str,
    prompt: str,
    search_term: str,
    context_file: str,
    commit_msg: str = "",
    pr_title: str = "",
) -> None:
    """Validate campaign parameters. Raises SystemExit on error."""
    if commit_msg and not _CONVENTIONAL_PREFIXES.match(commit_msg):
        print(
            f"Error: --commit-msg must start with a conventional commit prefix "
            f"(e.g. fix:, feat:, chore:).\n  Got: {commit_msg!r}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if pr_title and not _CONVENTIONAL_PREFIXES.match(pr_title):
        print(
            f"Error: --pr-title must start with a conventional commit prefix "
            f"(e.g. fix:, feat:, chore:).\n  Got: {pr_title!r}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if not file_glob:
        print("Error: --file-glob is required.", file=sys.stderr)
        raise SystemExit(1)

    if mode == "regex":
        if not find or not replace:
            print("Error: --find and --replace are required for regex mode.", file=sys.stderr)
            raise SystemExit(1)
        try:
            re.compile(find)
        except re.error as e:
            print(f"Error: Invalid regex in --find: {e}", file=sys.stderr)
            raise SystemExit(1) from e
    elif mode == "llm":
        if not prompt:
            print("Error: --prompt is required for llm mode.", file=sys.stderr)
            raise SystemExit(1)
        if not search_term:
            print("Error: --search-term is required for llm mode.", file=sys.stderr)
            raise SystemExit(1)
        if context_file and not Path(context_file).exists():
            print(f"Error: Context file not found: {context_file}", file=sys.stderr)
            raise SystemExit(1)
    elif mode == "create":
        if not prompt:
            print("Error: --prompt is required for create mode.", file=sys.stderr)
            raise SystemExit(1)
        if any(c in file_glob for c in "*?["):
            print(
                "Error: --file-glob must be an exact file path for create mode (no wildcards).",
                file=sys.stderr,
            )
            raise SystemExit(1)
        if context_file and not Path(context_file).exists():
            print(f"Error: Context file not found: {context_file}", file=sys.stderr)
            raise SystemExit(1)


app = typer.Typer(
    help="Fleet-wide regex find-and-replace across GitHub org repos.\n\nRun 'stuc examples' for usage examples.",
    rich_markup_mode=None,
    no_args_is_help=True,
)


@app.command()
def examples() -> None:
    """Show workflow, examples, and prerequisites."""
    _print_examples()


@app.command()
def init(
    name: Annotated[str | None, typer.Argument(help="Campaign name (used as filename and identifier)")] = None,
    mode: Annotated[str | None, typer.Option(help="Campaign mode: regex, llm, or create")] = None,
    org: Annotated[list[str] | None, typer.Option(help="GitHub org to target (repeatable)")] = None,
    file_glob: Annotated[str | None, typer.Option(help="Glob pattern for files to modify")] = None,
    find: Annotated[str, typer.Option(help="Python regex pattern to find")] = "",
    replace: Annotated[str, typer.Option(help="Replacement string")] = "",
    prompt: Annotated[str, typer.Option(help="LLM instruction for transforming/generating files")] = "",
    search_term: Annotated[str, typer.Option(help="Literal search term for gh search code")] = "",
    context_file: Annotated[str, typer.Option(help="Path to context file for LLM")] = "",
    validation: Annotated[str, typer.Option(help="Shell command to validate LLM output")] = "",
    branch: Annotated[str | None, typer.Option(help="Git branch name to create")] = None,
    commit_msg: Annotated[str | None, typer.Option(help="Git commit message")] = None,
    pr_title: Annotated[str | None, typer.Option(help="PR title")] = None,
    pr_body: Annotated[str | None, typer.Option(help="PR body text")] = None,
    exclude_repo: Annotated[list[str] | None, typer.Option(help="Repo to skip (repeatable)")] = None,
    issue_repo: Annotated[str, typer.Option(help="Repo for tracking issue")] = "",
) -> None:
    """Create a new campaign definition."""
    from rich.console import Console

    from stuc import config as stuc_config

    console = Console()

    # Check if interactive wizard is needed
    needs_wizard = (
        name is None
        or mode is None
        or org is None
        or file_glob is None
        or branch is None
        or commit_msg is None
        or pr_title is None
    )
    if needs_wizard:
        if not sys.stdin.isatty():
            missing = []
            if name is None:
                missing.append("NAME")
            if mode is None:
                missing.append("--mode")
            if org is None:
                missing.append("--org")
            if file_glob is None:
                missing.append("--file-glob")
            if branch is None:
                missing.append("--branch")
            if commit_msg is None:
                missing.append("--commit-msg")
            if pr_title is None:
                missing.append("--pr-title")
            print(f"Error: missing required options: {', '.join(missing)}", file=sys.stderr)
            print("\nProvide all required options or run in a terminal for interactive mode.", file=sys.stderr)
            raise SystemExit(1)

        from stuc.interactive import InitParams, init_wizard

        params = init_wizard(
            InitParams(
                name=name or "",
                mode=mode or "",
                org=org or [],
                file_glob=file_glob or "",
                find=find,
                replace=replace,
                prompt=prompt,
                search_term=search_term,
                context_file=context_file,
                validation=validation,
                branch=branch or "",
                commit_msg=commit_msg or "",
                pr_title=pr_title or "",
                pr_body=pr_body or "",
                exclude_repo=exclude_repo or [],
                issue_repo=issue_repo,
            )
        )
        name = params.name
        mode = params.mode
        org = params.org
        file_glob = params.file_glob
        find = params.find
        replace = params.replace
        prompt = params.prompt
        search_term = params.search_term
        context_file = params.context_file
        validation = params.validation
        branch = params.branch
        commit_msg = params.commit_msg
        pr_title = params.pr_title
        pr_body = params.pr_body
        exclude_repo = params.exclude_repo
        issue_repo = params.issue_repo

    mode = mode or "regex"
    orgs = org or []
    exclude_repos = exclude_repo or []

    # Resolve defaults from global config
    if not issue_repo:
        issue_repo = stuc_config.get("issue_repo")
    if not pr_body:
        pr_body = stuc_config.get("pr_body") or "Automated migration by stuc."

    _validate_campaign(mode, file_glob, find, replace, prompt, search_term, context_file, commit_msg, pr_title)

    campaign = Campaign(
        name=name,
        mode=mode,
        orgs=orgs,
        file_glob=file_glob,
        find=find,
        replace=replace,
        branch=branch,
        commit_msg=commit_msg,
        pr_title=pr_title,
        pr_body=pr_body,
        exclude_repos=exclude_repos,
        prompt=prompt,
        search_term=search_term,
        context_file=context_file,
        validation=validation,
        issue_repo=issue_repo,
    )
    path = campaign.save()
    console.print(f"[green]Campaign created:[/green] {path}")
    console.print(f"\nNext step: run [bold]stuc plan {name}[/bold] to preview changes.")


@app.command("list")
def list_campaigns() -> None:
    """List all existing campaigns."""
    from rich.console import Console

    console = Console()

    campaigns = Campaign.list_all()
    if not campaigns:
        console.print("No campaigns found. Create one with [bold]stuc init[/bold].")
        return

    console.print(f"[bold]Campaigns[/bold] ({len(campaigns)}):\n")
    for name in sorted(campaigns):
        try:
            c = Campaign.load(name)
            orgs = ", ".join(c.orgs)
            pr_count = len(c.prs)
            if c.mode == "create":
                prompt_display = c.prompt[:50] + ("..." if len(c.prompt) > 50 else "")
                console.print(
                    f"  [cyan]{name}[/cyan]  mode=[dim]create[/dim]  orgs=[dim]{orgs}[/dim]"
                    f"  file=[dim]{c.file_glob}[/dim]  prompt=[dim]{prompt_display}[/dim]  PRs=[dim]{pr_count}[/dim]"
                )
            elif c.mode == "llm":
                prompt_display = c.prompt[:50] + ("..." if len(c.prompt) > 50 else "")
                console.print(
                    f"  [cyan]{name}[/cyan]  mode=[dim]llm[/dim]  orgs=[dim]{orgs}[/dim]"
                    f"  prompt=[dim]{prompt_display}[/dim]  PRs=[dim]{pr_count}[/dim]"
                )
            else:
                console.print(
                    f"  [cyan]{name}[/cyan]  orgs=[dim]{orgs}[/dim]"
                    f"  find=[dim]{c.find}[/dim]  PRs=[dim]{pr_count}[/dim]"
                )
        except Exception:
            console.print(f"  [cyan]{name}[/cyan]  [dim](could not load)[/dim]")


@app.command()
def plan(
    name: Annotated[str, typer.Argument(help="Campaign name")],
) -> None:
    """Preview what a campaign would change (dry run)."""
    from stuc.discover import show_plan

    campaign = Campaign.load(name)
    changes = show_plan(campaign)

    # Interactive review if TTY
    if changes and sys.stdin.isatty():
        from stuc.interactive import review_plan

        review_plan(campaign, changes)


@app.command()
def apply(
    name: Annotated[str, typer.Argument(help="Campaign name")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would happen")] = False,
    auto_merge: Annotated[bool, typer.Option("--auto-merge", help="Enable auto-merge")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Execute the campaign: clone repos, apply changes, open PRs."""
    from stuc.apply import apply_campaign

    campaign = Campaign.load(name)

    if not yes and not dry_run and sys.stdin.isatty():
        from stuc.discover import discover_repos, preview_changes
        from stuc.interactive import confirm_apply

        hits = discover_repos(campaign)
        changes = preview_changes(campaign, hits)
        if not changes:
            print("No changes to apply.")
            return
        if not confirm_apply(campaign, changes):
            print("Aborted.")
            raise SystemExit(0)
        apply_campaign(campaign, dry_run=dry_run, auto_merge=auto_merge, changes=changes)
        return

    apply_campaign(campaign, dry_run=dry_run, auto_merge=auto_merge)


@app.command()
def delete(
    name: Annotated[str, typer.Argument(help="Campaign name to delete")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Delete a campaign definition."""
    from rich.console import Console

    console = Console()

    campaign = Campaign.load(name)
    if not yes:
        pr_count = len(campaign.prs)
        if pr_count:
            console.print(f"[yellow]Warning: this campaign has {pr_count} PR(s) that will NOT be closed.[/yellow]")
        answer = input(f"Delete campaign '{name}'? [y/N] ")
        if answer.lower() not in ("y", "yes"):
            console.print("Aborted.")
            return

    path = campaign.delete()
    console.print(f"[green]Deleted:[/green] {path}")


@app.command()
def status(
    name: Annotated[str | None, typer.Argument(help="Campaign name or GitHub issue URL")] = None,
    refresh: Annotated[bool, typer.Option("--refresh", help="Re-fetch PR status")] = False,
    auto_merge: Annotated[bool, typer.Option("--auto-merge", help="Enable auto-merge on passing PRs")] = False,
    all_campaigns: Annotated[
        bool, typer.Option("--all", help="Show status for all open campaigns in issue_repo")
    ] = False,
    mine: Annotated[bool, typer.Option("--mine", help="Show status for my open campaigns in issue_repo")] = False,
) -> None:
    """Check PR state and CI status for all repos in a campaign."""
    from stuc import config as stuc_config
    from stuc import gh
    from stuc.issue import STUC_DATA_MARKER, extract_campaign_from_issue, is_issue_url
    from stuc.status import show_status

    if all_campaigns or mine:
        issue_repo = stuc_config.get("issue_repo")
        if not issue_repo:
            print("Error: no issue_repo configured. Run: stuc config issue_repo <owner/repo>", file=sys.stderr)
            raise SystemExit(1)

        author = gh.current_user() if mine else None
        issues = gh.list_issues(issue_repo, state="open", author=author)
        stuc_issues = [i for i in issues if STUC_DATA_MARKER in (i.get("body") or "")]

        if not stuc_issues:
            label = "your" if mine else "any"
            print(f"No open stuc campaigns found ({label}) in {issue_repo}.")
            return

        for issue in stuc_issues:
            campaign = extract_campaign_from_issue(issue["body"])
            campaign.issue_url = issue["url"]
            show_status(campaign, refresh=refresh, auto_merge=auto_merge)
        return

    if name is None:
        print("Error: provide a campaign name, issue URL, or use --all / --mine.", file=sys.stderr)
        raise SystemExit(1)

    if is_issue_url(name):
        issue_data = gh.get_issue(name)
        campaign = extract_campaign_from_issue(issue_data["body"])
        campaign.issue_url = name
    else:
        campaign = Campaign.load(name)
    show_status(campaign, refresh=refresh, auto_merge=auto_merge)


@app.command()
def config(
    key: Annotated[str | None, typer.Argument(help="Config key to get or set")] = None,
    value: Annotated[str | None, typer.Argument(help="Value to set")] = None,
) -> None:
    """Get or set global stuc configuration."""
    from rich.console import Console

    from stuc import config as stuc_config

    console = Console()

    if key is None:
        # Show all config
        data = stuc_config.load()
        if not any(data.values()):
            console.print("No configuration set. Use [bold]stuc config <key> <value>[/bold] to set defaults.")
            return
        for k, v in sorted(data.items()):
            if v:
                console.print(f"  [cyan]{k}[/cyan] = {v}")
    elif value is None:
        # Get single key
        val = stuc_config.get(key)
        if val:
            console.print(val)
        else:
            console.print("[dim](not set)[/dim]")
    else:
        # Set key
        if key not in stuc_config.DEFAULTS:
            console.print(f"[red]Unknown config key:[/red] {key}")
            console.print(f"Available keys: {', '.join(sorted(stuc_config.DEFAULTS))}")
            raise SystemExit(1)
        path = stuc_config.set_value(key, value)
        console.print(f"[green]Set[/green] {key} = {value}")
        console.print(f"[dim]Saved to {path}[/dim]")


def main() -> None:
    try:
        app()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("\nHint: Use 'stuc list' to see existing campaigns, or 'stuc init' to create one.", file=sys.stderr)
        sys.exit(1)
    except re.error as e:
        print(f"Error: Invalid regex pattern: {e}", file=sys.stderr)
        print(
            "\nHint: The --find argument must be a valid Python regex. Use raw strings and escape special characters.",
            file=sys.stderr,
        )
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
