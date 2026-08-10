from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from retirement_conductor.canonical import with_digest
from retirement_conductor.errors import Refusal
from retirement_conductor.schemas import validate_schema
from retirement_conductor.superset import SupersetAdapter
from retirement_conductor.superset_config import SupersetSettings
from retirement_conductor.superset_gate import (
    SupersetGateVerifier,
    capture_superset_gate_binding,
)
from retirement_conductor.vocabulary import RefusalCode

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


class FakeGateClient:
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
                {"id": 1, "uuid": "column-id", "column_name": "id", "type": "INT"},
                {
                    "id": 2,
                    "uuid": "column-status",
                    "column_name": "status",
                    "type": "STRING",
                },
            ],
            "metrics": [],
            "changed_on": "2026-08-10T11:50:00Z",
        }
        self.chart = {
            "id": 2,
            "uuid": "chart-uuid",
            "datasource_id": 1,
            "datasource_type": "table",
            "viz_type": "table",
            "params": json.dumps(
                {
                    "all_columns": ["id", "status", "amount"],
                    "order_by_cols": [["id", True]],
                    "row_limit": 1000,
                },
                sort_keys=True,
            ),
            "query_context": None,
            "owners": [{"id": 1}],
        }
        self.database = {
            "id": 4,
            "uuid": "441e07c8-4a86-4931-a2d0-5324cce29ddc",
        }
        self.version = "6.0.0"
        self.semantic_drift = False
        self.reverse_order = False
        self.auth_failure = False
        self.permission_failure = False
        self.outage = False
        self.timeout = False
        self.deleted: str | None = None
        self.update_calls = 0
        self.read_calls = 0

    def authenticate(self) -> None:
        if self.auth_failure:
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_PERMISSION_DENIED,
                "authentication refused",
            )

    def health(self) -> str:
        if self.outage:
            raise Refusal(RefusalCode.SOURCE_NOT_FOUND, "Superset unavailable")
        self._read()
        return "OK"

    def server_version(self) -> str:
        self._read()
        return self.version

    def get_dataset(self, dataset_id: int) -> dict[str, Any]:
        self._read()
        assert dataset_id == 1
        if self.deleted == "dataset":
            raise Refusal(RefusalCode.SOURCE_NOT_FOUND, "dataset deleted")
        return copy.deepcopy(self.dataset)

    def update_dataset(self, dataset_id: int, sql: str) -> dict[str, Any]:
        assert dataset_id == 1
        self.update_calls += 1
        self.dataset["sql"] = sql
        self.dataset["changed_on"] = "2026-08-10T11:55:00Z"
        return {"id": 1}

    def get_chart(self, chart_id: int) -> dict[str, Any]:
        self._read()
        assert chart_id == 2
        if self.deleted == "chart":
            raise Refusal(RefusalCode.SOURCE_NOT_FOUND, "chart deleted")
        return copy.deepcopy(self.chart)

    def get_database(self, database_id: int) -> dict[str, Any]:
        self._read()
        assert database_id == 4
        if self.deleted == "database":
            raise Refusal(RefusalCode.SOURCE_NOT_FOUND, "database deleted")
        return copy.deepcopy(self.database)

    def execute_chart(self, chart_id: int) -> dict[str, Any]:
        self._read()
        assert chart_id == 2
        status = "changed" if self.semantic_drift else "pending"
        rows = [
            {"id": 1, "status": status, "amount": 10.0},
            {"id": 2, "status": "shipped", "amount": 20.0},
        ]
        if self.reverse_order:
            rows.reverse()
        return {
            "status": "success",
            "error": None,
            "data": rows,
            "rowcount": 2,
            "sql_rowcount": 2,
            "colnames": ["id", "status", "amount"],
            "is_cached": None,
            "query": str(self.dataset["sql"]),
        }

    def _read(self) -> None:
        self.read_calls += 1
        if self.permission_failure:
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_PERMISSION_DENIED,
                "read permission removed",
            )
        if self.timeout:
            raise TimeoutError("injected read timeout")


def settings(*, allow_apply: bool) -> SupersetSettings:
    return SupersetSettings(
        base_url="http://127.0.0.1:18088",
        username="gate-verifier",
        password="runtime-only",
        provider="db",
        principal="local-read-only-verifier",
        version="6.0.0",
        allow_apply=allow_apply,
        allowed_dataset_ids=(1,),
        timeout_seconds=5,
    )


def expected_source() -> dict[str, Any]:
    return {
        "id": "superset:c40f2cbb-6683-4278-b6df-790a5ac1611d",
        "required": True,
        "status": "COMPLETE",
        "source_version": "0.1.0",
        "identity": "dataset:1:c40f2cbb-6683-4278-b6df-790a5ac1611d:chart:2:chart-uuid",
        "scope": {
            "direction": "downstream",
            "max_hops": 1,
            "filters": ["dataset_id:1", "chart_id:2"],
            "pages": 1,
            "reported_total": 1,
            "returned_total": 1,
        },
        "freshness": {
            "observed_at": "2026-08-10T12:00:00Z",
            "source_updated_at": "2026-08-10T11:55:00Z",
            "maximum_age_seconds": 300,
        },
        "permissions": {
            "principal": "local-read-only-verifier",
            "effective_scope": "read-only",
        },
        "limitations": ["DataHub connector field lineage is corroborative."],
        "artifact_ids": [],
    }


def accepted(
    tmp_path: Path,
) -> tuple[FakeGateClient, dict[str, Any], SupersetSettings]:
    client = FakeGateClient()
    mutation_adapter = SupersetAdapter(settings(allow_apply=True), client)
    preflight = mutation_adapter.preflight(
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
    plan = mutation_adapter.plan(
        preflight,
        campaign_id="campaign-1",
        consumer_id="consumer-1",
        allow_semantic_change=False,
        artifact_root=tmp_path / "migration",
    )
    apply_record = mutation_adapter.apply(
        plan,
        confirmed_plan_digest=str(plan["plan_digest"]),
        artifact_root=tmp_path / "migration",
    )
    validation = mutation_adapter.validate(
        plan, apply_record, artifact_root=tmp_path / "validation"
    )
    receipt = mutation_adapter.emit_receipt(
        plan,
        apply_record,
        validation,
        compensation=None,
        artifact_root=tmp_path / "migration",
        captured_at="2026-08-10T11:55:00Z",
    )
    read_settings = settings(allow_apply=False)
    binding = capture_superset_gate_binding(
        settings=read_settings,
        client=client,
        consumer_id="consumer-1",
        datahub_native_identity={
            "urn": plan["datahub_urn"],
            "mapping_basis": "DataHub connector URL datasource_id",
        },
        plan=plan,
        receipt=receipt,
        validation=validation,
        expected_evidence_source=expected_source(),
        captured_at="2026-08-10T12:00:00Z",
        maximum_age_seconds=300,
        artifact_root=tmp_path / "gate",
    )
    return client, binding, read_settings


def verify(
    client: FakeGateClient,
    binding: dict[str, Any],
    read_settings: SupersetSettings,
    *,
    now: datetime = NOW,
) -> dict[str, Any]:
    return SupersetGateVerifier(
        settings=read_settings,
        client=client,
        clock=lambda: NOW,
    ).verify(binding, trusted_now=now)


def test_unchanged_verification_is_repeatable_and_never_mutates(tmp_path: Path) -> None:
    client, binding, read_settings = accepted(tmp_path)
    mutation_calls_before = client.update_calls
    state_before = copy.deepcopy((client.dataset, client.chart, client.database))

    first = verify(client, binding, read_settings)
    second = verify(client, binding, read_settings)

    assert first["binding_matches"] == second["binding_matches"]
    assert all(first["binding_matches"].values())
    assert (
        first["current_source_fingerprint"]
        == binding["accepted_native"]["dataset_fingerprint"]
    )
    assert first["capabilities"]["mutation"] is False
    envelope = with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": first["observed_at"],
            "mode": "live",
            "sources": [first["evidence_source"]],
        },
        "envelope_digest",
    )
    validate_schema("evidence-envelope", envelope)
    assert first["evidence_source"]["id"] == expected_source()["id"]
    assert first["evidence_source"]["identity"] == expected_source()["identity"]
    assert first["evidence_source"]["scope"] == expected_source()["scope"]
    assert client.update_calls == mutation_calls_before
    assert (client.dataset, client.chart, client.database) == state_before


@pytest.mark.parametrize(
    ("change", "binding_name"),
    [
        (
            lambda client, binding: client.dataset.__setitem__(
                "sql",
                f"{binding['accepted_plan']['target']['after_sql']} WHERE id > 0",
            ),
            "post_apply_fingerprint",
        ),
        (
            lambda client, binding: client.dataset.__setitem__(
                "sql", binding["accepted_plan"]["target"]["before_sql"]
            ),
            "legacy_field_absent",
        ),
        (
            lambda client, binding: client.dataset.__setitem__(
                "sql",
                str(binding["accepted_plan"]["target"]["after_sql"]).replace(
                    "order_status", "other_status"
                ),
            ),
            "replacement_mapping_exact",
        ),
        (
            lambda client, binding: client.dataset["owners"].append({"id": 2}),
            "post_apply_fingerprint",
        ),
    ],
)
def test_source_drift_refuses_with_specific_binding(
    tmp_path: Path, change: Any, binding_name: str
) -> None:
    client, binding, read_settings = accepted(tmp_path)
    change(client, binding)

    with pytest.raises(Refusal) as exc_info:
        verify(client, binding, read_settings)

    assert exc_info.value.code == RefusalCode.SOURCE_FINGERPRINT_MISMATCH
    assert exc_info.value.details["binding"] == binding_name


def test_chart_move_refuses_exact_dataset_binding(tmp_path: Path) -> None:
    client, binding, read_settings = accepted(tmp_path)
    client.chart["datasource_id"] = 99

    with pytest.raises(Refusal) as exc_info:
        verify(client, binding, read_settings)

    assert exc_info.value.code == RefusalCode.IDENTITY_NATIVE_OBJECT_RECREATED
    assert "chart_dataset_binding" in exc_info.value.details["mismatches"]


def test_chart_context_and_semantic_drift_refuse(tmp_path: Path) -> None:
    client, binding, read_settings = accepted(tmp_path)
    client.chart["params"] = json.dumps({"row_limit": 1})
    client.semantic_drift = True

    with pytest.raises(Refusal) as exc_info:
        verify(client, binding, read_settings)

    assert exc_info.value.code == RefusalCode.SOURCE_FINGERPRINT_MISMATCH
    assert exc_info.value.details["binding"] == "chart_context"


@pytest.mark.parametrize(
    ("field", "object_name", "mismatch"),
    [
        ("uuid", "dataset", "dataset_uuid"),
        ("uuid", "chart", "chart_uuid"),
        ("uuid", "database", "database_uuid"),
    ],
)
def test_uuid_drift_refuses(
    tmp_path: Path, field: str, object_name: str, mismatch: str
) -> None:
    client, binding, read_settings = accepted(tmp_path)
    target = getattr(client, object_name)
    target[field] = "recreated-uuid"
    if object_name == "database":
        embedded_database = client.dataset["database"]
        assert isinstance(embedded_database, dict)
        embedded_database["uuid"] = "recreated-uuid"

    with pytest.raises(Refusal) as exc_info:
        verify(client, binding, read_settings)

    assert exc_info.value.code == RefusalCode.IDENTITY_NATIVE_OBJECT_RECREATED
    assert mismatch in exc_info.value.details["mismatches"]


def test_semantic_and_ordering_drift_refuse(tmp_path: Path) -> None:
    client, binding, read_settings = accepted(tmp_path)
    client.reverse_order = True

    with pytest.raises(Refusal) as exc_info:
        verify(client, binding, read_settings)

    assert exc_info.value.code == RefusalCode.VALIDATION_RECEIPT_FAILED
    assert exc_info.value.details["binding"] == "semantic_result"


@pytest.mark.parametrize("deleted", ["dataset", "chart", "database"])
def test_deleted_native_object_refuses(tmp_path: Path, deleted: str) -> None:
    client, binding, read_settings = accepted(tmp_path)
    client.deleted = deleted

    with pytest.raises(Refusal) as exc_info:
        verify(client, binding, read_settings)

    assert exc_info.value.code == RefusalCode.SOURCE_NOT_FOUND


def test_authentication_and_timeout_refuse(tmp_path: Path) -> None:
    client, binding, read_settings = accepted(tmp_path)
    client.auth_failure = True
    with pytest.raises(Refusal) as auth:
        verify(client, binding, read_settings)
    assert auth.value.code == RefusalCode.SOURCE_DATAHUB_PERMISSION_DENIED

    client.auth_failure = False
    client.timeout = True
    with pytest.raises(Refusal) as timeout:
        verify(client, binding, read_settings)
    assert timeout.value.code == RefusalCode.RECONCILIATION_REFRESH_TIMEOUT


def test_read_permission_and_outage_refuse(tmp_path: Path) -> None:
    client, binding, read_settings = accepted(tmp_path)
    client.permission_failure = True
    with pytest.raises(Refusal) as permission:
        verify(client, binding, read_settings)
    assert permission.value.code == RefusalCode.SOURCE_DATAHUB_PERMISSION_DENIED

    client.permission_failure = False
    client.outage = True
    with pytest.raises(Refusal) as outage:
        verify(client, binding, read_settings)
    assert outage.value.code == RefusalCode.SOURCE_NOT_FOUND


def test_unexpected_response_shape_refuses(tmp_path: Path) -> None:
    client, binding, read_settings = accepted(tmp_path)
    client.chart.pop("uuid")

    with pytest.raises(Refusal) as exc_info:
        verify(client, binding, read_settings)

    assert exc_info.value.code == RefusalCode.RUNTIME_STATE_DRIFT


@pytest.mark.parametrize(
    "artifact", ["accepted_plan", "accepted_receipt", "accepted_validation"]
)
def test_tampered_accepted_artifact_refuses(tmp_path: Path, artifact: str) -> None:
    client, binding, read_settings = accepted(tmp_path)
    tampered = copy.deepcopy(binding)
    tampered[artifact]["tampered"] = True
    tampered = with_digest(tampered, "binding_digest")

    with pytest.raises(Refusal) as exc_info:
        verify(client, tampered, read_settings)

    assert exc_info.value.code == RefusalCode.INTEGRITY_DIGEST_MISMATCH


def test_version_and_configuration_drift_refuse(tmp_path: Path) -> None:
    client, binding, read_settings = accepted(tmp_path)
    client.version = "6.0.1"
    with pytest.raises(Refusal) as version:
        verify(client, binding, read_settings)
    assert version.value.code == RefusalCode.SOURCE_RECEIPT_VERSION_MISMATCH

    changed_settings = SupersetSettings(
        **{**read_settings.__dict__, "timeout_seconds": 6}
    )
    client.version = "6.0.0"
    with pytest.raises(Refusal) as configuration:
        verify(client, binding, changed_settings)
    assert configuration.value.code == RefusalCode.GATE_STATE_DRIFT

    adapter_drift = copy.deepcopy(binding)
    adapter_drift["adapter_version"] = "0.2.0"
    adapter_drift = with_digest(adapter_drift, "binding_digest")
    with pytest.raises(Refusal) as adapter:
        verify(client, adapter_drift, read_settings)
    assert adapter.value.code == RefusalCode.SOURCE_RECEIPT_VERSION_MISMATCH


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "superset:operator-selected"),
        ("identity", "dataset:99:other:chart:88:other"),
        ("scope", {**expected_source()["scope"], "filters": ["dataset_id:99"]}),
        (
            "permissions",
            {"principal": "other-principal", "effective_scope": "read-only"},
        ),
    ],
)
def test_expected_source_must_match_accepted_native_scope(
    tmp_path: Path, field: str, value: Any
) -> None:
    client, binding, read_settings = accepted(tmp_path)
    changed = copy.deepcopy(binding)
    changed["expected_evidence_source"][field] = value
    changed = with_digest(changed, "binding_digest")

    with pytest.raises(Refusal) as exc_info:
        verify(client, changed, read_settings)

    assert exc_info.value.code == RefusalCode.EVIDENCE_REQUIRED_SOURCE_INCOMPLETE


def test_stale_observation_refuses_under_trusted_clock(tmp_path: Path) -> None:
    client, binding, read_settings = accepted(tmp_path)

    with pytest.raises(Refusal) as exc_info:
        verify(client, binding, read_settings, now=NOW + timedelta(seconds=301))

    assert exc_info.value.code == RefusalCode.EVIDENCE_RECEIPT_EXPIRED


def test_gate_runtime_refuses_mutation_capability(tmp_path: Path) -> None:
    client, binding, _ = accepted(tmp_path)

    with pytest.raises(Refusal) as exc_info:
        SupersetGateVerifier(
            settings=settings(allow_apply=True),
            client=client,
        ).verify(binding, trusted_now=NOW)

    assert exc_info.value.code == RefusalCode.AUTH_APPLY_DISABLED
