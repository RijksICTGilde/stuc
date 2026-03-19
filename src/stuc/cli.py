"""CLI entrypoint with subcommands: init, list, plan, apply, status."""

import argparse
import re
import sys

from stuc.campaign import Campaign


EPILOG = """
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

  # Preview what the campaign would change
  stuc plan bump-actions

  # Apply changes (opens PRs)
  stuc apply bump-actions

  # Check PR and CI status
  stuc status bump-actions --refresh

  # Delete a campaign
  stuc delete bump-actions --yes

  # List all campaigns
  stuc list

prerequisites:
  - The 'gh' CLI must be installed and authenticated (gh auth status)
  - You need push access to target repos (to create branches and PRs)
  - For LLM mode: the 'claude' CLI must be installed (claude.ai/code)
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="stuc",
        description="Fleet-wide regex find-and-replace across GitHub org repos. "
        "Creates a 'campaign' that discovers matching files via gh search, "
        "previews diffs, then clones repos, applies changes, and opens PRs.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)  # init, list, plan, apply, delete, status

    # init
    p_init = subparsers.add_parser(
        "init",
        help="Create a new campaign definition (saved to ~/.stuc/campaigns/<name>.yml)",
        description="Create a campaign that defines a regex find-and-replace across repos in one or more GitHub orgs. "
        "The campaign is saved as YAML and can be previewed with 'plan' before applying.",
    )
    p_init.add_argument("name", help="Campaign name (used as filename and identifier, e.g. 'bump-actions-v2')")
    p_init.add_argument("--mode", choices=["regex", "llm"], default="regex",
                        help="Campaign mode: 'regex' for find-and-replace, 'llm' for claude-powered transformation (default: regex)")
    p_init.add_argument("--org", action="append", required=True, dest="orgs",
                        help="GitHub org to target. Can be specified multiple times for multiple orgs (e.g. --org OrgA --org OrgB)")
    p_init.add_argument("--file-glob", required=True,
                        help="Glob pattern for files to modify (e.g. '.github/workflows/*.yml' or '**/*.toml')")
    p_init.add_argument("--find", default="",
                        help="Python regex pattern to find (required for regex mode). Supports capture groups "
                        "(e.g. 'MyOrg/actions/([^@]+)@v1')")
    p_init.add_argument("--replace", default="",
                        help="Replacement string (required for regex mode). Use \\1, \\2 for backreferences "
                        "(e.g. 'MyOrg/actions/\\1@v2')")
    p_init.add_argument("--prompt", default="",
                        help="LLM instruction for transforming files (required for llm mode)")
    p_init.add_argument("--search-term", default="",
                        help="Literal search term for gh search code (required for llm mode)")
    p_init.add_argument("--context-file", default="",
                        help="Path to a file with additional context for the LLM (optional, llm mode only)")
    p_init.add_argument("--validation", default="",
                        help="Shell command to validate LLM output (optional, llm mode only). "
                        "The file path is available as $FILE")
    p_init.add_argument("--branch", required=True,
                        help="Git branch name to create in each repo (e.g. 'stuc/bump-actions-v2')")
    p_init.add_argument("--commit-msg", required=True,
                        help="Git commit message for the change (e.g. 'chore: bump actions to v2')")
    p_init.add_argument("--pr-title", required=True,
                        help="Title for the pull request created in each repo")
    p_init.add_argument("--pr-body", default="Automated migration by stuc.",
                        help="Body text for the pull request (default: 'Automated migration by stuc.')")
    p_init.add_argument("--exclude-repo", action="append", default=[], dest="exclude_repos",
                        help="Repo to skip, as 'org/repo'. Can be specified multiple times")

    # list
    subparsers.add_parser(
        "list",
        help="List all existing campaigns",
        description="List all campaign files in ~/.stuc/campaigns/. Shows campaign names that can be used with plan/apply/status.",
    )

    # plan
    p_plan = subparsers.add_parser(
        "plan",
        help="Preview what a campaign would change (dry run, no modifications)",
        description="Discover matching files across GitHub orgs and show a diff preview. "
        "This is read-only: no repos are cloned, no branches created, no PRs opened.",
    )
    p_plan.add_argument("name", help="Campaign name (must have been created with 'init' first)")

    # apply
    p_apply = subparsers.add_parser(
        "apply",
        help="Execute the campaign: clone repos, apply changes, push branches, open PRs",
        description="For each repo with matching changes: clone it, create a branch, apply the regex replacement, "
        "commit, push, and open a pull request. Repos that already have an open PR on the campaign branch are skipped. "
        "PR URLs are saved to the campaign file for tracking with 'status'.",
    )
    p_apply.add_argument("name", help="Campaign name (must have been created with 'init' first)")
    p_apply.add_argument("--dry-run", action="store_true",
                         help="Show what would happen without making any changes (no clones, no PRs)")
    p_apply.add_argument("--auto-merge", action="store_true",
                         help="Enable auto-merge (squash) on each created PR")

    # delete
    p_delete = subparsers.add_parser(
        "delete",
        help="Delete a campaign definition",
        description="Remove a campaign YAML file from ~/.stuc/campaigns/. "
        "This does not close or clean up any PRs that were already opened.",
    )
    p_delete.add_argument("name", help="Campaign name to delete")
    p_delete.add_argument("--yes", "-y", action="store_true",
                          help="Skip confirmation prompt")

    # status
    p_status = subparsers.add_parser(
        "status",
        help="Check PR state and CI status for all repos in a campaign",
        description="Show a table of all PRs created by a campaign with their current state (open/merged/closed), "
        "CI check results, and merge status.",
    )
    p_status.add_argument("name", help="Campaign name (must have been applied with 'apply' first)")
    p_status.add_argument("--refresh", action="store_true",
                          help="Re-fetch PR status from GitHub (otherwise uses cached data)")
    p_status.add_argument("--auto-merge", action="store_true",
                          help="Enable auto-merge on open PRs that have all CI checks passing")

    args = parser.parse_args()

    try:
        if args.command == "init":
            _cmd_init(args)
        elif args.command == "list":
            _cmd_list()
        elif args.command == "plan":
            _cmd_plan(args)
        elif args.command == "apply":
            _cmd_apply(args)
        elif args.command == "delete":
            _cmd_delete(args)
        elif args.command == "status":
            _cmd_status(args)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("\nHint: Use 'stuc list' to see existing campaigns, or 'stuc init' to create one.", file=sys.stderr)
        sys.exit(1)
    except re.error as e:
        print(f"Error: Invalid regex pattern: {e}", file=sys.stderr)
        print("\nHint: The --find argument must be a valid Python regex. "
              "Use raw strings and escape special characters.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_init(args: argparse.Namespace) -> None:
    from pathlib import Path

    from rich.console import Console
    console = Console()

    if args.mode == "regex":
        if not args.find or not args.replace:
            print("Error: --find and --replace are required for regex mode.", file=sys.stderr)
            sys.exit(1)
        try:
            re.compile(args.find)
        except re.error as e:
            print(f"Error: Invalid regex in --find: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.mode == "llm":
        if not args.prompt:
            print("Error: --prompt is required for llm mode.", file=sys.stderr)
            sys.exit(1)
        if not args.search_term:
            print("Error: --search-term is required for llm mode.", file=sys.stderr)
            sys.exit(1)
        if args.context_file and not Path(args.context_file).exists():
            print(f"Error: Context file not found: {args.context_file}", file=sys.stderr)
            sys.exit(1)

    campaign = Campaign(
        name=args.name,
        mode=args.mode,
        orgs=args.orgs,
        file_glob=args.file_glob,
        find=args.find,
        replace=args.replace,
        branch=args.branch,
        commit_msg=args.commit_msg,
        pr_title=args.pr_title,
        pr_body=args.pr_body,
        exclude_repos=args.exclude_repos,
        prompt=args.prompt,
        search_term=args.search_term,
        context_file=args.context_file,
        validation=args.validation,
    )
    path = campaign.save()
    console.print(f"[green]Campaign created:[/green] {path}")
    console.print(f"\nNext step: run [bold]stuc plan {args.name}[/bold] to preview changes.")


def _cmd_list() -> None:
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
            if c.mode == "llm":
                prompt_display = c.prompt[:50] + ("..." if len(c.prompt) > 50 else "")
                console.print(f"  [cyan]{name}[/cyan]  mode=[dim]llm[/dim]  orgs=[dim]{orgs}[/dim]  prompt=[dim]{prompt_display}[/dim]  PRs=[dim]{pr_count}[/dim]")
            else:
                console.print(f"  [cyan]{name}[/cyan]  orgs=[dim]{orgs}[/dim]  find=[dim]{c.find}[/dim]  PRs=[dim]{pr_count}[/dim]")
        except Exception:
            console.print(f"  [cyan]{name}[/cyan]  [dim](could not load)[/dim]")


def _cmd_plan(args: argparse.Namespace) -> None:
    from stuc.discover import show_plan
    campaign = Campaign.load(args.name)
    show_plan(campaign)


def _cmd_apply(args: argparse.Namespace) -> None:
    from stuc.apply import apply_campaign
    campaign = Campaign.load(args.name)
    apply_campaign(campaign, dry_run=args.dry_run, auto_merge=args.auto_merge)


def _cmd_delete(args: argparse.Namespace) -> None:
    from rich.console import Console
    console = Console()

    campaign = Campaign.load(args.name)
    if not args.yes:
        pr_count = len(campaign.prs)
        if pr_count:
            console.print(f"[yellow]Warning: this campaign has {pr_count} PR(s) that will NOT be closed.[/yellow]")
        answer = input(f"Delete campaign '{args.name}'? [y/N] ")
        if answer.lower() not in ("y", "yes"):
            console.print("Aborted.")
            return

    path = campaign.delete()
    console.print(f"[green]Deleted:[/green] {path}")


def _cmd_status(args: argparse.Namespace) -> None:
    from stuc.status import show_status
    campaign = Campaign.load(args.name)
    show_status(campaign, refresh=args.refresh, auto_merge=args.auto_merge)


if __name__ == "__main__":
    main()
