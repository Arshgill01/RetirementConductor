from __future__ import annotations

import pytest

from retirement_conductor.datahub_config import DataHubSettings
from retirement_conductor.errors import Refusal


def test_datahub_settings_expose_reference_not_token_value() -> None:
    settings = DataHubSettings.from_environment(
        {
            "DATAHUB_GMS_URL": "http://127.0.0.1:18080/",
            "DATAHUB_GMS_TOKEN_REFERENCE": "DISPOSABLE_TOKEN",
            "DISPOSABLE_TOKEN": "do-not-render-this-value",
            "DATAHUB_MCP_URL": "http://127.0.0.1:8000/mcp",
        }
    )

    summary = settings.safe_summary()

    assert settings.token == "do-not-render-this-value"
    assert summary["token_reference"] == "DISPOSABLE_TOKEN"
    assert summary["token_present"] is True
    assert "do-not-render-this-value" not in str(summary)


def test_datahub_settings_require_explicit_gms_endpoint() -> None:
    with pytest.raises(Refusal, match="SOURCE_DATAHUB_UNAVAILABLE"):
        DataHubSettings.from_environment({})


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://user:do-not-render@datahub.test",
        "https://datahub.test?token=do-not-render",
        "file:///tmp/datahub",
    ],
)
def test_datahub_settings_reject_secret_bearing_or_non_http_urls(
    endpoint: str,
) -> None:
    with pytest.raises(Refusal) as caught:
        DataHubSettings.from_environment({"DATAHUB_GMS_URL": endpoint})

    assert "do-not-render" not in str(caught.value.as_dict())
