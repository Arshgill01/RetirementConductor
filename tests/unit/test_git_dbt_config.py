from __future__ import annotations

from pathlib import Path

import pytest

from retirement_conductor.errors import Refusal
from retirement_conductor.git_dbt_config import GitDbtSettings


def test_git_dbt_settings_are_opt_in_and_secret_safe(tmp_path: Path) -> None:
    settings = GitDbtSettings.from_environment(
        {
            "GIT_DBT_REPOSITORY_ROOT": str(tmp_path),
            "GIT_DBT_REPOSITORY_ID": "analytics",
            "GIT_DBT_DEFAULT_BRANCH": "main",
            "GIT_DBT_DBT_EXECUTABLE": "/usr/bin/true",
            "GIT_DBT_PRINCIPAL": "disposable-operator",
            "GIT_DBT_ALLOW_APPLY": "true",
            "GIT_DBT_VALIDATION_TIMEOUT_SECONDS": "45",
            "UNRELATED_SECRET": "must-not-appear",
        }
    )

    summary = settings.safe_summary()

    assert settings.allow_apply is True
    assert summary["repository_id"] == "analytics"
    assert summary["validation_timeout_seconds"] == 45
    assert "must-not-appear" not in str(summary)


@pytest.mark.parametrize(
    "environment",
    [
        {},
        {
            "GIT_DBT_REPOSITORY_ROOT": "/tmp/repository",
            "GIT_DBT_ALLOW_APPLY": "yes",
        },
        {
            "GIT_DBT_REPOSITORY_ROOT": "/tmp/repository",
            "GIT_DBT_VALIDATION_TIMEOUT_SECONDS": "0",
        },
    ],
)
def test_git_dbt_settings_refuse_unsafe_or_incomplete_values(
    environment: dict[str, str],
) -> None:
    with pytest.raises(Refusal):
        GitDbtSettings.from_environment(environment)
