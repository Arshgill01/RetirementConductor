from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from retirement_conductor.errors import Refusal
from retirement_conductor.workbench import build_workbench_view
from retirement_conductor.workbench_server import WorkbenchApplication, serve_workbench

ROOT = Path(__file__).resolve().parents[2]
LATE = ROOT / "artifacts/public/phase04/late-manifest.json"


def _late_manifest() -> dict[str, Any]:
    value = json.loads(LATE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _events(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    events = [
        {
            **item,
            "occurred_at": f"2026-07-30T12:{index:02d}:00Z",
            "payload": {},
        }
        for index, item in enumerate(manifest["transition_history"], start=1)
    ]
    proposed = next(
        event
        for event in events
        if event["event_type"] == "CONSUMER_DISPOSITION_CHANGED"
    )
    proposed["payload"] = {
        "disposition": "CHANGE_PROPOSED",
        "approved_targets": ["models/orders_isolated_model.sql"],
    }
    receipt = next(
        event for event in events if event["event_type"] == "RECEIPT_ACCEPTED"
    )
    receipt["payload"] = {
        "consumer_id": manifest["consumers"][0]["id"],
        "accepted_at": receipt["occurred_at"],
        "receipt": {
            "receipt_digest": manifest["consumers"][0]["receipt_digest"],
            "adapter": {"name": "git-dbt"},
            "apply": {"result": "APPLIED"},
        },
    }
    reconciliations = [
        event for event in events if event["event_type"] == "RECONCILIATION_RECORDED"
    ]
    reconciliations[-1]["payload"] = {
        "comparison": {"added": [manifest["consumers"][1]["id"]]}
    }
    decisions = [event for event in events if event["event_type"] == "POLICY_EVALUATED"]
    decisions[0]["payload"] = {"decision": "READY_TO_RETIRE"}
    decisions[-1]["payload"] = {"decision": "UNSAFE"}
    return events


def test_workbench_distills_late_consumer_without_inventing_identity() -> None:
    manifest = _late_manifest()
    view = build_workbench_view(
        manifest,
        _events(manifest),
        actions_enabled=True,
    )

    assert view["summary"] == {
        "headline": "A new consumer changed the answer.",
        "cause": "A consumer appeared after the frozen inventory.",
    }
    assert view["new_consumer_ids"] == [manifest["consumers"][1]["id"]]
    assert view["primary_action"]["label"] == "Review new consumer"
    assert view["primary_action"]["kind"] == "navigate"
    assert (
        next(stage for stage in view["stages"] if stage["key"] == "reconcile")["status"]
        == "current"
    )
    assert (
        next(stage for stage in view["stages"] if stage["key"] == "lease")["status"]
        == "invalidated"
    )
    assert view["change"]["paths"] == ["models/orders_isolated_model.sql"]
    assert view["change"]["receipt"]["adapter"] == "git-dbt"
    assert "Spark" not in json.dumps(view)


def test_workbench_rejects_event_stream_that_does_not_match_manifest() -> None:
    manifest = _late_manifest()
    events = _events(manifest)
    events.pop()

    with pytest.raises(ValueError, match="canonical manifest history"):
        build_workbench_view(manifest, events, actions_enabled=False)


def test_read_only_workbench_refuses_runtime_action(tmp_path: Path) -> None:
    application = WorkbenchApplication(
        store=tmp_path / "unused.sqlite",
        writer_id="workbench-test",
        campaign_id="campaign-one",
        actions_enabled=False,
        action_runner=lambda _operation: {"result": "SHOULD_NOT_RUN"},
    )

    with pytest.raises(Refusal, match="not enabled") as refusal:
        application.run("reconcile")

    assert refusal.value.code == "AUTH_APPROVAL_MISSING"


def test_workbench_refuses_operations_outside_inventory_and_reconcile(
    tmp_path: Path,
) -> None:
    application = WorkbenchApplication(
        store=tmp_path / "unused.sqlite",
        writer_id="workbench-test",
        campaign_id="campaign-one",
        actions_enabled=True,
        action_runner=lambda _operation: {"result": "SHOULD_NOT_RUN"},
    )

    with pytest.raises(Refusal, match="only inventory and reconciliation") as refusal:
        application.run("authorize")

    assert refusal.value.code == "SCOPE_TARGET_NOT_ALLOWED"


@pytest.mark.parametrize(
    ("host", "origin"),
    [
        ("0.0.0.0", "http://localhost:3000"),
        ("127.0.0.1", "https://operator.example.com"),
    ],
)
def test_workbench_server_refuses_non_loopback_exposure(
    tmp_path: Path,
    host: str,
    origin: str,
) -> None:
    application = WorkbenchApplication(
        store=tmp_path / "unused.sqlite",
        writer_id="workbench-test",
        campaign_id="campaign-one",
        actions_enabled=False,
        action_runner=lambda _operation: {"result": "SHOULD_NOT_RUN"},
    )

    with pytest.raises(Refusal, match=r"loopback|127\.0\.0\.1"):
        serve_workbench(
            application,
            host=host,
            port=0,
            allowed_origins=[origin],
        )
