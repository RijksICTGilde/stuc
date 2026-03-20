# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is stuc?

stuc is a CLI tool for fleet-wide regex-based find-and-replace across GitHub org repos. It discovers matching files via `gh search code`, previews diffs, then clones repos, applies changes, and opens PRs. Campaigns (find/replace definitions targeting specific orgs and file globs) are persisted as YAML in `~/.stuc/campaigns/`.

## Commands

```bash
# Install
uv sync

# Run tests
uv run pytest

# Run a single test
uv run pytest tests/test_discover.py::test_extract_search_term_simple

# Run the CLI
uv run stuc --help
```

## Architecture

The CLI has four subcommands that form a pipeline: `init` -> `plan` -> `apply` -> `status`.

- **cli.py** - argparse entrypoint, dispatches to subcommand handlers
- **campaign.py** - `Campaign` dataclass with YAML serialization to `~/.stuc/campaigns/`. Stores find/replace pattern, target orgs, file glob, branch/PR config, and tracks created PR URLs
- **discover.py** - Uses `gh search code` to find matching files across orgs, then fetches file content via GitHub API to generate before/after diffs. `_extract_search_term()` strips regex syntax to produce a literal query for GitHub's code search
- **gh.py** - Thin wrapper around the `gh` CLI. All GitHub interaction goes through this module (search, clone, PR creation, status checks, auto-merge)
- **apply.py** - Clones each repo to a tempdir, applies regex substitution, commits, pushes a branch, and creates a PR. Skips repos that already have an open PR on the campaign branch
- **status.py** - Fetches PR state and CI check status for all PRs in a campaign, with optional auto-merge for green PRs

## Testing

Tests mock `subprocess.run` and `CAMPAIGNS_DIR` to avoid real GitHub calls and filesystem side effects. The `tmp_path` pytest fixture is used for campaign file I/O tests.
