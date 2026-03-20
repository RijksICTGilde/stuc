"""Global stuc configuration (~/.stuc/config.yml)."""

from pathlib import Path

import yaml

CONFIG_PATH = Path.home() / ".stuc" / "config.yml"

DEFAULTS = {
    "issue_repo": "",
    "pr_body": "",
}


def load() -> dict:
    """Load config, returning defaults for missing keys."""
    data = {}
    if CONFIG_PATH.exists():
        data = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    return {**DEFAULTS, **data}


def save(data: dict) -> Path:
    """Save config to disk."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    return CONFIG_PATH


def get(key: str) -> str:
    """Get a single config value."""
    return load().get(key, DEFAULTS.get(key, ""))


def set_value(key: str, value: str) -> Path:
    """Set a single config value and save."""
    data = load()
    data[key] = value
    return save(data)
