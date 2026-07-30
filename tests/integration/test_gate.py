from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from retirement_conductor.canonical import digest_json, with_digest, write_json
from retirement_conductor.errors import Refusal
from retirement_conductor.gate import (
    ProducerGateWorkflow,
    TrustedProducerContext,
)
from retirement_conductor.specification import load_specification
from retirement_conductor.store import CampaignStore

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN_ID = "ret-orders-legacy-status"
CONSUMER_ID = "consumer-dbt-order-summary"
PLAN_DIGEST = f"sha256:{'a' * 64}"
SOURCE_VERSION = "commit-one"
TARGETS = ["models/order_summary.sql"]
TRUSTED_NOW = datetime(2026, 1, 1, 11, 30, tzinfo=UTC)


def _envelope() -> dict[str, Any]:
    return with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": "2026-01-01T11:00:00Z",
            "mode": "live",
            "sources": [
                {
                    "id": "datahub",
                    "required": True,
                    "status": "COMPLETE",
                    "source_version": "fixture-live/1",
                }
            ],
        },
        "envelope_digest",
    )


def _approval(store: CampaignStore) -> dict[str, Any]:
    projection = store.projection(CAMPAIGN_ID)
    return with_digest(
        {
            "schema_version": "1.0.0",
            "approval_id": "gate-test-approval",
            "campaign_id": CAMPAIGN_ID,
            "plan_digest": PLAN_DIGEST,
            "source_version": SOURCE_VERSION,
            "targets": TARGETS,
            "principal": "fixture-operator",
            "scope": ["apply", "validate"],
            "authorization_digest": projection.input_digests["authorization"],
            "authorized_at": "2026-01-01T11:00:00Z",
            "expires_at": "2026-01-01T13:00:00Z",
        },
        "approval_digest",
    )


def _receipt() -> dict[str, Any]:
    value = json.loads(
        (ROOT / "artifacts/public/phase00/receipt.json").read_text(encoding="utf-8")
    )
    value["campaign_id"] = CAMPAIGN_ID
    value["consumer_id"] = CONSUMER_ID
    value["adapter"]["mode"] = "live"
    value["adapter"]["name"] = "git-dbt"
    value["apply"]["result"] = "APPLIED"
    value["apply"]["actual_targets"] = TARGETS
    value["plan"]["digest"] = PLAN_DIGEST
    value["source_before"]["version"] = SOURCE_VERSION
    value["captured_at"] = "2026-01-01T11:20:00Z"
    value["expires_at"] = "2026-01-01T13:00:00Z"
    return with_digest(value, "receipt_digest")


def _ready_store(
    tmp_path: Path,
    *,
    publication: bool = True,
) -> CampaignStore:
    store = CampaignStore(tmp_path / "campaign.sqlite", writer_id="writer-one")
    specification = load_specification(ROOT / "fixtures/specs/valid.yaml")
    store.create_campaign(
        specification,
        occurred_at="2026-01-01T10:00:00Z",
    )
    store.record_inventory(
        CAMPAIGN_ID,
        evidence_envelope=_envelope(),
        consumers=[
            {
                "id": CONSUMER_ID,
                "disposition": "IDENTIFIED",
                "receipt_digest": None,
            }
        ],
        snapshot_digest=f"sha256:{'1' * 64}",
        occurred_at="2026-01-01T10:10:00Z",
    )
    store.change_consumer_disposition(
        CAMPAIGN_ID,
        CONSUMER_ID,
        "CHANGE_PROPOSED",
        occurred_at="2026-01-01T10:20:00Z",
        idempotency_key="propose",
        plan_digest=PLAN_DIGEST,
        source_version=SOURCE_VERSION,
        approved_targets=TARGETS,
    )
    store.record_approval(
        CAMPAIGN_ID,
        _approval(store),
        plan_digest=PLAN_DIGEST,
        source_version=SOURCE_VERSION,
        targets=TARGETS,
        required_scope=["apply"],
        trusted_now=TRUSTED_NOW,
        occurred_at="2026-01-01T11:00:00Z",
        idempotency_key="approval",
    )
    store.begin_migration_with_claim(
        CAMPAIGN_ID,
        {
            "repository": "analytics",
            "commit": SOURCE_VERSION,
            "path": TARGETS[0],
        },
        plan_digest=PLAN_DIGEST,
        source_version=SOURCE_VERSION,
        targets=TARGETS,
        required_scope=["apply"],
        trusted_now=TRUSTED_NOW,
        occurred_at="2026-01-01T11:10:00Z",
    )
    store.change_consumer_disposition(
        CAMPAIGN_ID,
        CONSUMER_ID,
        "APPLIED",
        occurred_at="2026-01-01T11:15:00Z",
        idempotency_key="applied",
    )
    store.accept_receipt(
        CAMPAIGN_ID,
        CONSUMER_ID,
        _receipt(),
        trusted_now=TRUSTED_NOW,
        occurred_at="2026-01-01T11:30:00Z",
        idempotency_key="receipt",
    )
    comparison = with_digest(
        {
            "schema_version": "1.0.0",
            "campaign_id": CAMPAIGN_ID,
            "captured_at": "2026-01-01T11:40:00Z",
        },
        "comparison_digest",
    )
    comparison_root = tmp_path / "artifacts" / CAMPAIGN_ID / "reconciliation"
    write_json(comparison_root / "comparison.json", comparison)
    store.record_reconciliation(
        CAMPAIGN_ID,
        evidence_envelope=_envelope(),
        consumer_ids=[CONSUMER_ID],
        comparison={"comparison_digest": comparison["comparison_digest"]},
        snapshot_digest=f"sha256:{'2' * 64}",
        occurred_at="2026-01-01T11:40:00Z",
    )
    ready = store.evaluate(
        CAMPAIGN_ID,
        occurred_at="2026-01-01T11:45:00Z",
    )
    assert ready["decision"] == "READY_TO_RETIRE"
    if publication:
        content_digest = f"sha256:{'3' * 64}"
        lifecycle_digest = f"sha256:{'4' * 64}"
        store.record_publication(
            CAMPAIGN_ID,
            {
                "logical_key": f"campaign/{CAMPAIGN_ID}",
                "urn": "urn:li:document:gate-test",
                "content_digest": content_digest,
                "published_manifest_digest": ready["manifest_digest"],
                "lifecycle_digest_before": lifecycle_digest,
                "readback_verified": False,
            },
            occurred_at="2026-01-01T11:50:00Z",
            idempotency_key="publication",
        )
        store.verify_publication(
            CAMPAIGN_ID,
            {
                "urn": "urn:li:document:gate-test",
                "content_digest": content_digest,
                "lifecycle_digest_after": lifecycle_digest,
                "readback_artifact_id": f"sha256:{'5' * 64}",
                "verified_at": "2026-01-01T11:55:00Z",
            },
            occurred_at="2026-01-01T11:55:00Z",
            idempotency_key="publication-verify",
        )
    return store


def _context(
    *,
    run_id: str = "trusted-run-one",
    trusted: bool = True,
) -> TrustedProducerContext:
    return TrustedProducerContext(
        run_id=run_id,
        provider="fixture-ci",
        trusted=trusted,
    )


def _plan(
    store: CampaignStore,
    tmp_path: Path,
    *,
    publication: bool = True,
) -> dict[str, Any]:
    manifest = store.materialize(CAMPAIGN_ID)
    projection = store.projection(CAMPAIGN_ID)
    publication_value = manifest.get("publication") if publication else None
    publication_content_digest = (
        publication_value["content_digest"]
        if isinstance(publication_value, dict)
        else f"sha256:{'3' * 64}"
    )
    published_manifest_digest = (
        publication_value["published_manifest_digest"]
        if isinstance(publication_value, dict)
        else manifest["manifest_digest"]
    )
    common_digest = f"sha256:{'6' * 64}"
    plan = with_digest(
        {
            "schema_version": "1.0.0",
            "campaign_id": CAMPAIGN_ID,
            "prepared_at": "2026-01-01T12:00:00Z",
            "expires_at": "2026-01-01T12:10:00Z",
            "writer_id": "writer-one",
            "trusted_run": {
                "id": "trusted-run-one",
                "provider": "fixture-ci",
            },
            "manifest": {
                "digest": manifest["manifest_digest"],
                "decision": manifest["decision"],
                "specification_digest": manifest["specification_digest"],
                "evidence_envelope_digest": manifest["evidence_envelope"][
                    "envelope_digest"
                ],
                "reconciliation_digest": projection.reconciliations[-1][
                    "comparison_digest"
                ],
                "publication_content_digest": publication_content_digest,
                "published_manifest_digest": published_manifest_digest,
                "input_digests": dict(projection.input_digests),
                "receipt_digests": list(manifest["receipt_digests"]),
            },
            "producer_source": {
                "repository_identity": common_digest,
                "remote_identity": common_digest,
                "branch": "main",
                "version": "producer-commit-one",
                "working_tree_clean": True,
                "marker_path": "fixtures/producer.json",
                "marker_digest": common_digest,
            },
            "git_dbt": {
                "settings_digest": common_digest,
                "preflight_digest": common_digest,
                "migration_plan_digest": common_digest,
                "apply_digest": common_digest,
                "validation_digest": common_digest,
                "receipt_digest": common_digest,
                "validator_binding_digest": common_digest,
                "artifact_set_digest": common_digest,
            },
            "action": {
                "type": "write_public_safe_sentinel",
                "action_id": "producer-sentinel-one",
                "sentinel_root_identity": digest_json(str(tmp_path / "sentinels")),
                "relative_path": f"{CAMPAIGN_ID}/trusted-run-one.json",
            },
            "limitations": ["Public-safe fixture sentinel only."],
        },
        "plan_digest",
    )
    store.issue_gate_plan(plan)
    return plan


def _workflow(
    store: CampaignStore,
    tmp_path: Path,
) -> ProducerGateWorkflow:
    return ProducerGateWorkflow(
        store=store,
        artifact_directory=tmp_path / "artifacts",
        producer_repository_root=tmp_path,
        producer_source_marker=tmp_path / "producer.json",
        sentinel_root=tmp_path / "sentinels",
        boundary=None,
        git_dbt=None,
    )


def _stub_verification() -> dict[str, str]:
    return {
        "datahub_snapshot_digest": f"sha256:{'7' * 64}",
        "source_reconciliation_digest": f"sha256:{'8' * 64}",
        "publication_readback_artifact_id": f"sha256:{'9' * 64}",
    }


def test_gate_accepts_digest_bound_stored_specification(tmp_path: Path) -> None:
    with _ready_store(tmp_path) as store:
        workflow = _workflow(store, tmp_path)
        projection = store.projection(CAMPAIGN_ID)

        workflow._verify_campaign_inputs(
            CAMPAIGN_ID,
            projection.input_digests,
        )


def test_gate_executes_one_sentinel_and_refuses_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _ready_store(tmp_path) as store:
        workflow = _workflow(store, tmp_path)
        plan = _plan(store, tmp_path)
        plan_path = tmp_path / "producer-plan.json"
        write_json(plan_path, plan)
        monkeypatch.setattr(
            workflow, "_producer_source", lambda: plan["producer_source"]
        )
        monkeypatch.setattr(
            workflow,
            "_verify_ready_state",
            lambda *_args, **_kwargs: _stub_verification(),
        )

        result = workflow.execute(
            CAMPAIGN_ID,
            context=_context(),
            plan_path=plan_path,
            executed_at="2026-01-01T12:05:00Z",
        )

        sentinel = tmp_path / "sentinels" / plan["action"]["relative_path"]
        assert result["decision"] == "READY_TO_RETIRE"
        assert result["manifest_digest"] == plan["manifest"]["digest"]
        assert sentinel.is_file()
        assert len(list((tmp_path / "sentinels").rglob("*.json"))) == 1
        assert store.gate_attempts(CAMPAIGN_ID)[0]["status"] == "EXECUTED"

        with pytest.raises(Refusal, match="GATE_PLAN_REPLAYED"):
            workflow.execute(
                CAMPAIGN_ID,
                context=_context(),
                plan_path=plan_path,
                executed_at="2026-01-01T12:06:00Z",
            )
        assert len(list((tmp_path / "sentinels").rglob("*.json"))) == 1


@pytest.mark.parametrize(
    ("context", "executed_at", "expected_code"),
    [
        (_context(trusted=False), "2026-01-01T12:05:00Z", "GATE_PROVENANCE_UNTRUSTED"),
        (
            _context(run_id="different-run"),
            "2026-01-01T12:05:00Z",
            "GATE_PROVENANCE_UNTRUSTED",
        ),
        (_context(), "2026-01-01T12:10:00Z", "GATE_PLAN_EXPIRED"),
    ],
)
def test_gate_refuses_untrusted_wrong_run_and_delayed_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    context: TrustedProducerContext,
    executed_at: str,
    expected_code: str,
) -> None:
    with _ready_store(tmp_path) as store:
        workflow = _workflow(store, tmp_path)
        plan = _plan(store, tmp_path)
        plan_path = tmp_path / "producer-plan.json"
        write_json(plan_path, plan)
        monkeypatch.setattr(
            workflow, "_producer_source", lambda: plan["producer_source"]
        )
        monkeypatch.setattr(
            workflow,
            "_verify_ready_state",
            lambda *_args, **_kwargs: _stub_verification(),
        )

        with pytest.raises(Refusal, match=expected_code):
            workflow.execute(
                CAMPAIGN_ID,
                context=context,
                plan_path=plan_path,
                executed_at=executed_at,
            )

        assert not (tmp_path / "sentinels").exists()
        assert store.gate_attempts(CAMPAIGN_ID)[-1]["status"] == "REFUSED"


def test_gate_refuses_source_drift_and_tampered_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _ready_store(tmp_path) as store:
        workflow = _workflow(store, tmp_path)
        plan = _plan(store, tmp_path)
        plan_path = tmp_path / "producer-plan.json"
        write_json(plan_path, plan)
        monkeypatch.setattr(
            workflow,
            "_verify_ready_state",
            lambda *_args, **_kwargs: _stub_verification(),
        )
        changed_source = {**plan["producer_source"], "version": "changed"}
        monkeypatch.setattr(workflow, "_producer_source", lambda: changed_source)

        with pytest.raises(Refusal, match="GATE_SOURCE_DRIFT"):
            workflow.execute(
                CAMPAIGN_ID,
                context=_context(),
                plan_path=plan_path,
                executed_at="2026-01-01T12:05:00Z",
            )

        tampered = {**plan, "writer_id": "other-writer"}
        write_json(plan_path, tampered)
        with pytest.raises(Refusal, match="INTEGRITY_DIGEST_MISMATCH"):
            workflow.execute(
                CAMPAIGN_ID,
                context=_context(),
                plan_path=plan_path,
                executed_at="2026-01-01T12:06:00Z",
            )
        assert not (tmp_path / "sentinels").exists()


def test_gate_refuses_recomputed_but_unissued_plan(
    tmp_path: Path,
) -> None:
    with _ready_store(tmp_path) as store:
        workflow = _workflow(store, tmp_path)
        issued = _plan(store, tmp_path)
        changed = deepcopy(issued)
        changed["action"]["action_id"] = "different-producer-action"
        changed["action"]["relative_path"] = (
            f"{CAMPAIGN_ID}/different-producer-action.json"
        )
        changed.pop("plan_digest")
        changed = with_digest(changed, "plan_digest")
        plan_path = tmp_path / "producer-plan.json"
        write_json(plan_path, changed)

        with pytest.raises(Refusal, match="GATE_PLAN_INVALID"):
            workflow.execute(
                CAMPAIGN_ID,
                context=_context(),
                plan_path=plan_path,
                executed_at="2026-01-01T12:05:00Z",
            )
        assert not (tmp_path / "sentinels").exists()


def test_gate_marks_failed_action_unknown_and_consumes_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _ready_store(tmp_path) as store:
        workflow = _workflow(store, tmp_path)
        plan = _plan(store, tmp_path)
        plan_path = tmp_path / "producer-plan.json"
        write_json(plan_path, plan)
        monkeypatch.setattr(
            workflow, "_producer_source", lambda: plan["producer_source"]
        )
        monkeypatch.setattr(
            workflow,
            "_verify_ready_state",
            lambda *_args, **_kwargs: _stub_verification(),
        )

        def fail_write(_path: Path, _value: dict[str, Any]) -> None:
            raise OSError("controlled failure")

        monkeypatch.setattr(workflow, "_write_new_sentinel", fail_write)
        with pytest.raises(Refusal, match="GATE_ACTION_OUTCOME_UNKNOWN"):
            workflow.execute(
                CAMPAIGN_ID,
                context=_context(),
                plan_path=plan_path,
                executed_at="2026-01-01T12:05:00Z",
            )

        assert store.gate_attempts(CAMPAIGN_ID)[0]["status"] == "OUTCOME_UNKNOWN"
        with pytest.raises(Refusal, match="GATE_PLAN_REPLAYED"):
            store.claim_gate_plan(
                CAMPAIGN_ID,
                manifest_digest=str(plan["manifest"]["digest"]),
                decision="READY_TO_RETIRE",
                plan_digest=str(plan["plan_digest"]),
                trusted_run_id="trusted-run-one",
                recorded_at="2026-01-01T12:06:00Z",
            )


def test_gate_refuses_ready_campaign_without_verified_publication(
    tmp_path: Path,
) -> None:
    with _ready_store(tmp_path, publication=False) as store:
        workflow = _workflow(store, tmp_path)
        plan = _plan(store, tmp_path, publication=False)
        plan_path = tmp_path / "producer-plan.json"
        write_json(plan_path, plan)

        with pytest.raises(Refusal, match="GATE_PUBLICATION_UNVERIFIED"):
            workflow.execute(
                CAMPAIGN_ID,
                context=_context(),
                plan_path=plan_path,
                executed_at="2026-01-01T12:05:00Z",
            )
        assert not (tmp_path / "sentinels").exists()
