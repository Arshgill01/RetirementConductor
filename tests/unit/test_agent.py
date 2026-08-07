from __future__ import annotations

import json
from pathlib import Path

import pytest

from retirement_conductor.agent import AgentCommandRuntime, AgentSettings
from retirement_conductor.canonical import write_json

ROOT = Path(__file__).resolve().parents[2]


def _runtime(tmp_path: Path) -> AgentCommandRuntime:
    return AgentCommandRuntime(
        AgentSettings(
            store=tmp_path / "campaigns.sqlite",
            writer_id="agent-test-writer",
            artifact_directory=tmp_path / "artifacts",
            specification_root=ROOT / "fixtures" / "specs",
            refresh_receipt=tmp_path / "refresh.json",
            indexing_timeout_seconds=1,
        )
    )


def test_agent_runtime_creates_and_inspects_campaign(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)

    created = runtime.create_campaign(
        "valid.yaml",
        occurred_at="2026-08-07T00:00:00Z",
    )
    inspected = runtime.inspect_campaign("ret-orders-legacy-status")
    explained = runtime.explain_campaign("ret-orders-legacy-status")

    assert created["command_exit_code"] == 0
    assert created["manifest"]["decision"] == "BLOCKED"
    assert inspected["command_exit_code"] == 0
    assert inspected["view"]["decision"] == "BLOCKED"
    assert explained["command_exit_code"] == 0
    assert "BLOCKED" in explained["explanation"]


def test_agent_runtime_rejects_path_and_identifier_escape(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)

    with pytest.raises(ValueError, match="specification must remain inside"):
        runtime.create_campaign(
            "../../README.md",
            occurred_at="2026-08-07T00:00:00Z",
        )

    with pytest.raises(ValueError, match="campaign_id must contain"):
        runtime.inspect_campaign("../../campaign")


def test_authorization_instructions_cannot_record_approval(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    plan_path = (
        tmp_path / "artifacts" / "ret-orders-legacy-status" / "git-dbt" / "plan.json"
    )
    write_json(
        plan_path,
        {
            "plan_digest": "sha256:" + ("a" * 64),
            "target": {"path": "models/orders.sql"},
        },
    )

    result = runtime.approval_instructions(
        "ret-orders-legacy-status",
        authorized_at="2026-08-07T00:00:00Z",
        expires_at="2026-08-07T00:15:00Z",
    )

    assert result["result"] == "HUMAN_AUTHORIZATION_REQUIRED"
    assert result["authorized_targets"] == ["models/orders.sql"]
    assert result["command_argv"][:4] == [
        "retirement-conductor",
        "adapter",
        "git-dbt",
        "authorize",
    ]
    assert not runtime.settings.store.exists()
    assert json.loads(plan_path.read_text(encoding="utf-8"))["plan_digest"] == (
        "sha256:" + ("a" * 64)
    )
