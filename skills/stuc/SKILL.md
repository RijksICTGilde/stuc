---
name: stuc
description: Fleet-wide find-and-replace across GitHub org repos. Use when the user wants to make the same text change across many repositories in a GitHub org - like bumping action versions, updating URLs, renaming packages, migrating config patterns, or adding new files to repos that don't have them. Supports regex, LLM-powered (claude) transformations, and file creation mode.
---

# stuc - fleet-wide repo updates

You are helping the user run a multi-repo campaign using the `stuc` CLI. stuc supports three modes: **regex** (deterministic find-and-replace), **llm** (context-aware transformations via `claude -p`), and **create** (add new files to repos that don't have them).

## Prerequisite check

Before doing anything, verify the `gh` CLI is authenticated:

```bash
gh auth status
```

If this fails, stop and tell the user to run `gh auth login` first.

For LLM mode, also verify the `claude` CLI is available:

```bash
claude --version
```

If this fails, tell the user to install it from https://claude.ai/code.

Also verify stuc is installed:

```bash
stuc --help
```

If this fails, install it: `uv tool install -e /path/to/stuc` (or `uv tool install stuc` if published).

## Workflow

stuc has seven subcommands. The core pipeline has four steps that run in order:

### 1. Init - create the campaign

**Regex mode** (default):

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

**LLM mode** (for context-aware transformations):

```bash
stuc init <campaign-name> \
  --mode llm \
  --org <github-org> \
  --file-glob "<glob-pattern>" \
  --search-term "<literal-search-term>" \
  --prompt "<instruction-for-claude>" \
  --branch "stuc/<campaign-name>" \
  --commit-msg "<conventional-commit-message>" \
  --pr-title "<PR title>"
```

**Create mode** (add new files to repos that don't have them):

```bash
stuc init <campaign-name> \
  --mode create \
  --org <github-org> \
  --file-glob "<exact-file-path>" \
  --prompt "<instruction-for-claude-to-generate-file>" \
  --branch "stuc/<campaign-name>" \
  --commit-msg "<conventional-commit-message>" \
  --pr-title "<PR title>"
```

Key details for all modes:
- `--file-glob` uses fnmatch syntax: `".github/workflows/*.yml"`, `"**/*.toml"`
- `--org` can be repeated: `--org OrgA --org OrgB`
- `--exclude-repo` can be repeated: `--exclude-repo org/repo1 --exclude-repo org/repo2`
- `--issue-repo <org/repo>` creates a tracking issue in that repo (falls back to `stuc config issue_repo`)
- Campaign is saved to `~/.stuc/campaigns/<name>.yml`

Regex mode details:
- `--find` takes a Python regex. Use capture groups like `([^@]+)` and reference them in `--replace` with `\1`

LLM mode details:
- `--search-term` is a literal string used for GitHub code search to discover candidate files
- `--prompt` is the instruction passed to `claude -p` for each file
- `--context-file` (optional) path to a file with extra context included in the LLM prompt
- `--validation` (optional) shell command to validate each transformed file (runs during `apply`)

Create mode details:
- `--file-glob` must be an exact file path (no wildcards), e.g. `.github/dependabot.yml`
- `--prompt` is the instruction passed to `claude -p` to generate the file content
- Discovery is inverted: stuc lists org repos and checks which ones are **missing** the target file
- `--context-file` and `--validation` work the same as in LLM mode

### 2. Plan - preview changes

```bash
stuc plan <campaign-name>
```

This searches GitHub for matching files and shows a diff preview. No changes are made. Review the output with the user before proceeding.

### 3. Apply - execute the campaign

```bash
stuc apply <campaign-name>
```

This clones each repo, creates a branch, applies the transformation, commits, pushes, and opens a PR. If `issue_repo` is configured (via `--issue-repo` or `stuc config`), a tracking issue is created on first apply and updated with PR links. Add `--dry-run` if the user wants another check. Add `--auto-merge` to enable auto-merge on PRs.

### 4. Status - track PRs

```bash
stuc status <campaign-name> --refresh
```

Shows PR state (open/merged/closed) and CI results. Use `--auto-merge` to enable auto-merge on open PRs with green CI.

You can also pass a GitHub issue URL instead of a campaign name:

```bash
stuc status https://github.com/MyOrg/fleet-ops/issues/42 --refresh
```

This reconstructs the campaign from the machine-readable YAML embedded in the issue body.

## Other commands

```bash
stuc list                              # show all existing campaigns
stuc delete <name> [--yes]             # delete a campaign definition (does not close PRs)
stuc config                            # show all global config
stuc config issue_repo MyOrg/fleet-ops # set default tracking issue repo
stuc config pr_body "Custom body text" # set default PR body
stuc --help                            # full help with examples
stuc <cmd> --help                      # help for a specific subcommand
```

## How to handle user requests

Based on what the user wants:

1. **Pick the right mode**: If the change is a deterministic text substitution (version bumps, URL renames, config values), use **regex** mode. If the change needs understanding of context (refactoring, adding sections, rewriting based on guidelines), use **llm** mode. If the user wants to add a new file to repos that don't have it (Dependabot config, LICENSE, SECURITY.md, CI workflows), use **create** mode.
2. **Regex mode**: Translate the user's description into a `--find` regex and `--replace` string. Test the regex mentally against likely file content. If unsure, ask.
3. **LLM mode**: Write a clear `--prompt` instruction. Pick a `--search-term` that will find the right files via GitHub code search. If the user has a reference document (style guide, spec, etc.), use `--context-file`.
4. **Figure out the file glob**: What files would contain this text? Workflow files, config files, source code?
5. **Pick a good campaign name**: Short, descriptive, kebab-case (e.g. `bump-checkout-v4`, `migrate-api-url`)
6. **Use conventional commits**: `chore:`, `fix:`, `build:` etc. for the commit message
7. **Run each step in order**: init, plan (review with user), apply, status

**LLM/create mode caveats**: Each file requires a `claude -p` call, so `plan` is slower. LLM output is non-deterministic - the diff at `plan` time shows the direction, but `apply` may produce slightly different output. Review carefully.

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
- "No matching files found" - check the "Search query:" output. For regex mode: if it looks garbled, restructure your regex so the literal part (e.g. `org/repo`) is not hidden inside character classes. For LLM mode: adjust your `--search-term`
- PR already exists - stuc skips repos that already have an open PR on the campaign branch. This is safe to re-run.
- "claude CLI not found" - install from https://claude.ai/code (LLM mode only)
- "LLM transform failed" - the `claude -p` call failed or timed out. Check that `claude` works standalone. Large files may need more time.

## Important

- Always run `stuc plan` and show the results to the user before running `stuc apply`
- The plan step is read-only. Only `apply` creates branches and PRs.
- If the regex is tricky, test it with a quick Python snippet first:
  ```bash
  uv run python -c "import re; print(re.sub(r'<find>', r'<replace>', '<sample-input>'))"
  ```
