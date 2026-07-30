from __future__ import annotations

import json
from pathlib import Path

import pytest

from retirement_conductor.cli import main
from retirement_conductor.looker_access import (
    CONTROL_VARIABLES,
    DERIVED_EVIDENCE_VARIABLES,
    LOOKER_ACCESS_VARIABLES,
    OPTIONAL_SECRET_VARIABLES,
    write_looker_access_packet,
)
from retirement_conductor.looker_config import LookerSettings


def _marked_environment() -> tuple[dict[str, str], list[str]]:
    names = (
        *LOOKER_ACCESS_VARIABLES,
        *DERIVED_EVIDENCE_VARIABLES,
        *OPTIONAL_SECRET_VARIABLES,
        *CONTROL_VARIABLES,
    )
    values = {name: f"sensitive-marker-{index}" for index, name in enumerate(names)}
    values["LOOKER_ALLOW_APPLY"] = "false"
    return values, [value for value in values.values() if value != "false"]


def test_access_packet_reports_names_without_any_environment_values(
    tmp_path: Path,
) -> None:
    environment, markers = _marked_environment()
    output = tmp_path / "access-request.md"

    result = write_looker_access_packet(
        output,
        campaign_id="ret-orders-live",
        environment=environment,
    )

    rendered = output.read_text(encoding="utf-8")
    serialized = json.dumps(result)
    for marker in markers:
        assert marker not in rendered
        assert marker not in serialized
    assert result["provisioning_allowed"] is False
    assert result["apply_control"] == "DISABLED"
    assert result["resume_command"] == (
        "retirement-conductor deployment preflight --profile looker-plan"
    )
    assert result["campaign_state_required_before_adapter_preflight"] is True
    assert {item["status"] for item in result["configuration"]} == {"CONFIGURED"}
    assert "PROVISIONING_ALLOWED=false" in rendered
    assert "This resume point does not assume a campaign already exists." in rendered
    assert "placeholder campaign or guess those identities" in rendered
    assert "There is intentionally no apply command" in rendered
    assert output.stat().st_mode & 0o777 == 0o600


def test_access_packet_cli_never_constructs_live_settings(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    marker = "recognizable-live-secret-value"
    monkeypatch.setenv("LOOKER_CLIENT_SECRET", marker)

    def unexpected_settings(*args: object, **kwargs: object) -> LookerSettings:
        raise AssertionError("access packet instantiated live Looker settings")

    monkeypatch.setattr(LookerSettings, "from_environment", unexpected_settings)
    output = tmp_path / "packet.md"
    exit_code = main(
        [
            "adapter",
            "looker",
            "access-packet",
            "--campaign",
            "ret-orders-live",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    stdout = capsys.readouterr().out
    assert marker not in stdout
    assert marker not in output.read_text(encoding="utf-8")
    assert json.loads(stdout)["result"] == "ACCESS_PACKET_WRITTEN"
