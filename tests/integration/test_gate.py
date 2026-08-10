from __future__ import annotations

import json
from collections.abc import Mapping
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
from retirement_conductor.postgres_producer import (
    POSTGRES_LEGACY_COLUMN_MISSING,
    MutationTransportLost,
    PostgresActionOutcome,
    PostgresProducerAction,
    normalize_observation,
)
from retirement_conductor.postgres_producer_config import (
    PostgresConnectionSettings,
    PostgresProducerSettings,
    PostgresTarget,
)
from retirement_conductor.schemas import validate_schema
from retirement_conductor.specification import load_specification
from retirement_conductor.store import CampaignStore
from retirement_conductor.superset_config import SupersetSettings
from retirement_conductor.superset_gate import SupersetGateVerifier

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
    issue: bool = True,
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
    if issue:
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


def test_fresh_retire_prepares_and_executes_inside_one_invocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _ready_store(tmp_path) as store:
        workflow = _workflow(store, tmp_path)
        calls: list[tuple[str, dict[str, Any]]] = []

        def prepare(
            campaign_id: str,
            **kwargs: Any,
        ) -> dict[str, Any]:
            calls.append(("prepare", {"campaign_id": campaign_id, **kwargs}))
            return {"plan": {"plan_digest": f"sha256:{'a' * 64}"}}

        def execute(
            campaign_id: str,
            **kwargs: Any,
        ) -> dict[str, Any]:
            calls.append(("execute", {"campaign_id": campaign_id, **kwargs}))
            return {
                "result": "EXECUTED",
                "decision": "READY_TO_RETIRE",
                "manifest_digest": f"sha256:{'b' * 64}",
                "gate_receipt": {"receipt_digest": f"sha256:{'c' * 64}"},
            }

        times = iter(("2026-01-01T12:00:00Z", "2026-01-01T12:00:01Z"))
        monkeypatch.setattr("retirement_conductor.gate.utc_now", lambda: next(times))
        monkeypatch.setattr(workflow, "prepare", prepare)
        monkeypatch.setattr(workflow, "execute", execute)

        result = workflow.retire(
            CAMPAIGN_ID,
            context=_context(),
            action_type="write_public_safe_sentinel",
        )

        assert result["result"] == "EXECUTED"
        assert result["operation"] == "FRESH_CHECK_AND_RETIRE"
        assert result["producer_plan_digest"] == f"sha256:{'a' * 64}"
        assert result["internal_plan_reused"] is False
        assert [name for name, _details in calls] == ["prepare", "execute"]
        assert calls[0][1]["prepared_at"] == "2026-01-01T12:00:00Z"
        assert calls[0][1]["expires_at"] == "2026-01-01T12:05:00Z"
        assert calls[1][1]["executed_at"] == "2026-01-01T12:00:01Z"


def test_fresh_retire_refuses_an_invalid_internal_window(tmp_path: Path) -> None:
    with _ready_store(tmp_path) as store:
        workflow = _workflow(store, tmp_path)

        with pytest.raises(Refusal, match="GATE_PLAN_INVALID"):
            workflow.retire(
                CAMPAIGN_ID,
                context=_context(),
                action_type="write_public_safe_sentinel",
                plan_lifetime_seconds=901,
            )


def test_fresh_retire_reuses_an_unconsumed_internal_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _ready_store(tmp_path) as store:
        workflow = _workflow(store, tmp_path)
        plan = _plan(store, tmp_path)

        def unexpected_prepare(*_args: object, **_kwargs: object) -> None:
            pytest.fail("an existing plan for the same manifest must be reused")

        def execute(
            campaign_id: str,
            **kwargs: Any,
        ) -> dict[str, Any]:
            assert campaign_id == CAMPAIGN_ID
            assert kwargs["executed_at"] == "2026-01-01T12:05:00Z"
            return {
                "result": "EXECUTED",
                "decision": "READY_TO_RETIRE",
                "manifest_digest": plan["manifest"]["digest"],
                "gate_receipt": {"receipt_digest": f"sha256:{'c' * 64}"},
            }

        monkeypatch.setattr(workflow, "prepare", unexpected_prepare)
        monkeypatch.setattr(workflow, "execute", execute)
        monkeypatch.setattr(
            "retirement_conductor.gate.utc_now",
            lambda: "2026-01-01T12:05:00Z",
        )

        result = workflow.retire(
            CAMPAIGN_ID,
            context=_context(),
            action_type="write_public_safe_sentinel",
        )

        assert result["internal_plan_reused"] is True
        assert result["producer_plan_digest"] == plan["plan_digest"]
        persisted = json.loads(
            (tmp_path / "artifacts" / CAMPAIGN_ID / "producer" / "plan.json").read_text(
                encoding="utf-8"
            )
        )
        assert persisted == plan


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


POSTGRES_TARGET = PostgresTarget(
    database="gate_test",
    schema="retirement_lab",
    table="orders",
    legacy_column="legacy_status",
    replacement_column="order_status",
)


def _postgres_raw(
    principal: str,
    *,
    can_alter: bool,
    legacy_present: bool = True,
) -> dict[str, Any]:
    columns = [
        {
            "position": 1,
            "name": "order_id",
            "type_oid": 20,
            "type_modifier": -1,
            "formatted_type": "bigint",
            "not_null": True,
            "default_expression": None,
            "identity_kind": "",
            "generated_kind": "",
        }
    ]
    if legacy_present:
        columns.append(
            {
                "position": 2,
                "name": "legacy_status",
                "type_oid": 25,
                "type_modifier": -1,
                "formatted_type": "text",
                "not_null": True,
                "default_expression": None,
                "identity_kind": "",
                "generated_kind": "",
            }
        )
    columns.append(
        {
            "position": 3,
            "name": "order_status",
            "type_oid": 25,
            "type_modifier": -1,
            "formatted_type": "text",
            "not_null": True,
            "default_expression": None,
            "identity_kind": "",
            "generated_kind": "",
        }
    )
    return {
        "database": {
            "name": POSTGRES_TARGET.database,
            "oid": 5,
            "server_version": "16.10",
            "server_version_num": "160010",
        },
        "principal": {
            "session_user": principal,
            "current_user": principal,
            "table_owner": "gate_mutator",
            "can_alter_table": can_alter,
        },
        "table": {
            "relation_oid": 20,
            "schema_oid": 10,
            "columns": columns,
            "legacy_dependencies": [],
        },
    }


class _GatePostgresClient:
    def __init__(
        self,
        principal: str,
        *,
        can_alter: bool,
        behavior: str = "commit",
    ) -> None:
        self.connection = PostgresConnectionSettings(
            host="127.0.0.1",
            port=25432,
            database=POSTGRES_TARGET.database,
            username=principal,
            password="runtime-only",
            connect_timeout_seconds=5,
            lock_timeout_seconds=5,
        )
        self.current = normalize_observation(
            _postgres_raw(principal, can_alter=can_alter),
            POSTGRES_TARGET,
        )
        self.behavior = behavior
        self.execute_calls = 0
        self.mirror: _GatePostgresClient | None = None
        self.unavailable = False

    def observe(self, target: PostgresTarget) -> dict[str, Any]:
        assert target == POSTGRES_TARGET
        if self.unavailable:
            raise Refusal("POSTGRES_CONNECTION_UNAVAILABLE", "controlled outage")
        return deepcopy(self.current)

    def execute_drop(self, _plan: Mapping[str, Any]) -> dict[str, Any]:
        self.execute_calls += 1
        absent = normalize_observation(
            _postgres_raw(
                self.connection.username,
                can_alter=True,
                legacy_present=False,
            ),
            POSTGRES_TARGET,
        )
        self.current = absent
        if self.mirror is not None:
            self.mirror.current = deepcopy(absent)
            if self.behavior == "lost-response":
                self.mirror.unavailable = True
        if self.behavior == "lost-response":
            raise MutationTransportLost("after_intent")
        return {
            "destructive_statements_attempted": 1,
            "destructive_statements_committed": 1,
        }


def _postgres_settings() -> PostgresProducerSettings:
    return PostgresProducerSettings(
        host="127.0.0.1",
        port=25432,
        database=POSTGRES_TARGET.database,
        observer_username="gate_observer",
        observer_password="runtime-only",
        mutation_username="gate_mutator",
        mutation_password="runtime-only",
        allow_apply=True,
        allowed_targets=(POSTGRES_TARGET,),
    )


def _postgres_plan(
    store: CampaignStore,
    tmp_path: Path,
    action: PostgresProducerAction,
) -> dict[str, Any]:
    base = deepcopy(_plan(store, tmp_path, issue=False))
    native = action.plan(
        action.observe(POSTGRES_TARGET),
        actions=[POSTGRES_TARGET],
        action_expires_at="2026-01-01T12:10:00Z",
    )
    base["schema_version"] = "2.0.0"
    base["superset"] = []
    base["action"] = {
        "type": "postgres_drop_column_v1",
        "action_id": "postgres-action-one",
        "action_digest": native["action_digest"],
        "postgres_action_plan": native,
    }
    base["limitations"] = ["Disposable PostgreSQL fixture action only."]
    base.pop("plan_digest")
    value = with_digest(base, "plan_digest")
    validate_schema("producer-plan-v2", value)
    store.issue_gate_plan(value)
    return value


def _postgres_verification() -> dict[str, Any]:
    return with_digest(
        {
            "datahub_snapshot_digest": f"sha256:{'7' * 64}",
            "git_dbt_reconciliation_digest": f"sha256:{'8' * 64}",
            "superset_observations": [],
            "producer_schema_observation_digest": f"sha256:{'a' * 64}",
            "publication_readback_artifact_id": f"sha256:{'9' * 64}",
        },
        "verification_digest",
    )


def _postgres_workflow(
    store: CampaignStore,
    tmp_path: Path,
    action: PostgresProducerAction,
    factory: Any,
) -> ProducerGateWorkflow:
    return ProducerGateWorkflow(
        store=store,
        artifact_directory=tmp_path / "artifacts",
        producer_repository_root=tmp_path,
        producer_source_marker=tmp_path / "producer.json",
        sentinel_root=tmp_path / "sentinels",
        boundary=None,
        git_dbt=None,
        postgres_action=action,
        postgres_target=POSTGRES_TARGET,
        mutation_client_factory=factory,
    )


def test_postgres_gate_claims_intent_before_one_action_and_refuses_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _ready_store(tmp_path) as store:
        observer = _GatePostgresClient("gate_observer", can_alter=False)
        action = PostgresProducerAction(_postgres_settings(), observer)
        mutator = _GatePostgresClient("gate_mutator", can_alter=True)
        mutator.mirror = observer
        factory_calls = 0

        def mutation_factory() -> _GatePostgresClient:
            nonlocal factory_calls
            factory_calls += 1
            assert store.gate_attempts(CAMPAIGN_ID)[-1]["status"] == "INTENT_RECORDED"
            return mutator

        workflow = _postgres_workflow(store, tmp_path, action, mutation_factory)
        plan = _postgres_plan(store, tmp_path, action)
        plan_path = tmp_path / "postgres-plan.json"
        write_json(plan_path, plan)
        monkeypatch.setattr(
            workflow, "_producer_source", lambda: plan["producer_source"]
        )
        verification_calls = 0

        def verify_once(*_args: object, **_kwargs: object) -> dict[str, object]:
            nonlocal verification_calls
            verification_calls += 1
            if verification_calls > 1:
                raise Refusal(
                    POSTGRES_LEGACY_COLUMN_MISSING,
                    "the committed action changed native state",
                )
            return _postgres_verification()

        monkeypatch.setattr(workflow, "_verify_ready_state", verify_once)

        result = workflow.execute(
            CAMPAIGN_ID,
            context=_context(),
            plan_path=plan_path,
            executed_at="2026-01-01T12:05:00Z",
        )

        assert result["result"] == "EXECUTED"
        assert result["gate_receipt"]["action"]["result"] == "COMMITTED"
        assert result["gate_receipt"]["action"]["legacy_column_present"] is False
        assert mutator.execute_calls == 1
        assert factory_calls == 1
        assert verification_calls == 1
        assert store.gate_attempts(CAMPAIGN_ID)[-1]["status"] == "EXECUTED"
        with pytest.raises(Refusal, match="GATE_PLAN_REPLAYED"):
            workflow.execute(
                CAMPAIGN_ID,
                context=_context(),
                plan_path=plan_path,
                executed_at="2026-01-01T12:06:00Z",
            )
        assert mutator.execute_calls == 1
        assert factory_calls == 1


def test_postgres_gate_closes_pre_execution_failure_without_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _ready_store(tmp_path) as store:
        observer = _GatePostgresClient("gate_observer", can_alter=False)
        action = PostgresProducerAction(_postgres_settings(), observer)

        def failed_factory() -> _GatePostgresClient:
            assert store.gate_attempts(CAMPAIGN_ID)[-1]["status"] == "INTENT_RECORDED"
            raise OSError("controlled pre-execution crash")

        workflow = _postgres_workflow(store, tmp_path, action, failed_factory)
        plan = _postgres_plan(store, tmp_path, action)
        plan_path = tmp_path / "postgres-plan.json"
        write_json(plan_path, plan)
        monkeypatch.setattr(
            workflow, "_producer_source", lambda: plan["producer_source"]
        )
        monkeypatch.setattr(
            workflow,
            "_verify_ready_state",
            lambda *_args, **_kwargs: _postgres_verification(),
        )

        with pytest.raises(Refusal, match="GATE_ACTION_NOT_COMMITTED"):
            workflow.execute(
                CAMPAIGN_ID,
                context=_context(),
                plan_path=plan_path,
                executed_at="2026-01-01T12:05:00Z",
            )
        attempt = store.gate_attempts(CAMPAIGN_ID)[-1]
        assert attempt["status"] == "NOT_COMMITTED"
        assert (
            attempt["outcome"]["action_outcome"]["destructive_statements_attempted"]
            == 0
        )
        assert observer.current["legacy_column"] is not None


def test_postgres_gate_permission_loss_consumes_plan_without_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _ready_store(tmp_path) as store:
        observer = _GatePostgresClient("gate_observer", can_alter=False)
        action = PostgresProducerAction(_postgres_settings(), observer)
        mutator = _GatePostgresClient("gate_mutator", can_alter=False)
        workflow = _postgres_workflow(store, tmp_path, action, lambda: mutator)
        plan = _postgres_plan(store, tmp_path, action)
        plan_path = tmp_path / "postgres-plan.json"
        write_json(plan_path, plan)
        monkeypatch.setattr(
            workflow,
            "_producer_source",
            lambda: plan["producer_source"],
        )
        monkeypatch.setattr(
            workflow,
            "_verify_ready_state",
            lambda *_args, **_kwargs: _postgres_verification(),
        )

        with pytest.raises(Refusal, match="POSTGRES_MUTATION_PERMISSION_DENIED"):
            workflow.execute(
                CAMPAIGN_ID,
                context=_context(),
                plan_path=plan_path,
                executed_at="2026-01-01T12:05:00Z",
            )
        assert store.gate_attempts(CAMPAIGN_ID)[-1]["status"] == "NOT_COMMITTED"
        assert mutator.execute_calls == 0
        assert observer.current["legacy_column"] is not None


def test_postgres_gate_resolves_lost_response_without_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _ready_store(tmp_path) as store:
        observer = _GatePostgresClient("gate_observer", can_alter=False)
        action = PostgresProducerAction(_postgres_settings(), observer)
        mutator = _GatePostgresClient(
            "gate_mutator", can_alter=True, behavior="lost-response"
        )
        mutator.mirror = observer
        workflow = _postgres_workflow(store, tmp_path, action, lambda: mutator)
        plan = _postgres_plan(store, tmp_path, action)
        plan_path = tmp_path / "postgres-plan.json"
        write_json(plan_path, plan)
        verification = _postgres_verification()
        write_json(
            tmp_path
            / "artifacts"
            / CAMPAIGN_ID
            / "producer"
            / "gate-verification.json",
            verification,
        )
        monkeypatch.setattr(
            workflow, "_producer_source", lambda: plan["producer_source"]
        )
        monkeypatch.setattr(
            workflow,
            "_verify_ready_state",
            lambda *_args, **_kwargs: verification,
        )

        with pytest.raises(Refusal, match="GATE_ACTION_OUTCOME_UNKNOWN"):
            workflow.execute(
                CAMPAIGN_ID,
                context=_context(),
                plan_path=plan_path,
                executed_at="2026-01-01T12:05:00Z",
            )
        assert store.gate_attempts(CAMPAIGN_ID)[-1]["status"] == "OUTCOME_UNKNOWN"
        observer.unavailable = False
        recovered = workflow.resolve_postgres_outcome(
            CAMPAIGN_ID,
            context=_context(),
            plan_path=plan_path,
            observed_at="2026-01-01T12:07:00Z",
        )
        assert recovered["result"] == "RECOVERED_COMMITTED"
        assert recovered["gate_receipt"]["action"]["result"] == str(
            PostgresActionOutcome.COMMITTED
        )
        assert mutator.execute_calls == 1
        assert store.gate_attempts(CAMPAIGN_ID)[-1]["status"] == "EXECUTED"


def test_gate_merges_fresh_superset_observation_from_issued_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _ready_store(tmp_path) as store:
        superset_settings = SupersetSettings(
            base_url="http://127.0.0.1:18088",
            username="gate-verifier",
            password="runtime-only",
            provider="db",
            principal="read-only-verifier",
            version="6.0.0",
            allow_apply=False,
            allowed_dataset_ids=(1,),
            timeout_seconds=5,
        )
        workflow = ProducerGateWorkflow(
            store=store,
            artifact_directory=tmp_path / "artifacts",
            producer_repository_root=tmp_path,
            producer_source_marker=tmp_path / "producer.json",
            sentinel_root=tmp_path / "sentinels",
            boundary=None,
            git_dbt=None,
            superset_settings=superset_settings,
            superset_client=object(),  # type: ignore[arg-type]
        )
        native_plan = with_digest(
            {
                "campaign_id": CAMPAIGN_ID,
                "consumer_id": "consumer-superset",
                "datahub_urn": "urn:li:dataset:superset-one",
            },
            "plan_digest",
        )
        native_receipt = with_digest(
            {"consumer_id": "consumer-superset"}, "receipt_digest"
        )
        native_validation = with_digest({"result": "PASSED"}, "validation_digest")
        accepted = {
            "plan": native_plan,
            "receipt": native_receipt,
            "validation": native_validation,
        }
        binding = with_digest({"consumer_id": "consumer-superset"}, "binding_digest")
        write_json(
            tmp_path
            / "artifacts"
            / CAMPAIGN_ID
            / "producer"
            / "superset-gate"
            / "gate-binding.json",
            binding,
        )
        expected = {
            "consumer_id": "consumer-superset",
            "datahub_urn": "urn:li:dataset:superset-one",
            "binding_digest": binding["binding_digest"],
            "plan_digest": native_plan["plan_digest"],
            "receipt_digest": native_receipt["receipt_digest"],
            "validation_digest": native_validation["validation_digest"],
        }
        source = {
            "id": "superset:dataset-one",
            "required": True,
            "status": "COMPLETE",
            "source_version": "0.1.0",
            "identity": "dataset:1:dataset-one:chart:2:chart-one",
            "scope": {
                "direction": "downstream",
                "max_hops": 1,
                "filters": ["dataset_id:1", "chart_id:2"],
                "pages": 1,
                "reported_total": 1,
                "returned_total": 1,
            },
            "freshness": {
                "observed_at": "2026-01-01T12:05:00Z",
                "source_updated_at": "2026-01-01T12:05:00Z",
                "maximum_age_seconds": 300,
            },
            "permissions": {
                "principal": "read-only-verifier",
                "effective_scope": "read-only",
            },
            "limitations": ["Table-level DataHub lineage is complementary."],
            "artifact_ids": [f"sha256:{'b' * 64}"],
        }
        observation = with_digest(
            {
                "source_id": source["id"],
                "evidence_source": source,
            },
            "observation_digest",
        )
        monkeypatch.setattr(
            workflow,
            "_accepted_superset_artifacts",
            lambda _campaign_id: [accepted],
        )
        calls = 0

        def verify_superset(
            _self: SupersetGateVerifier,
            observed_binding: dict[str, Any],
            **_kwargs: Any,
        ) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            assert observed_binding == binding
            return observation

        monkeypatch.setattr(SupersetGateVerifier, "verify", verify_superset)
        initial = with_digest(
            {
                "schema_version": "1.0.0",
                "captured_at": "2026-01-01T12:05:00Z",
                "mode": "live",
                "sources": [source | {"id": "datahub"}],
            },
            "envelope_digest",
        )

        merged, observations = workflow._verify_superset_gate_bindings(
            CAMPAIGN_ID,
            plan={"superset": [expected]},
            envelope=initial,
            trusted_now="2026-01-01T12:05:00Z",
        )

        assert calls == 1
        assert observations == [
            {
                "consumer_id": "consumer-superset",
                "observation_digest": observation["observation_digest"],
            }
        ]
        assert any(item["id"] == source["id"] for item in merged["sources"])
        validate_schema("evidence-envelope", merged)
