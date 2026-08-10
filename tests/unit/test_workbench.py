from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import Event, Thread
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

import retirement_conductor.workbench_server as workbench_server
from retirement_conductor.errors import Refusal
from retirement_conductor.workbench import build_workbench_view
from retirement_conductor.workbench_server import (
    WorkbenchApplication,
    create_workbench_server,
    serve_workbench,
)

ROOT = Path(__file__).resolve().parents[2]
LATE = ROOT / "artifacts/public/phase04/late-manifest.json"
PAIRING_TOKEN = "test-pairing-token-that-is-longer-than-thirty-two-characters"


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
        next(stage for stage in view["stages"] if stage["key"] == "retire")["status"]
        == "blocked"
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


def test_workbench_allows_only_one_runtime_action_at_a_time(tmp_path: Path) -> None:
    started = Event()
    release = Event()

    def runner(_operation: str) -> dict[str, Any]:
        started.set()
        release.wait(timeout=2)
        return {"command_exit_code": 1, "message": "expected test stop"}

    application = WorkbenchApplication(
        store=tmp_path / "unused.sqlite",
        writer_id="workbench-test",
        campaign_id="campaign-one",
        actions_enabled=True,
        action_runner=runner,
    )

    def run_first() -> None:
        with pytest.raises(Refusal, match="expected test stop"):
            application.run("inventory")

    first = Thread(target=run_first)
    first.start()
    assert started.wait(timeout=2)
    try:
        with pytest.raises(Refusal, match="still running") as refusal:
            application.run("reconcile")
        assert refusal.value.code == "RUNTIME_OPERATION_IN_PROGRESS"
    finally:
        release.set()
        first.join(timeout=2)


def test_workbench_maps_sqlite_contention_to_stable_refusal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def locked_store(*_args: object, **_kwargs: object) -> None:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(workbench_server, "CampaignStore", locked_store)
    application = WorkbenchApplication(
        store=tmp_path / "campaign.sqlite",
        writer_id="workbench-test",
        campaign_id="campaign-one",
        actions_enabled=False,
        action_runner=lambda _operation: {"result": "SHOULD_NOT_RUN"},
    )

    with pytest.raises(Refusal, match="temporarily unavailable") as refusal:
        application.view()

    assert refusal.value.code == "RUNTIME_STORE_LOCKED"


@pytest.mark.parametrize(
    ("host", "origin"),
    [
        ("0.0.0.0", "http://localhost:3000"),
        ("127.0.0.1", "http://operator.example.com"),
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
            pairing_token=PAIRING_TOKEN,
        )


def test_workbench_server_accepts_explicit_https_origin(tmp_path: Path) -> None:
    application = WorkbenchApplication(
        store=tmp_path / "unused.sqlite",
        writer_id="workbench-test",
        campaign_id="campaign-one",
        actions_enabled=False,
        action_runner=lambda _operation: {"result": "SHOULD_NOT_RUN"},
    )

    server = create_workbench_server(
        application,
        host="127.0.0.1",
        port=0,
        allowed_origins=["https://operator.example.com"],
        pairing_token=PAIRING_TOKEN,
    )
    server.server_close()


def test_workbench_server_requires_pairing_and_supports_private_network_preflight(
    tmp_path: Path,
) -> None:
    origin = "https://operator.example.com"
    application = WorkbenchApplication(
        store=tmp_path / "unused.sqlite",
        writer_id="workbench-test",
        campaign_id="campaign-one",
        actions_enabled=False,
        action_runner=lambda _operation: {"result": "SHOULD_NOT_RUN"},
    )
    server = create_workbench_server(
        application,
        host="127.0.0.1",
        port=0,
        allowed_origins=[origin],
        pairing_token=PAIRING_TOKEN,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        with pytest.raises(HTTPError) as unauthorized:
            urlopen(
                Request(f"{base_url}/api/health", headers={"Origin": origin}),
                timeout=2,
            )
        assert unauthorized.value.code == 401

        with urlopen(
            Request(
                f"{base_url}/api/health",
                headers={
                    "Authorization": f"Bearer {PAIRING_TOKEN}",
                    "Origin": origin,
                },
            ),
            timeout=2,
        ) as response:
            payload = json.loads(response.read())
            assert payload["authentication"] == "paired-token"
            assert response.headers["Access-Control-Allow-Origin"] == origin

        with urlopen(
            Request(
                f"{base_url}/api/health",
                method="OPTIONS",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "authorization",
                    "Access-Control-Request-Private-Network": "true",
                },
            ),
            timeout=2,
        ) as response:
            assert response.status == 204
            assert response.headers["Access-Control-Allow-Private-Network"] == "true"
            assert "Authorization" in response.headers["Access-Control-Allow-Headers"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
