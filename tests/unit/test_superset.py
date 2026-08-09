from __future__ import annotations

import copy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from retirement_conductor.canonical import digest_json, with_digest
from retirement_conductor.errors import Refusal
from retirement_conductor.superset import SupersetAdapter, replace_identifier_once
from retirement_conductor.superset_config import SupersetSettings
from retirement_conductor.superset_workflow import SupersetWorkflow
from retirement_conductor.vocabulary import RefusalCode


class FakeSupersetClient:
    def __init__(self) -> None:
        self.dataset = {
            "id": 1,
            "uuid": "c40f2cbb-6683-4278-b6df-790a5ac1611d",
            "database": {
                "id": 4,
                "uuid": "441e07c8-4a86-4931-a2d0-5324cce29ddc",
            },
            "schema": "public",
            "table_name": "ws04_status_by_order",
            "sql": "SELECT id, legacy_status AS status, amount FROM public.orders",
            "owners": [{"id": 1}],
            "columns": [
                {"id": 1, "uuid": "column-id", "column_name": "id", "type": "INTEGER"},
                {
                    "id": 2,
                    "uuid": "column-status",
                    "column_name": "status",
                    "type": "STRING",
                },
                {
                    "id": 3,
                    "uuid": "column-amount",
                    "column_name": "amount",
                    "type": "DECIMAL",
                },
            ],
            "metrics": [
                {
                    "id": 1,
                    "uuid": "metric-count",
                    "metric_name": "count",
                    "expression": "COUNT(*)",
                }
            ],
            "changed_on": "2026-08-09T00:00:00",
        }
        self.chart = {"id": 2, "uuid": "chart-uuid", "datasource_id": 1}
        self.update_behavior = "normal"
        self.semantic_drift = False
        self.execution_failure = False
        self.update_calls = 0

    def authenticate(self) -> None:
        return None

    def health(self) -> str:
        return "OK"

    def get_dataset(self, dataset_id: int) -> dict[str, Any]:
        assert dataset_id == 1
        return copy.deepcopy(self.dataset)

    def update_dataset(self, dataset_id: int, sql: str) -> dict[str, Any]:
        assert dataset_id == 1
        self.update_calls += 1
        if self.update_behavior == "timeout_before":
            raise TimeoutError
        self.dataset["sql"] = sql
        self.dataset["changed_on"] = f"2026-08-09T00:00:0{self.update_calls}"
        if self.update_behavior == "timeout_after":
            raise TimeoutError
        return {"id": 1}

    def get_chart(self, chart_id: int) -> dict[str, Any]:
        assert chart_id == 2
        return copy.deepcopy(self.chart)

    def execute_chart(self, chart_id: int) -> dict[str, Any]:
        assert chart_id == 2
        replacement = "order_status" in str(self.dataset["sql"])
        status = "changed" if replacement and self.semantic_drift else "pending"
        rows = [{"id": 1, "status": status, "amount": 10.0}]
        return {
            "status": "failed" if self.execution_failure else "success",
            "error": "native failure" if self.execution_failure else None,
            "data": rows,
            "rowcount": 1,
            "sql_rowcount": 1,
            "colnames": ["id", "status", "amount"],
            "is_cached": None,
            "query": str(self.dataset["sql"]),
        }


def settings(*, allow_apply: bool = True) -> SupersetSettings:
    return SupersetSettings(
        base_url="http://127.0.0.1:18088",
        username="operator",
        password="credential",
        provider="db",
        principal="disposable-operator",
        version="6.0.0",
        allow_apply=allow_apply,
        allowed_dataset_ids=(1,),
        timeout_seconds=5,
    )


def planned(
    tmp_path: Path,
    client: FakeSupersetClient,
    *,
    allow_apply: bool = True,
) -> tuple[SupersetAdapter, dict[str, Any]]:
    adapter = SupersetAdapter(settings(allow_apply=allow_apply), client)
    preflight = adapter.preflight(
        datahub_entities=[
            {
                "urn": (
                    "urn:li:dataset:(urn:li:dataPlatform:superset,"
                    "WS04.public.ws04_status_by_order,PROD)"
                ),
                "external_url": (
                    "http://127.0.0.1:18088/explore/"
                    "?datasource_type=table&datasource_id=1"
                ),
            }
        ],
        dataset_id=1,
        chart_id=2,
        legacy_field="legacy_status",
        replacement_field="order_status",
        artifact_root=tmp_path / "preflight",
    )
    plan = adapter.plan(
        preflight,
        campaign_id="campaign-1",
        consumer_id="consumer-1",
        allow_semantic_change=False,
        artifact_root=tmp_path / "campaign-1" / "superset",
    )
    return adapter, plan


def approval(plan: dict[str, Any], authorization_digest: str) -> dict[str, Any]:
    return with_digest(
        {
            "schema_version": "1.0.0",
            "approval_id": "approval-1",
            "campaign_id": plan["campaign_id"],
            "plan_digest": plan["plan_digest"],
            "source_version": plan["source_version"],
            "targets": plan["proposed_targets"],
            "principal": "external-operator",
            "scope": ["apply", "compensate"],
            "authorization_digest": authorization_digest,
            "authorized_at": "2026-08-09T00:00:00Z",
            "expires_at": "2026-08-09T01:00:00Z",
        },
        "approval_digest",
    )


def test_preflight_binds_exact_datahub_and_native_identity(tmp_path: Path) -> None:
    client = FakeSupersetClient()
    _, plan = planned(tmp_path, client)

    assert plan["native_identity"]["dataset_id"] == 1
    assert plan["native_identity"]["dataset_uuid"] == client.dataset["uuid"]
    assert plan["target"]["before_sql"].count("legacy_status") == 1
    assert plan["target"]["after_sql"].count("order_status") == 1
    assert plan["proposed_targets"] == [f"superset:dataset:1:{client.dataset['uuid']}"]


def test_sql_replacement_ignores_comments_and_literals() -> None:
    sql = """-- legacy_status is historical
select legacy_status, 'legacy_status', $$legacy_status$$ from orders
/* legacy_status is not executable */
"""

    replaced = replace_identifier_once(sql, "legacy_status", "order_status")

    assert "select order_status" in replaced
    assert replaced.count("legacy_status") == 4


@pytest.mark.parametrize(
    "sql",
    [
        "select 'legacy_status' from orders",
        'select "legacy_status" from orders',
        "select `legacy_status` from orders",
        "select [legacy_status] from orders",
    ],
)
def test_sql_replacement_refuses_non_executable_or_quoted_tokens(sql: str) -> None:
    with pytest.raises(Refusal) as exc_info:
        replace_identifier_once(sql, "legacy_status", "order_status")

    assert exc_info.value.code == RefusalCode.IDENTITY_FIELD_AMBIGUOUS


def test_workflow_refuses_apply_without_external_approval(tmp_path: Path) -> None:
    client = FakeSupersetClient()
    adapter, plan = planned(tmp_path, client)
    workflow = SupersetWorkflow(adapter, tmp_path / "artifacts")

    with pytest.raises(Refusal) as exc_info:
        workflow.apply(
            plan,
            approval=None,
            authorization_digest=digest_json({"mode": "apply"}),
            confirmed_plan_digest=str(plan["plan_digest"]),
            trusted_now=datetime(2026, 8, 9, 0, 5, tzinfo=UTC),
        )

    assert exc_info.value.code == RefusalCode.AUTH_APPROVAL_MISSING
    assert client.update_calls == 0


def test_preflight_refuses_ambiguous_datahub_identity(tmp_path: Path) -> None:
    client = FakeSupersetClient()
    adapter = SupersetAdapter(settings(), client)
    entity = {
        "urn": (
            "urn:li:dataset:(urn:li:dataPlatform:superset,"
            "WS04.public.ws04_status_by_order,PROD)"
        ),
        "external_url": (
            "http://127.0.0.1:18088/explore/?datasource_type=table&datasource_id=1"
        ),
    }

    with pytest.raises(Refusal) as exc_info:
        adapter.preflight(
            datahub_entities=[entity, entity],
            dataset_id=1,
            chart_id=2,
            legacy_field="legacy_status",
            replacement_field="order_status",
            artifact_root=tmp_path,
        )

    assert exc_info.value.code == RefusalCode.IDENTITY_AMBIGUOUS


def test_apply_refuses_when_capability_is_disabled(tmp_path: Path) -> None:
    client = FakeSupersetClient()
    adapter, plan = planned(tmp_path, client, allow_apply=False)

    with pytest.raises(Refusal) as exc_info:
        adapter.apply(
            plan,
            confirmed_plan_digest=str(plan["plan_digest"]),
            artifact_root=tmp_path,
        )

    assert exc_info.value.code == RefusalCode.AUTH_APPLY_DISABLED
    assert client.update_calls == 0


def test_apply_refuses_source_drift_before_mutation(tmp_path: Path) -> None:
    client = FakeSupersetClient()
    adapter, plan = planned(tmp_path, client)
    client.dataset["sql"] = f"{plan['target']['before_sql']} WHERE id > 0"

    with pytest.raises(Refusal) as exc_info:
        adapter.apply(
            plan,
            confirmed_plan_digest=str(plan["plan_digest"]),
            artifact_root=tmp_path,
        )

    assert exc_info.value.code == RefusalCode.SOURCE_FINGERPRINT_MISMATCH
    assert client.update_calls == 0


def test_approved_apply_validates_emits_receipt_and_reconciles(
    tmp_path: Path,
) -> None:
    client = FakeSupersetClient()
    adapter, plan = planned(tmp_path, client)
    workflow = SupersetWorkflow(adapter, tmp_path / "artifacts")
    authorization_digest = digest_json({"mode": "apply", "datasets": [1]})

    apply_record = workflow.apply(
        plan,
        approval=approval(plan, authorization_digest),
        authorization_digest=authorization_digest,
        confirmed_plan_digest=str(plan["plan_digest"]),
        trusted_now=datetime(2026, 8, 9, 0, 5, tzinfo=UTC),
    )
    accepted = workflow.validate_and_emit_receipt(plan, apply_record)
    receipt = accepted["receipt"]
    reconciliation = workflow.reconcile(
        plan,
        receipt,
        {
            "dataset_urn": plan["datahub_urn"],
            "dataset_external_url": (
                "http://127.0.0.1:18088/explore/?datasource_type=table&datasource_id=1"
            ),
            "upstream_field_urns": [
                "urn:li:schemaField:(urn:li:dataset:(postgres,orders,PROD),order_status)"
            ],
            "table_only": False,
            "connector_version": "1.6.0",
            "direct_reread": True,
        },
    )

    assert apply_record["actual_targets"] == plan["proposed_targets"]
    assert accepted["validation"]["semantic_parity"] is True
    assert receipt["adapter"]["name"] == "superset"
    assert reconciliation["native_fingerprint"] == plan["target"]["after_fingerprint"]


def test_apply_recovers_timeout_only_after_exact_native_reread(tmp_path: Path) -> None:
    client = FakeSupersetClient()
    client.update_behavior = "timeout_after"
    adapter, plan = planned(tmp_path, client)

    record = adapter.apply(
        plan,
        confirmed_plan_digest=str(plan["plan_digest"]),
        artifact_root=tmp_path,
    )

    assert record["recovered_after_timeout"] is True
    assert record["after_fingerprint"] == plan["target"]["after_fingerprint"]


def test_apply_timeout_without_observed_change_stays_unknown(tmp_path: Path) -> None:
    client = FakeSupersetClient()
    client.update_behavior = "timeout_before"
    adapter, plan = planned(tmp_path, client)

    with pytest.raises(Refusal) as exc_info:
        adapter.apply(
            plan,
            confirmed_plan_digest=str(plan["plan_digest"]),
            artifact_root=tmp_path,
        )

    assert exc_info.value.code == RefusalCode.APPLY_OUTCOME_UNKNOWN


def test_validation_refuses_semantic_drift(tmp_path: Path) -> None:
    client = FakeSupersetClient()
    adapter, plan = planned(tmp_path, client)
    apply_record = adapter.apply(
        plan,
        confirmed_plan_digest=str(plan["plan_digest"]),
        artifact_root=tmp_path,
    )
    client.semantic_drift = True

    with pytest.raises(Refusal) as exc_info:
        adapter.validate(plan, apply_record, artifact_root=tmp_path / "validate")

    assert exc_info.value.code == RefusalCode.VALIDATION_RECEIPT_FAILED


def test_validation_refuses_native_execution_failure(tmp_path: Path) -> None:
    client = FakeSupersetClient()
    adapter, plan = planned(tmp_path, client)
    apply_record = adapter.apply(
        plan,
        confirmed_plan_digest=str(plan["plan_digest"]),
        artifact_root=tmp_path,
    )
    client.execution_failure = True

    with pytest.raises(Refusal) as exc_info:
        adapter.validate(plan, apply_record, artifact_root=tmp_path / "validate")

    assert exc_info.value.code == RefusalCode.VALIDATION_RECEIPT_FAILED


def test_receipt_refuses_validation_from_another_apply(tmp_path: Path) -> None:
    client = FakeSupersetClient()
    adapter, plan = planned(tmp_path, client)
    apply_record = adapter.apply(
        plan,
        confirmed_plan_digest=str(plan["plan_digest"]),
        artifact_root=tmp_path,
    )
    validation = adapter.validate(plan, apply_record, artifact_root=tmp_path)
    foreign = dict(validation)
    foreign.pop("validation_digest")
    foreign["apply_digest"] = digest_json({"another": "apply"})
    foreign = with_digest(foreign, "validation_digest")

    with pytest.raises(Refusal) as exc_info:
        adapter.emit_receipt(
            plan,
            apply_record,
            foreign,
            compensation=None,
            artifact_root=tmp_path,
        )

    assert exc_info.value.code == RefusalCode.VALIDATION_RECEIPT_FAILED


def test_compensation_restores_and_refuses_intervening_owner_change(
    tmp_path: Path,
) -> None:
    client = FakeSupersetClient()
    adapter, plan = planned(tmp_path, client)
    apply_record = adapter.apply(
        plan,
        confirmed_plan_digest=str(plan["plan_digest"]),
        artifact_root=tmp_path,
    )
    restored = adapter.compensate(
        plan,
        apply_record,
        artifact_root=tmp_path / "restore",
    )
    assert restored["restored_fingerprint"] == plan["target"]["before_fingerprint"]

    apply_record = adapter.apply(
        plan,
        confirmed_plan_digest=str(plan["plan_digest"]),
        artifact_root=tmp_path / "reapply",
    )
    client.dataset["sql"] = f"{plan['target']['after_sql']} WHERE id > 0"
    calls = client.update_calls

    with pytest.raises(Refusal) as exc_info:
        adapter.compensate(
            plan,
            apply_record,
            artifact_root=tmp_path / "conflict",
        )

    assert exc_info.value.code == RefusalCode.COMPENSATION_CONFLICT
    assert client.update_calls == calls


def test_table_only_datahub_evidence_cannot_close_consumer(tmp_path: Path) -> None:
    client = FakeSupersetClient()
    adapter, plan = planned(tmp_path, client)
    apply_record = adapter.apply(
        plan,
        confirmed_plan_digest=str(plan["plan_digest"]),
        artifact_root=tmp_path,
    )
    validation = adapter.validate(plan, apply_record, artifact_root=tmp_path)
    receipt = adapter.emit_receipt(
        plan,
        apply_record,
        validation,
        compensation=None,
        artifact_root=tmp_path,
    )

    with pytest.raises(Refusal) as exc_info:
        adapter.reconcile_source(
            plan,
            receipt,
            {
                "dataset_urn": plan["datahub_urn"],
                "dataset_external_url": (
                    "http://127.0.0.1:18088/explore/"
                    "?datasource_type=table&datasource_id=1"
                ),
                "upstream_field_urns": [],
                "table_only": True,
            },
            artifact_root=tmp_path / "reconcile",
        )

    assert exc_info.value.code == RefusalCode.RECONCILIATION_SCOPE_MISMATCH
