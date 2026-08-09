from __future__ import annotations

import pytest

from retirement_conductor.errors import Refusal
from retirement_conductor.superset_config import SupersetSettings


def test_superset_settings_are_apply_opt_in_and_secret_safe() -> None:
    settings = SupersetSettings.from_environment(
        {
            "SUPERSET_URL": "http://127.0.0.1:18088",
            "SUPERSET_USERNAME": "operator",
            "SUPERSET_PASSWORD": "do-not-render",
            "SUPERSET_VERSION": "6.0.0",
            "SUPERSET_ALLOW_APPLY": "true",
            "SUPERSET_ALLOWED_DATASET_IDS": "7, 7, 3",
        }
    )

    assert settings.allow_apply is True
    assert settings.allowed_dataset_ids == (3, 7)
    assert "do-not-render" not in str(settings.safe_summary())


@pytest.mark.parametrize(
    "environment",
    [
        {},
        {
            "SUPERSET_URL": "https://shared.example",
            "SUPERSET_USERNAME": "u",
            "SUPERSET_PASSWORD": "p",
            "SUPERSET_VERSION": "6.0.0",
        },
        {
            "SUPERSET_URL": "http://127.0.0.1:18088",
            "SUPERSET_USERNAME": "u",
            "SUPERSET_PASSWORD": "p",
            "SUPERSET_VERSION": "6.0.0",
            "SUPERSET_ALLOW_APPLY": "yes",
        },
    ],
)
def test_superset_settings_refuse_incomplete_or_broad_scope(
    environment: dict[str, str],
) -> None:
    with pytest.raises(Refusal):
        SupersetSettings.from_environment(environment)
