"""Campaign YAML CRUD."""

import datetime
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CAMPAIGNS_DIR = Path.home() / ".stuc" / "campaigns"


@dataclass
class Campaign:
    name: str
    orgs: list[str]
    file_glob: str
    find: str = ""
    replace: str = ""
    branch: str = ""
    commit_msg: str = ""
    pr_title: str = ""
    pr_body: str = ""
    repos: list[str] = field(default_factory=list)
    exclude_repos: list[str] = field(default_factory=list)
    created_at: str = ""
    prs: dict[str, str] = field(default_factory=dict)  # repo -> pr_url
    mode: str = "regex"  # "regex" or "llm"
    prompt: str = ""  # LLM instruction
    search_term: str = ""  # Explicit search term for gh search code
    context_file: str = ""  # Path to context file on disk
    validation: str = ""  # Shell command to validate output
    issue_repo: str = ""  # Repo for tracking issue, e.g. "MyOrg/fleet-ops"
    issue_url: str = ""  # URL of the created tracking issue

    @property
    def path(self) -> Path:
        return CAMPAIGNS_DIR / f"{self.name}.yml"

    def save(self) -> Path:
        CAMPAIGNS_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "name": self.name,
            "mode": self.mode,
            "orgs": self.orgs,
            "file_glob": self.file_glob,
            "find": self.find,
            "replace": self.replace,
            "branch": self.branch,
            "commit_msg": self.commit_msg,
            "pr_title": self.pr_title,
            "pr_body": self.pr_body,
            "repos": self.repos,
            "exclude_repos": self.exclude_repos,
            "created_at": self.created_at or datetime.datetime.now(datetime.UTC).isoformat(),
            "prs": self.prs,
            "prompt": self.prompt,
            "search_term": self.search_term,
            "context_file": self.context_file,
            "validation": self.validation,
            "issue_repo": self.issue_repo,
            "issue_url": self.issue_url,
        }
        self.path.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False))
        return self.path

    @classmethod
    def load(cls, name: str) -> "Campaign":
        path = CAMPAIGNS_DIR / f"{name}.yml"
        if not path.exists():
            raise FileNotFoundError(f"Campaign not found: {name}\nExpected at: {path}")
        data = yaml.safe_load(path.read_text())
        return cls(
            name=data["name"],
            orgs=data.get("orgs", []),
            file_glob=data["file_glob"],
            find=data.get("find", ""),
            replace=data.get("replace", ""),
            branch=data.get("branch", ""),
            commit_msg=data.get("commit_msg", ""),
            pr_title=data.get("pr_title", ""),
            pr_body=data.get("pr_body", ""),
            repos=data.get("repos", []),
            exclude_repos=data.get("exclude_repos", []),
            created_at=data.get("created_at", ""),
            prs=data.get("prs", {}),
            mode=data.get("mode", "regex"),
            prompt=data.get("prompt", ""),
            search_term=data.get("search_term", ""),
            context_file=data.get("context_file", ""),
            validation=data.get("validation", ""),
            issue_repo=data.get("issue_repo", ""),
            issue_url=data.get("issue_url", ""),
        )

    def delete(self) -> Path:
        path = self.path
        if not path.exists():
            raise FileNotFoundError(f"Campaign not found: {self.name}\nExpected at: {path}")
        path.unlink()
        return path

    @classmethod
    def list_all(cls) -> list[str]:
        if not CAMPAIGNS_DIR.exists():
            return []
        return [p.stem for p in CAMPAIGNS_DIR.glob("*.yml")]
