"""CLI entrypoint with subcommands: init, plan, apply, status."""

import argparse
import sys

from stuc.campaign import Campaign


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="stuc",
        description="Fleet-wide regex updates across GitHub org repos",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Create a new campaign")
    p_init.add_argument("name", help="Campaign name")
    p_init.add_argument("--org", action="append", required=True, dest="orgs", help="GitHub org(s) to target")
    p_init.add_argument("--file-glob", required=True, help="Glob pattern for files to modify")
    p_init.add_argument("--find", required=True, help="Regex pattern to find")
    p_init.add_argument("--replace", required=True, help="Replacement string")
    p_init.add_argument("--branch", required=True, help="Branch name for PRs")
    p_init.add_argument("--commit-msg", required=True, help="Commit message")
    p_init.add_argument("--pr-title", required=True, help="PR title")
    p_init.add_argument("--pr-body", default="Automated migration by stuc.", help="PR body")
    p_init.add_argument("--exclude-repo", action="append", default=[], dest="exclude_repos", help="Repos to skip")

    # plan
    p_plan = subparsers.add_parser("plan", help="Dry run — show what would change")
    p_plan.add_argument("name", help="Campaign name")

    # apply
    p_apply = subparsers.add_parser("apply", help="Execute the campaign")
    p_apply.add_argument("name", help="Campaign name")
    p_apply.add_argument("--dry-run", action="store_true", help="Show what would happen without making changes")
    p_apply.add_argument("--auto-merge", action="store_true", help="Enable auto-merge on created PRs")

    # status
    p_status = subparsers.add_parser("status", help="Check PR and CI status")
    p_status.add_argument("name", help="Campaign name")
    p_status.add_argument("--refresh", action="store_true", help="Re-fetch status from GitHub")
    p_status.add_argument("--auto-merge", action="store_true", help="Enable auto-merge on open PRs with green CI")

    args = parser.parse_args()

    if args.command == "init":
        _cmd_init(args)
    elif args.command == "plan":
        _cmd_plan(args)
    elif args.command == "apply":
        _cmd_apply(args)
    elif args.command == "status":
        _cmd_status(args)


def _cmd_init(args: argparse.Namespace) -> None:
    from rich.console import Console
    console = Console()

    campaign = Campaign(
        name=args.name,
        orgs=args.orgs,
        file_glob=args.file_glob,
        find=args.find,
        replace=args.replace,
        branch=args.branch,
        commit_msg=args.commit_msg,
        pr_title=args.pr_title,
        pr_body=args.pr_body,
        exclude_repos=args.exclude_repos,
    )
    path = campaign.save()
    console.print(f"[green]Campaign created:[/green] {path}")


def _cmd_plan(args: argparse.Namespace) -> None:
    from stuc.discover import show_plan
    campaign = Campaign.load(args.name)
    show_plan(campaign)


def _cmd_apply(args: argparse.Namespace) -> None:
    from stuc.apply import apply_campaign
    campaign = Campaign.load(args.name)
    apply_campaign(campaign, dry_run=args.dry_run, auto_merge=args.auto_merge)


def _cmd_status(args: argparse.Namespace) -> None:
    from stuc.status import show_status
    campaign = Campaign.load(args.name)
    show_status(campaign, refresh=args.refresh, auto_merge=args.auto_merge)


if __name__ == "__main__":
    main()
