"""Secret-safe configuration for the local Git/dbt adapter."""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from retirement_conductor.canonical import digest_json
from retirement_conductor.errors import Refusal
from retirement_conductor.vocabulary import RefusalCode


@dataclass(frozen=True)
class GitDbtSettings:
    """Resolved local paths and capabilities for one disposable repository."""

    repository_root: Path
    repository_id: str
    default_branch: str
    dbt_executable: Path
    principal: str
    allow_apply: bool
    validation_timeout_seconds: int
    bwrap_executable: Path
    git_executable: Path

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> GitDbtSettings:
        values = os.environ if environment is None else environment
        root_value = values.get("GIT_DBT_REPOSITORY_ROOT", "").strip()
        if not root_value:
            raise Refusal(
                RefusalCode.SOURCE_GIT_UNAVAILABLE,
                "GIT_DBT_REPOSITORY_ROOT must identify the disposable repository.",
                {"required_reference": "GIT_DBT_REPOSITORY_ROOT"},
            )
        repository_root = Path(root_value).resolve()
        dbt_value = values.get(
            "GIT_DBT_DBT_EXECUTABLE",
            ".retirement-conductor/tools/dbt-duckdb-1.10.1/bin/dbt",
        ).strip()
        bwrap_value = values.get("GIT_DBT_BWRAP_EXECUTABLE", "").strip()
        git_value = values.get("GIT_DBT_GIT_EXECUTABLE", "").strip()
        bwrap = Path(bwrap_value or shutil.which("bwrap") or "/missing/bwrap").resolve()
        git = Path(git_value or shutil.which("git") or "/missing/git").resolve()
        timeout_text = values.get(
            "GIT_DBT_VALIDATION_TIMEOUT_SECONDS",
            "180",
        )
        try:
            timeout = int(timeout_text)
        except ValueError as exc:
            raise Refusal(
                RefusalCode.SPEC_SCHEMA_INVALID,
                "The Git/dbt validation timeout must be an integer.",
            ) from exc
        if timeout < 1 or timeout > 900:
            raise Refusal(
                RefusalCode.SPEC_SCHEMA_INVALID,
                "The Git/dbt validation timeout must be between 1 and 900 seconds.",
            )
        allow_text = values.get("GIT_DBT_ALLOW_APPLY", "false").strip().lower()
        if allow_text not in {"true", "false"}:
            raise Refusal(
                RefusalCode.SPEC_SCHEMA_INVALID,
                "GIT_DBT_ALLOW_APPLY must be true or false.",
            )
        repository_id = values.get("GIT_DBT_REPOSITORY_ID", "analytics").strip()
        default_branch = values.get("GIT_DBT_DEFAULT_BRANCH", "main").strip()
        principal = values.get(
            "GIT_DBT_PRINCIPAL",
            "local-disposable-operator",
        ).strip()
        if not repository_id or not default_branch or not principal:
            raise Refusal(
                RefusalCode.SPEC_SCHEMA_INVALID,
                "Git/dbt safe identity settings cannot be empty.",
            )
        return cls(
            repository_root=repository_root,
            repository_id=repository_id,
            default_branch=default_branch,
            dbt_executable=Path(dbt_value).resolve(),
            principal=principal,
            allow_apply=allow_text == "true",
            validation_timeout_seconds=timeout,
            bwrap_executable=bwrap,
            git_executable=git,
        )

    def safe_summary(self) -> dict[str, object]:
        return {
            "repository_id": self.repository_id,
            "repository_identity": digest_json(str(self.repository_root)),
            "default_branch": self.default_branch,
            "dbt_tool_identity": digest_json(str(self.dbt_executable)),
            "principal": self.principal,
            "allow_apply": self.allow_apply,
            "validation_timeout_seconds": self.validation_timeout_seconds,
            "sandbox": "bubblewrap-unshared-network",
        }
