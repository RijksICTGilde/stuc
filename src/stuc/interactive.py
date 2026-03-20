"""Interactive prompts for init wizard, plan review, and apply confirmation."""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

import questionary

from stuc import gh
from stuc.campaign import Campaign


@dataclass
class InitParams:
    """Typed container for init wizard parameters."""

    name: str = ""
    mode: str = ""
    org: list[str] = field(default_factory=list)
    file_glob: str = ""
    find: str = ""
    replace: str = ""
    prompt: str = ""
    search_term: str = ""
    context_file: str = ""
    validation: str = ""
    branch: str = ""
    commit_msg: str = ""
    pr_title: str = ""
    pr_body: str = ""
    exclude_repo: list[str] = field(default_factory=list)
    issue_repo: str = ""


def _ask(question: questionary.Question) -> str:
    """Ask a questionary question, exit on Ctrl-C."""
    result = question.ask()
    if result is None:
        sys.exit(1)
    return result


def _ask_list(question: questionary.Question) -> list[str]:
    """Ask a questionary checkbox/multi-select, exit on Ctrl-C."""
    result = question.ask()
    if result is None:
        sys.exit(1)
    return result


def _validate_regex(pattern: str) -> bool | str:
    """Validate a regex pattern for questionary."""
    if not pattern:
        return "Pattern is required"
    try:
        re.compile(pattern)
    except re.error as e:
        return f"Invalid regex: {e}"
    return True


def _required(msg: str) -> Callable[[str], bool | str]:
    """Return a questionary validator that rejects empty strings."""
    return lambda val: True if val.strip() else msg


def init_wizard(params: InitParams) -> InitParams:
    """Prompt for missing campaign fields interactively. Returns completed params."""
    from stuc import config as stuc_config

    # Name
    if not params.name:
        params.name = _ask(questionary.text("Campaign name:", validate=_required("Name is required")))

    # Mode
    if not params.mode:
        params.mode = _ask(questionary.select("Campaign mode:", choices=["regex", "llm", "create"], default="regex"))

    mode = params.mode

    # Orgs
    if not params.org:
        available_orgs = gh.list_user_orgs()
        if available_orgs:
            params.org = _ask_list(
                questionary.checkbox(
                    "GitHub orgs to target:",
                    choices=available_orgs,
                    validate=lambda val: True if val else "Select at least one org",
                )
            )
        else:
            orgs: list[str] = []
            while True:
                org = _ask(
                    questionary.text(
                        "GitHub org (empty to finish):" if orgs else "GitHub org to target:",
                        validate=lambda val, o=orgs: True if val.strip() or o else "At least one org is required",
                    )
                )
                if not org.strip():
                    break
                orgs.append(org.strip())
            params.org = orgs

    # File glob
    if not params.file_glob:
        if mode == "create":
            params.file_glob = _ask(
                questionary.text(
                    "Exact file path to create (no wildcards):",
                    validate=lambda val: (
                        "Path is required"
                        if not val.strip()
                        else "Must not contain wildcards"
                        if any(c in val for c in "*?[")
                        else True
                    ),
                )
            )
        else:
            params.file_glob = _ask(
                questionary.text(
                    "File glob pattern (e.g. '.github/workflows/*.yml'):",
                    validate=_required("File glob is required"),
                )
            )

    # Mode-specific fields
    if mode == "regex":
        if not params.find:
            params.find = _ask(questionary.text("Regex pattern to find:", validate=_validate_regex))
        if not params.replace:
            params.replace = _ask(
                questionary.text("Replacement string:", validate=_required("Replacement string is required"))
            )
    elif mode == "llm":
        if not params.prompt:
            params.prompt = _ask(
                questionary.text("LLM instruction for transforming files:", validate=_required("Prompt is required"))
            )
        if not params.search_term:
            params.search_term = _ask(
                questionary.text(
                    "Literal search term for gh search code:", validate=_required("Search term is required")
                )
            )
    elif mode == "create":
        if not params.prompt:
            params.prompt = _ask(
                questionary.text("LLM instruction for generating the file:", validate=_required("Prompt is required"))
            )

    # Branch
    if not params.branch:
        params.branch = _ask(
            questionary.text(
                "Git branch name:",
                default=f"stuc/{params.name}",
                validate=_required("Branch name is required"),
            )
        )

    # Commit message
    if not params.commit_msg:
        params.commit_msg = _ask(questionary.text("Commit message:", validate=_required("Commit message is required")))

    # PR title
    if not params.pr_title:
        params.pr_title = _ask(questionary.text("PR title:", validate=_required("PR title is required")))

    # PR body (optional) - default from global config
    if not params.pr_body:
        config_default = stuc_config.get("pr_body") or "Automated migration by stuc."
        params.pr_body = _ask(questionary.text("PR body (Enter to use default):", default=config_default))

    # Exclude repos (optional)
    if not params.exclude_repo:
        exclude = _ask(questionary.text("Repos to exclude (comma-separated, or Enter to skip):"))
        params.exclude_repo = [r.strip() for r in exclude.split(",") if r.strip()] if exclude.strip() else []

    # Issue repo (optional) - default from global config
    if not params.issue_repo:
        config_default = stuc_config.get("issue_repo") or ""
        if config_default:
            params.issue_repo = config_default
        else:
            params.issue_repo = _ask(questionary.text("Tracking issue repo (Enter to skip):")) or ""

    # Context file (llm/create only)
    if mode in ("llm", "create") and not params.context_file:
        params.context_file = _ask(questionary.text("Context file path (Enter to skip):")) or ""

    # Validation command (llm/create only)
    if mode in ("llm", "create") and not params.validation:
        params.validation = _ask(questionary.text("Validation command (Enter to skip):")) or ""

    return params


def review_plan(campaign: Campaign, changes: dict) -> None:
    """Interactive plan review: let user exclude repos after seeing diffs."""
    if not changes or not sys.stdin.isatty():
        return

    repos = sorted(changes.keys())
    print(f"\nFound changes in {len(repos)} repos:")
    for repo in repos:
        print(f"  {repo} ({len(changes[repo])} file(s))")

    selected = _ask_list(questionary.checkbox("Select repos to EXCLUDE from apply:", choices=repos))

    if selected:
        campaign.exclude_repos = list(set(campaign.exclude_repos) | set(selected))
        campaign.save()
        print(f"Excluded {len(selected)} repo(s). Updated campaign.")

    print(f"\nNext step: run stuc apply {campaign.name}")


def confirm_apply(campaign: Campaign, changes: dict) -> bool:
    """Show apply summary and ask for confirmation. Returns True to proceed."""
    repos = sorted(changes.keys())
    total_files = sum(len(files) for files in changes.values())

    print(f"\nAbout to apply campaign '{campaign.name}':")
    print(f"  {len(repos)} repo(s), {total_files} file(s)")
    for repo in repos:
        print(f"    {repo} ({len(changes[repo])} file(s))")

    return _ask(questionary.confirm("Proceed with apply?", default=True))
