from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from retirement_conductor.errors import Refusal
from retirement_conductor.looker_config import LookerSettings


def _environment(**overrides: str) -> dict[str, str]:
    values = {
        "LOOKER_BASE_URL": "http://127.0.0.1:19999",
        "LOOKER_CLIENT_ID": "fixture-client",
        "LOOKER_CLIENT_SECRET": "fixture-secret-value",
        "LOOKER_PLATFORM_INSTANCE": "retirement-disposable",
        "LOOKER_PROJECT_ID": "retirement_project",
        "LOOKER_MODEL_ID": "commerce",
        "LOOKER_EXPLORE_ID": "orders",
        "LOOKER_FOLDER_ID": "9",
        "LOOKER_CONTENT_TARGET": "look:41",
        "LOOKER_LEGACY_REFERENCE": "orders.legacy_status",
        "LOOKER_REPLACEMENT_REFERENCE": "orders.order_status",
        "LOOKER_DATAHUB_URN": (
            "urn:li:dashboard:(looker,retirement-disposable.look.41)"
        ),
        "LOOKER_GRAPH_SNAPSHOT_DIGEST": f"sha256:{'7' * 64}",
        "LOOKER_MODE": "fixture",
        "LOOKER_ALLOW_APPLY": "false",
    }
    values.update(overrides)
    return values


def test_settings_are_secret_safe_and_accept_official_aliases() -> None:
    values = _environment()
    values["LOOKERSDK_CLIENT_ID"] = values.pop("LOOKER_CLIENT_ID")
    values["LOOKERSDK_CLIENT_SECRET"] = values.pop("LOOKER_CLIENT_SECRET")
    settings = LookerSettings.from_environment(values)

    rendered = repr(settings)
    summary = settings.safe_summary()

    assert "fixture-secret-value" not in rendered
    assert "fixture-client" not in rendered
    assert "fixture-secret-value" not in str(summary)
    assert "fixture-client" not in str(summary)
    assert summary["credentials_configured"] is True
    assert settings.look_id == "41"


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"LOOKER_CONTENT_TARGET": "look:*"}, "SCOPE_TARGET_NOT_ALLOWED"),
        (
            {
                "LOOKER_MODE": "live",
                "LOOKER_BASE_URL": "http://looker.example.invalid",
            },
            "SOURCE_LOOKER_UNAVAILABLE",
        ),
        (
            {
                "LOOKER_CLIENT_ID": "one",
                "LOOKERSDK_CLIENT_ID": "two",
            },
            "SPEC_SCHEMA_INVALID",
        ),
        (
            {"LOOKER_GRAPH_SNAPSHOT_DIGEST": "not-a-digest"},
            "INTEGRITY_DIGEST_MISMATCH",
        ),
        (
            {"LOOKER_LEGACY_REFERENCE": "legacy_status"},
            "SPEC_SCHEMA_INVALID",
        ),
    ],
)
def test_settings_refuse_unsafe_or_ambiguous_scope(
    overrides: Mapping[str, str],
    code: str,
) -> None:
    with pytest.raises(Refusal) as raised:
        LookerSettings.from_environment(_environment(**dict(overrides)))
    assert raised.value.code == code


def test_settings_require_every_non_secret_identity() -> None:
    environment: dict[str, Any] = _environment()
    environment["LOOKER_PROJECT_ID"] = ""
    with pytest.raises(Refusal) as raised:
        LookerSettings.from_environment(environment)
    assert raised.value.code == "SPEC_SCHEMA_INVALID"
    assert raised.value.details == {"missing_settings": ["project_id"]}
