"""Issue body formatting and parsing. Pure functions, no I/O."""

import re

import yaml

from stuc.campaign import Campaign

STUC_DATA_MARKER = "# stuc-campaign-data"
STATUS_TABLE_START = "<!-- stuc-status-start -->"
STATUS_TABLE_END = "<!-- stuc-status-end -->"
STUC_FOOTER = "Managed by [stuc](https://github.com/RijksICTGilde/stuc)"


def _escape_md_table(value: str) -> str:
    """Escape characters that break markdown table cells."""
    return value.replace("|", "\\|").replace("`", "\\`")


def _is_pr_url(value: str) -> bool:
    """Check if a value looks like a GitHub PR URL (vs ERROR/SKIPPED status)."""
    return value.startswith("https://")


def format_issue_body(campaign: Campaign) -> str:
    """Build the full issue body markdown for a campaign."""
    parts = []

    # Campaign definition table
    parts.append("## Campaign definition\n")
    parts.append("| Field | Value |")
    parts.append("|-------|-------|")
    parts.append(f"| Mode | `{campaign.mode}` |")
    parts.append(f"| Orgs | {_escape_md_table(', '.join(campaign.orgs))} |")
    parts.append(f"| File glob | `{_escape_md_table(campaign.file_glob)}` |")
    if campaign.mode == "regex":
        parts.append(f"| Find | `{_escape_md_table(campaign.find)}` |")
        parts.append(f"| Replace | `{_escape_md_table(campaign.replace)}` |")
    else:
        parts.append(f"| Prompt | {_escape_md_table(campaign.prompt)} |")
    parts.append(f"| Branch | `{_escape_md_table(campaign.branch)}` |")
    parts.append("")

    # PR status table (use 5-column format consistently)
    parts.append("## PR status\n")
    parts.append(STATUS_TABLE_START)
    if campaign.prs:
        parts.append("| Repo | PR | State | CI | Merge |")
        parts.append("|------|-----|-------|-----|-------|")
        for repo, pr_url in sorted(campaign.prs.items()):
            if _is_pr_url(pr_url):
                short = pr_short(pr_url)
                parts.append(f"| {repo} | [{short}]({pr_url}) | - | - | - |")
            else:
                parts.append(f"| {repo} | {_escape_md_table(pr_url)} | - | - | - |")
    else:
        parts.append("_No PRs created yet._")
    parts.append(STATUS_TABLE_END)
    parts.append("")

    # Machine-readable YAML block
    data = {
        "name": campaign.name,
        "mode": campaign.mode,
        "orgs": campaign.orgs,
        "file_glob": campaign.file_glob,
        "find": campaign.find,
        "replace": campaign.replace,
        "branch": campaign.branch,
        "commit_msg": campaign.commit_msg,
        "pr_title": campaign.pr_title,
        "pr_body": campaign.pr_body,
        "prs": campaign.prs,
        "prompt": campaign.prompt,
        "search_term": campaign.search_term,
        "exclude_repos": campaign.exclude_repos,
        "issue_repo": campaign.issue_repo,
    }
    yaml_str = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    parts.append("<details>")
    parts.append("<summary>Machine-readable campaign data</summary>")
    parts.append("")
    parts.append(f"```yaml\n{STUC_DATA_MARKER}\n{yaml_str}```")
    parts.append("</details>")
    parts.append("")

    # Usage hints
    parts.append("## Usage\n")
    parts.append("```bash")
    parts.append("uv tool install git+https://github.com/RijksICTGilde/stuc.git")
    if campaign.issue_url:
        parts.append(f"stuc status {campaign.issue_url} --refresh")
    else:
        parts.append(f"stuc status {campaign.name} --refresh")
    parts.append("```")
    parts.append("")
    parts.append("---")
    parts.append(STUC_FOOTER)

    return "\n".join(parts)


def format_pr_body(original_body: str, issue_url: str | None = None) -> str:
    """Append a footer to a PR body with optional issue link and stuc branding.

    Skips if the footer is already present (idempotent).
    """
    if STUC_FOOTER in original_body:
        return original_body

    parts = [original_body, "", "---"]
    if issue_url:
        parts.append(f"Part of campaign: {issue_url}")
    parts.append(STUC_FOOTER)
    return "\n".join(parts)


def update_status_table(issue_body: str, status_rows: list[dict]) -> str:
    """Replace the PR status table in the issue body with updated data.

    status_rows: list of dicts with keys: repo, pr_url, state, ci, merge
    """
    start_idx = issue_body.find(STATUS_TABLE_START)
    end_idx = issue_body.find(STATUS_TABLE_END)
    if start_idx == -1 or end_idx == -1:
        return issue_body

    lines = []
    lines.append(STATUS_TABLE_START)
    if status_rows:
        lines.append("| Repo | PR | State | CI | Merge |")
        lines.append("|------|-----|-------|-----|-------|")
        for row in status_rows:
            pr_url = row["pr_url"]
            if _is_pr_url(pr_url):
                short = pr_short(pr_url)
                pr_cell = f"[{short}]({pr_url})"
            else:
                pr_cell = _escape_md_table(pr_url)
            lines.append(f"| {row['repo']} | {pr_cell} | {row['state']} | {row['ci']} | {row['merge']} |")
    else:
        lines.append("_No PRs created yet._")
    lines.append(STATUS_TABLE_END)

    new_table = "\n".join(lines)
    return issue_body[:start_idx] + new_table + issue_body[end_idx + len(STATUS_TABLE_END) :]


def extract_campaign_from_issue(issue_body: str) -> Campaign:
    """Extract a Campaign from the machine-readable YAML block in an issue body."""
    pattern = rf"```yaml\n{re.escape(STUC_DATA_MARKER)}\n(.*?)```"
    match = re.search(pattern, issue_body, re.DOTALL)
    if not match:
        raise ValueError("No stuc campaign data found in issue body")

    data = yaml.safe_load(match.group(1))
    return Campaign(
        name=data.get("name", "unknown"),
        orgs=data.get("orgs", []),
        file_glob=data.get("file_glob", ""),
        find=data.get("find", ""),
        replace=data.get("replace", ""),
        branch=data.get("branch", ""),
        commit_msg=data.get("commit_msg", ""),
        pr_title=data.get("pr_title", ""),
        pr_body=data.get("pr_body", ""),
        prs=data.get("prs", {}),
        mode=data.get("mode", "regex"),
        prompt=data.get("prompt", ""),
        search_term=data.get("search_term", ""),
        exclude_repos=data.get("exclude_repos", []),
        issue_repo=data.get("issue_repo", ""),
    )


def is_issue_url(value: str) -> bool:
    """Check if a string looks like a GitHub issue URL."""
    return bool(re.match(r"https://github\.com/.+/.+/issues/\d+$", value))


def pr_short(pr_url: str) -> str:
    """Extract short PR reference like 'org/repo#123' from URL."""
    parts = pr_url.rstrip("/").split("/")
    if len(parts) >= 5 and parts[-2] == "pull":
        return f"{parts[-4]}/{parts[-3]}#{parts[-1]}"
    return pr_url
