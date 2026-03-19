---
name: stuc
description: Fleet-wide regex find-and-replace across GitHub org repos. Use when the user wants to make the same text change across many repositories in a GitHub org - like bumping action versions, updating URLs, renaming packages, or migrating config patterns.
---

# stuc - fleet-wide regex updates

You are helping the user run a multi-repo find-and-replace campaign using the `stuc` CLI.

## Prerequisite check

Before doing anything, verify the `gh` CLI is authenticated:

```bash
gh auth status
```

If this fails, stop and tell the user to run `gh auth login` first.

Also verify stuc is installed:

```bash
stuc --help
```

If this fails, install it: `uv tool install -e /path/to/stuc` (or `uv tool install stuc` if published).

## Workflow

stuc has four steps that run in order. Always follow this sequence:

### 1. Init - create the campaign

```bash
stuc init <campaign-name> \
  --org <github-org> \
  --file-glob "<glob-pattern>" \
  --find "<python-regex>" \
  --replace "<replacement>" \
  --branch "stuc/<campaign-name>" \
  --commit-msg "<conventional-commit-message>" \
  --pr-title "<PR title>"
```

Key details:
- `--find` takes a Python regex. Use capture groups like `([^@]+)` and reference them in `--replace` with `\1`
- `--file-glob` uses fnmatch syntax: `".github/workflows/*.yml"`, `"**/*.toml"`
- `--org` can be repeated: `--org OrgA --org OrgB`
- `--exclude-repo` can be repeated: `--exclude-repo org/repo1 --exclude-repo org/repo2`
- Campaign is saved to `~/.stuc/campaigns/<name>.yml`

### 2. Plan - preview changes

```bash
stuc plan <campaign-name>
```

This searches GitHub for matching files and shows a diff preview. No changes are made. Review the output with the user before proceeding.

### 3. Apply - execute the campaign

```bash
stuc apply <campaign-name>
```

This clones each repo, creates a branch, applies the regex, commits, pushes, and opens a PR. Add `--dry-run` if the user wants another check. Add `--auto-merge` to enable auto-merge on PRs.

### 4. Status - track PRs

```bash
stuc status <campaign-name> --refresh
```

Shows PR state (open/merged/closed) and CI results. Use `--auto-merge` to enable auto-merge on open PRs with green CI.

## Other commands

```bash
stuc list                    # show all existing campaigns
stuc delete <name> [--yes]   # delete a campaign definition (does not close PRs)
stuc --help                  # full help with examples
stuc <cmd> --help            # help for a specific subcommand
```

## How to handle user requests

Based on what the user wants:

1. **Figure out the regex**: Translate the user's description into a `--find` regex and `--replace` string. Test the regex mentally against likely file content. If unsure, ask.
2. **Figure out the file glob**: What files would contain this text? Workflow files, config files, source code?
3. **Pick a good campaign name**: Short, descriptive, kebab-case (e.g. `bump-checkout-v4`, `migrate-api-url`)
4. **Use conventional commits**: `chore:`, `fix:`, `build:` etc. for the commit message
5. **Run each step in order**: init, plan (review with user), apply, status

## Regex design for GitHub search

`stuc plan` uses GitHub code search to find candidate files. GitHub code search is literal text, not regex. stuc extracts a search query from your `--find` regex by stripping regex syntax.

**How it works**: literal text is preserved, character classes (`[a-z]`) and their content are removed, group parentheses are removed but literal text inside groups is kept, escape sequences (`\s`, `\d`, `\b`) are removed, and trailing version fragments are stripped.

**Design your regex so the distinctive literal text survives extraction.** For example:
- `RijksICTGilde/zad-actions/([a-z-]+)@v[12]\b` → search query: `RijksICTGilde/zad-actions`
- `actions/checkout@v\d+` → search query: `actions/checkout`

If `stuc plan` reports "No matching files found", the search query was probably too short or garbled. Check what it shows as "Search query:" and adjust your regex so the literal part is clear.

## Error recovery

- "Campaign not found" - run `stuc list` to see what exists, or `stuc init` to create one
- "gh command failed" - check `gh auth status` and network connectivity
- "Invalid regex" - the `--find` pattern has syntax errors; fix and re-run `stuc init` with the same name (it overwrites)
- "No matching files found" - check the "Search query:" output. If it looks garbled, restructure your regex so the literal part (e.g. `org/repo`) is not hidden inside character classes
- PR already exists - stuc skips repos that already have an open PR on the campaign branch. This is safe to re-run.

## Important

- Always run `stuc plan` and show the results to the user before running `stuc apply`
- The plan step is read-only. Only `apply` creates branches and PRs.
- If the regex is tricky, test it with a quick Python snippet first:
  ```bash
  uv run python -c "import re; print(re.sub(r'<find>', r'<replace>', '<sample-input>'))"
  ```
