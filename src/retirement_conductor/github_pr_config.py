"""Secret-safe, explicit configuration for the GitHub pull-request boundary."""

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from retirement_conductor.errors import Refusal
from retirement_conductor.vocabulary import RefusalCode

REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REMOTE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
BRANCH_PREFIX = re.compile(r"^(?!/)(?!.*\.\.)[A-Za-z0-9._/-]+$")


@dataclass(frozen=True)
class GitHubPrSettings:
    """Resolved capability and identity allowlists for one GitHub repository."""

    repository_root: Path
    repository: str
    remote_name: str
    allowed_remote_url: str
    base_branch: str
    branch_prefix: str
    required_check_name: str
    principal: str
    allow_push: bool
    allow_pr_creation: bool
    git_executable: Path
    gh_executable: Path
    timeout_seconds: int = 120

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> GitHubPrSettings:
        values = os.environ if environment is None else environment
        root_text = values.get("GITHUB_PR_REPOSITORY_ROOT", "").strip()
        repository = values.get("GITHUB_PR_REPOSITORY", "").strip()
        allowed_remote_url = values.get("GITHUB_PR_ALLOWED_REMOTE_URL", "").strip()
        if not root_text or not repository or not allowed_remote_url:
            raise Refusal(
                RefusalCode.RUNTIME_CONFIGURATION_INCOMPLETE,
                (
                    "GitHub PR configuration requires repository root, identity, "
                    "and remote URL."
                ),
                {
                    "required_references": [
                        "GITHUB_PR_REPOSITORY_ROOT",
                        "GITHUB_PR_REPOSITORY",
                        "GITHUB_PR_ALLOWED_REMOTE_URL",
                    ]
                },
            )
        if not REPOSITORY.fullmatch(repository):
            _invalid("GITHUB_PR_REPOSITORY must be an exact owner/name identity.")
        if canonical_github_repository(allowed_remote_url) != repository.casefold():
            _invalid("The allowlisted remote URL and repository identity disagree.")
        remote_name = values.get("GITHUB_PR_REMOTE_NAME", "origin").strip()
        if not REMOTE_NAME.fullmatch(remote_name):
            _invalid("GITHUB_PR_REMOTE_NAME is invalid.")
        base_branch = values.get("GITHUB_PR_BASE_BRANCH", "main").strip()
        branch_prefix = values.get(
            "GITHUB_PR_BRANCH_PREFIX", "codex/semantic-pr-"
        ).strip()
        if not base_branch or not BRANCH_PREFIX.fullmatch(branch_prefix):
            _invalid("GitHub base branch or dedicated branch prefix is invalid.")
        required_check = values.get(
            "GITHUB_PR_REQUIRED_CHECK_NAME", "semantic-dbt"
        ).strip()
        principal = values.get("GITHUB_PR_PRINCIPAL", "github-operator").strip()
        if not required_check or not principal:
            _invalid("GitHub safe principal and required check name cannot be empty.")
        allow_push = _boolean(values, "GITHUB_PR_ALLOW_PUSH")
        allow_pr = _boolean(values, "GITHUB_PR_ALLOW_CREATE")
        timeout_text = values.get("GITHUB_PR_TIMEOUT_SECONDS", "120")
        try:
            timeout = int(timeout_text)
        except ValueError as exc:
            raise Refusal(
                RefusalCode.SPEC_SCHEMA_INVALID,
                "GITHUB_PR_TIMEOUT_SECONDS must be an integer.",
            ) from exc
        if timeout < 1 or timeout > 600:
            _invalid("GITHUB_PR_TIMEOUT_SECONDS must be between 1 and 600.")
        git_text = values.get("GITHUB_PR_GIT_EXECUTABLE", "").strip()
        gh_text = values.get("GITHUB_PR_GH_EXECUTABLE", "").strip()
        return cls(
            repository_root=Path(root_text).resolve(),
            repository=repository,
            remote_name=remote_name,
            allowed_remote_url=allowed_remote_url,
            base_branch=base_branch,
            branch_prefix=branch_prefix,
            required_check_name=required_check,
            principal=principal,
            allow_push=allow_push,
            allow_pr_creation=allow_pr,
            git_executable=Path(
                git_text or shutil.which("git") or "/missing/git"
            ).resolve(),
            gh_executable=Path(
                gh_text or shutil.which("gh") or "/missing/gh"
            ).resolve(),
            timeout_seconds=timeout,
        )

    def safe_summary(self) -> dict[str, object]:
        return {
            "repository": self.repository,
            "remote_name": self.remote_name,
            "allowed_remote_repository": canonical_github_repository(
                self.allowed_remote_url
            ),
            "base_branch": self.base_branch,
            "branch_prefix": self.branch_prefix,
            "required_check_name": self.required_check_name,
            "principal": self.principal,
            "allow_push": self.allow_push,
            "allow_pr_creation": self.allow_pr_creation,
            "timeout_seconds": self.timeout_seconds,
        }


def canonical_github_repository(remote_url: str) -> str:
    """Resolve an HTTPS or SSH GitHub URL to a lowercase owner/name identity."""

    value = remote_url.strip()
    if value.startswith("git@github.com:"):
        path = value.removeprefix("git@github.com:")
    else:
        parsed = urlparse(value)
        if parsed.scheme not in {"https", "ssh"} or parsed.hostname != "github.com":
            _invalid("Only an exact github.com remote is supported.")
        if parsed.query or parsed.fragment or parsed.username not in {None, "git"}:
            _invalid("The GitHub remote URL contains unsupported identity components.")
        path = parsed.path.lstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if not REPOSITORY.fullmatch(path):
        _invalid("The GitHub remote URL does not identify one owner/repository.")
    return path.casefold()


def _boolean(values: Mapping[str, str], name: str) -> bool:
    value = values.get(name, "false").strip().casefold()
    if value not in {"true", "false"}:
        _invalid(f"{name} must be true or false.")
    return value == "true"


def _invalid(message: str) -> None:
    raise Refusal(RefusalCode.SPEC_SCHEMA_INVALID, message)
