"""Read-only gate-time reconstruction for one accepted Superset receipt."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from retirement_conductor.canonical import digest_json, verify_digest, with_digest
from retirement_conductor.clock import parse_timestamp, validate_trusted_clock
from retirement_conductor.errors import Refusal
from retirement_conductor.superset import (
    ADAPTER_VERSION,
    identifier_occurrences,
    inspect_execution,
    snapshot_dataset,
    write_artifact,
)
from retirement_conductor.superset_config import SupersetSettings
from retirement_conductor.vocabulary import RefusalCode

GATE_BINDING_SCHEMA_VERSION = "1.0.0"
GATE_OBSERVATION_SCHEMA_VERSION = "1.0.0"
SEMANTIC_KEYS = (
    "rowcount",
    "sql_rowcount",
    "columns",
    "safe_output_digest",
    "query_digest",
)


class SupersetGateClient(Protocol):
    """Only the authenticated read surface available to gate verification."""

    def authenticate(self) -> None: ...

    def health(self) -> str: ...

    def server_version(self) -> str: ...

    def get_dataset(self, dataset_id: int) -> dict[str, Any]: ...

    def get_chart(self, chart_id: int) -> dict[str, Any]: ...

    def get_database(self, database_id: int) -> dict[str, Any]: ...

    def execute_chart(self, chart_id: int) -> dict[str, Any]: ...


def capture_superset_gate_binding(
    *,
    settings: SupersetSettings,
    client: SupersetGateClient,
    consumer_id: str,
    datahub_native_identity: Mapping[str, Any],
    plan: Mapping[str, Any],
    receipt: Mapping[str, Any],
    validation: Mapping[str, Any],
    expected_evidence_source: Mapping[str, Any],
    captured_at: str,
    maximum_age_seconds: int,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    """Freeze the accepted native facts that a later gate must reconstruct."""

    _require_read_only_settings(settings)
    _require_accepted_artifacts(
        consumer_id=consumer_id,
        datahub_native_identity=datahub_native_identity,
        plan=plan,
        receipt=receipt,
        validation=validation,
    )
    _require_evidence_source(
        expected_evidence_source,
        maximum_age_seconds,
        plan=plan,
        expected_principal=settings.principal,
    )
    if maximum_age_seconds < 1:
        raise Refusal(
            RefusalCode.RUNTIME_CONFIGURATION_INCOMPLETE,
            "Superset gate evidence must have a positive freshness window.",
        )
    parse_timestamp(captured_at)
    native = _read_native(settings, client, plan)
    _require_current_source(plan, native["dataset"])
    identity = dict(plan["native_identity"])
    chart = native["chart"]
    database = native["database"]
    _require_native_identities(identity, native["dataset"], chart, database)
    execution_raw, execution = _execute_native(client, plan)
    _require_semantic_validation(validation, execution)
    binding = with_digest(
        {
            "schema_version": GATE_BINDING_SCHEMA_VERSION,
            "consumer_id": consumer_id,
            "datahub_native_identity": dict(datahub_native_identity),
            "accepted_plan": dict(plan),
            "accepted_receipt": dict(receipt),
            "accepted_validation": dict(validation),
            "accepted_native": {
                "dataset_fingerprint": native["dataset"]["fingerprint"],
                "chart": chart,
                "database": database,
                "semantic_result": _semantic_result(execution_raw),
            },
            "adapter_version": ADAPTER_VERSION,
            "server_version": native["server_version"],
            "safe_configuration_digest": digest_json(settings.safe_summary()),
            "expected_evidence_source": dict(expected_evidence_source),
            "captured_at": captured_at,
            "maximum_age_seconds": maximum_age_seconds,
            "limitations": [
                (
                    "DataHub proves graph membership and cross-system identity; "
                    "native Superset SQL and execution prove consumer state."
                ),
                (
                    "The official Superset connector's supported lineage is "
                    "table-level; parser-derived field lineage is corroborative."
                ),
                "Read-only gate verification does not decide campaign readiness.",
            ],
        },
        "binding_digest",
    )
    if artifact_root is not None:
        write_artifact(artifact_root, "gate-binding", binding)
    return binding


class SupersetGateVerifier:
    """Reconstruct accepted Superset facts without a mutation method."""

    def __init__(
        self,
        *,
        settings: SupersetSettings,
        client: SupersetGateClient,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.client = client
        self.clock = clock or (lambda: datetime.now(UTC))

    def verify(
        self,
        binding: Mapping[str, Any],
        *,
        trusted_now: datetime,
        artifact_root: Path | None = None,
    ) -> dict[str, Any]:
        """Return one normalized fresh observation or raise a stable refusal."""

        _require_read_only_settings(self.settings)
        verify_digest(dict(binding), "binding_digest")
        plan = _mapping(binding, "accepted_plan")
        receipt = _mapping(binding, "accepted_receipt")
        validation = _mapping(binding, "accepted_validation")
        datahub_identity = _mapping(binding, "datahub_native_identity")
        consumer_id = _string(binding, "consumer_id")
        _require_accepted_artifacts(
            consumer_id=consumer_id,
            datahub_native_identity=datahub_identity,
            plan=plan,
            receipt=receipt,
            validation=validation,
        )
        if binding.get("adapter_version") != ADAPTER_VERSION:
            raise Refusal(
                RefusalCode.SOURCE_RECEIPT_VERSION_MISMATCH,
                "The Superset gate adapter version changed after acceptance.",
            )
        if binding.get("safe_configuration_digest") != digest_json(
            self.settings.safe_summary()
        ):
            raise Refusal(
                RefusalCode.GATE_STATE_DRIFT,
                "The safe Superset endpoint or read configuration changed.",
            )
        maximum_age_seconds = _positive_int(binding, "maximum_age_seconds")
        expected_source = _mapping(binding, "expected_evidence_source")
        _require_evidence_source(
            expected_source,
            maximum_age_seconds,
            plan=plan,
            expected_principal=self.settings.principal,
        )

        try:
            native = _read_native(self.settings, self.client, plan)
        except TimeoutError as exc:
            raise Refusal(
                RefusalCode.RECONCILIATION_REFRESH_TIMEOUT,
                "Superset gate-time native reread timed out.",
            ) from exc

        if native["server_version"] != binding.get("server_version"):
            raise Refusal(
                RefusalCode.SOURCE_RECEIPT_VERSION_MISMATCH,
                "The Superset server version changed after receipt acceptance.",
                {
                    "expected": binding.get("server_version"),
                    "actual": native["server_version"],
                },
            )
        identity = dict(plan["native_identity"])
        accepted_native = _mapping(binding, "accepted_native")
        chart = native["chart"]
        database = native["database"]
        _require_native_identities(identity, native["dataset"], chart, database)
        if chart != _mapping(accepted_native, "chart"):
            raise Refusal(
                RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
                "The saved Superset chart context changed after validation.",
                {"binding": "chart_context"},
            )
        if database != _mapping(accepted_native, "database"):
            raise Refusal(
                RefusalCode.IDENTITY_NATIVE_OBJECT_RECREATED,
                "The Superset database identity changed after validation.",
                {"binding": "database"},
            )
        _require_current_source(plan, native["dataset"])
        if native["dataset"]["fingerprint"] != accepted_native.get(
            "dataset_fingerprint"
        ):
            raise Refusal(
                RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
                "The Superset dataset fingerprint changed after validation.",
                {"binding": "dataset_fingerprint"},
            )
        try:
            execution_raw, execution = _execute_native(self.client, plan)
        except TimeoutError as exc:
            raise Refusal(
                RefusalCode.RECONCILIATION_REFRESH_TIMEOUT,
                "Superset gate-time saved-chart execution timed out.",
            ) from exc
        current_semantic = _semantic_result(execution_raw)
        if current_semantic != _mapping(accepted_native, "semantic_result"):
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_FAILED,
                "Gate-time saved-chart execution diverged from accepted semantics.",
                {"binding": "semantic_result"},
            )
        _require_semantic_validation(validation, execution)

        observed_at = self.clock().astimezone(UTC)
        trusted = trusted_now.astimezone(UTC)
        validate_trusted_clock(now=trusted, observed_at=observed_at)
        age_seconds = max(0, int((trusted - observed_at).total_seconds()))
        if age_seconds > maximum_age_seconds:
            raise Refusal(
                RefusalCode.EVIDENCE_RECEIPT_EXPIRED,
                "The fresh Superset observation exceeded its permitted age.",
                {
                    "age_seconds": age_seconds,
                    "maximum_age_seconds": maximum_age_seconds,
                },
            )

        artifact_ids = sorted(
            {
                digest_json(native["dataset"]),
                digest_json(chart),
                digest_json(database),
                digest_json(current_semantic),
            }
        )
        observed_timestamp = _timestamp(observed_at)
        evidence_source = {
            "id": expected_source["id"],
            "required": bool(expected_source["required"]),
            "status": "COMPLETE",
            "source_version": expected_source["source_version"],
            "identity": expected_source["identity"],
            "scope": dict(_mapping(expected_source, "scope")),
            "freshness": {
                "observed_at": observed_timestamp,
                "source_updated_at": observed_timestamp,
                "maximum_age_seconds": maximum_age_seconds,
            },
            "permissions": dict(_mapping(expected_source, "permissions")),
            "limitations": list(binding.get("limitations", [])),
            "artifact_ids": artifact_ids,
        }
        observation = with_digest(
            {
                "schema_version": GATE_OBSERVATION_SCHEMA_VERSION,
                "source_id": expected_source["id"],
                "mode": "live",
                "status": "COMPLETE",
                "observed_at": observed_timestamp,
                "maximum_age_seconds": maximum_age_seconds,
                "source_versions": {
                    "adapter": ADAPTER_VERSION,
                    "server": native["server_version"],
                },
                "permissions": dict(_mapping(expected_source, "permissions")),
                "capabilities": {
                    "authenticated_read": True,
                    "dataset_reread": True,
                    "chart_reread": True,
                    "database_reread": True,
                    "forced_saved_chart_execution": True,
                    "mutation": False,
                    "pagination_required": False,
                },
                "scope": dict(_mapping(expected_source, "scope")),
                "evidence_source": evidence_source,
                "native_identity": identity,
                "datahub_native_identity": datahub_identity,
                "current_source_fingerprint": native["dataset"]["fingerprint"],
                "forced_execution_result_digest": digest_json(current_semantic),
                "binding_matches": {
                    "consumer_id": True,
                    "datahub_native_identity": True,
                    "plan_digest": True,
                    "receipt_digest": True,
                    "dataset_id": True,
                    "dataset_uuid": True,
                    "chart_id": True,
                    "chart_uuid": True,
                    "chart_dataset_binding": True,
                    "chart_context": True,
                    "database_id": True,
                    "database_uuid": True,
                    "post_apply_fingerprint": True,
                    "legacy_field_absent": True,
                    "replacement_mapping_exact": True,
                    "server_version": True,
                    "adapter_version": True,
                    "safe_configuration": True,
                    "expected_evidence_source_identity": True,
                    "expected_evidence_source_scope": True,
                    "freshness_window": True,
                    "schema": True,
                    "row_count": True,
                    "ordering_contract": True,
                    "semantic_result_digest": True,
                },
                "artifact_ids": artifact_ids,
                "accepted_binding_digest": binding["binding_digest"],
                "limitations": list(binding.get("limitations", [])),
            },
            "observation_digest",
        )
        if artifact_root is not None:
            write_artifact(artifact_root, "gate-observation", observation)
        return observation


def snapshot_chart(chart: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize the saved-chart identity and executable query context."""

    try:
        identity = {
            "id": int(chart["id"]),
            "uuid": str(chart["uuid"]),
            "dataset_id": int(chart["datasource_id"]),
            "datasource_type": str(chart.get("datasource_type", "table")),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise Refusal(
            RefusalCode.RUNTIME_STATE_DRIFT,
            "Superset returned an unexpected saved-chart identity.",
        ) from exc
    content = {
        "viz_type": chart.get("viz_type"),
        "params": _canonical_json_value(chart.get("params")),
        "query_context": _canonical_json_value(chart.get("query_context")),
        "owners": sorted(
            int(owner["id"])
            for owner in chart.get("owners", [])
            if isinstance(owner, Mapping) and "id" in owner
        ),
    }
    return {
        "identity": identity,
        "content": content,
        "fingerprint": digest_json({"identity": identity, "content": content}),
    }


def snapshot_database(database: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize only public-safe immutable database identity facts."""

    try:
        identity = {"id": int(database["id"]), "uuid": str(database["uuid"])}
    except (KeyError, TypeError, ValueError) as exc:
        raise Refusal(
            RefusalCode.RUNTIME_STATE_DRIFT,
            "Superset returned an unexpected database identity.",
        ) from exc
    if not identity["uuid"]:
        raise Refusal(
            RefusalCode.IDENTITY_NOT_FOUND,
            "Superset did not expose the database UUID.",
        )
    return {"identity": identity, "fingerprint": digest_json(identity)}


def _read_native(
    settings: SupersetSettings,
    client: SupersetGateClient,
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    client.authenticate()
    if client.health().strip() != "OK":
        raise Refusal(
            RefusalCode.SOURCE_NOT_FOUND,
            "Superset health did not return the expected native result.",
        )
    identity = _mapping(plan, "native_identity")
    dataset = snapshot_dataset(client.get_dataset(int(identity["dataset_id"])))
    chart = snapshot_chart(client.get_chart(int(identity["chart_id"])))
    database = snapshot_database(client.get_database(int(identity["database_id"])))
    return {
        "server_version": client.server_version(),
        "dataset": dataset,
        "chart": chart,
        "database": database,
        "safe_configuration": settings.safe_summary(),
    }


def _execute_native(
    client: SupersetGateClient, plan: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    identity = _mapping(plan, "native_identity")
    execution_raw = client.execute_chart(int(identity["chart_id"]))
    execution = inspect_execution(execution_raw)
    if execution["result"] != "PASSED":
        raise Refusal(
            RefusalCode.VALIDATION_RECEIPT_FAILED,
            "Superset failed forced saved-chart execution at gate time.",
        )
    return execution_raw, execution


def _require_accepted_artifacts(
    *,
    consumer_id: str,
    datahub_native_identity: Mapping[str, Any],
    plan: Mapping[str, Any],
    receipt: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> None:
    verify_digest(dict(plan), "plan_digest")
    verify_digest(dict(receipt), "receipt_digest")
    verify_digest(dict(validation), "validation_digest")
    receipt_plan = _mapping(receipt, "plan")
    receipt_apply = _mapping(receipt, "apply")
    receipt_validation = _mapping(receipt, "validation")
    plan_target = _mapping(plan, "target")
    validation_observed = _mapping(validation, "observed")
    expected_urn = datahub_native_identity.get("urn")
    if (
        plan.get("consumer_id") != consumer_id
        or receipt.get("consumer_id") != consumer_id
        or not isinstance(expected_urn, str)
        or plan.get("datahub_urn") != expected_urn
        or receipt.get("datahub_urn") != expected_urn
        or receipt_plan.get("digest") != plan.get("plan_digest")
        or receipt_apply.get("after_fingerprint")
        != plan_target.get("after_fingerprint")
        or receipt_apply.get("actual_targets") != plan.get("proposed_targets")
        or receipt_validation.get("result") != "PASSED"
        or validation.get("result") != "PASSED"
        or validation.get("plan_digest") != plan.get("plan_digest")
        or validation.get("validator_version")
        != receipt_validation.get("validator_version")
        or sorted(validation.get("artifact_ids", []))
        != sorted(receipt_validation.get("artifact_ids", []))
        or any(key not in validation_observed for key in SEMANTIC_KEYS)
    ):
        raise Refusal(
            RefusalCode.INTEGRITY_DIGEST_MISMATCH,
            "Superset gate artifacts are not bound to one accepted migration.",
        )
    adapter = _mapping(receipt, "adapter")
    if (
        adapter.get("name") != "superset"
        or adapter.get("version") != ADAPTER_VERSION
        or adapter.get("mode") != "live"
    ):
        raise Refusal(
            RefusalCode.SOURCE_RECEIPT_VERSION_MISMATCH,
            "The accepted receipt is not from the current live Superset adapter.",
        )


def _require_native_identities(
    identity: Mapping[str, Any],
    dataset: Mapping[str, Any],
    chart: Mapping[str, Any],
    database: Mapping[str, Any],
) -> None:
    dataset_identity = _mapping(dataset, "identity")
    chart_identity = _mapping(chart, "identity")
    database_identity = _mapping(database, "identity")
    checks = {
        "dataset_id": int(dataset_identity["id"]) == int(identity["dataset_id"]),
        "dataset_uuid": str(dataset_identity["uuid"]) == str(identity["dataset_uuid"]),
        "database_id_embedded": int(dataset_identity["database_id"])
        == int(identity["database_id"]),
        "database_uuid_embedded": str(dataset_identity["database_uuid"])
        == str(identity["database_uuid"]),
        "chart_id": int(chart_identity["id"]) == int(identity["chart_id"]),
        "chart_uuid": str(chart_identity["uuid"]) == str(identity["chart_uuid"]),
        "chart_dataset_binding": int(chart_identity["dataset_id"])
        == int(identity["dataset_id"]),
        "database_id": int(database_identity["id"]) == int(identity["database_id"]),
        "database_uuid": str(database_identity["uuid"])
        == str(identity["database_uuid"]),
    }
    mismatches = [name for name, matched in checks.items() if not matched]
    if mismatches:
        raise Refusal(
            RefusalCode.IDENTITY_NATIVE_OBJECT_RECREATED,
            "A Superset native identity or chart binding changed after validation.",
            {"mismatches": mismatches},
        )


def _require_current_source(
    plan: Mapping[str, Any], dataset: Mapping[str, Any]
) -> None:
    target = _mapping(plan, "target")
    content = _mapping(dataset, "content")
    sql = content.get("sql")
    if not isinstance(sql, str):
        raise Refusal(
            RefusalCode.RUNTIME_STATE_DRIFT,
            "Superset did not expose current virtual-dataset SQL.",
        )
    legacy = _string(target, "legacy_field")
    replacement = _string(target, "replacement_field")
    legacy_count = identifier_occurrences(sql, legacy)
    replacement_count = identifier_occurrences(sql, replacement)
    expected_replacement_count = identifier_occurrences(
        _string(target, "after_sql"), replacement
    )
    if legacy_count != 0:
        raise Refusal(
            RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
            "The legacy field reappeared in executable Superset dataset SQL.",
            {"binding": "legacy_field_absent", "occurrences": legacy_count},
        )
    if replacement_count != expected_replacement_count or replacement_count < 1:
        raise Refusal(
            RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
            "The replacement-field mapping changed in Superset dataset SQL.",
            {
                "binding": "replacement_mapping_exact",
                "expected_occurrences": expected_replacement_count,
                "actual_occurrences": replacement_count,
            },
        )
    if dataset.get("fingerprint") != target.get("after_fingerprint"):
        raise Refusal(
            RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
            "The Superset dataset no longer matches the accepted post-apply state.",
            {"binding": "post_apply_fingerprint"},
        )


def _require_semantic_validation(
    validation: Mapping[str, Any], execution: Mapping[str, Any]
) -> None:
    accepted = _mapping(validation, "observed")
    mismatches = [
        key for key in SEMANTIC_KEYS if accepted.get(key) != execution.get(key)
    ]
    if mismatches:
        raise Refusal(
            RefusalCode.VALIDATION_RECEIPT_FAILED,
            "Superset gate-time execution differs from the accepted validation.",
            {"mismatches": mismatches},
        )


def _semantic_result(execution: Mapping[str, Any]) -> dict[str, Any]:
    normalized = inspect_execution(execution)
    data = execution.get("data")
    if not isinstance(data, list) or any(not isinstance(row, Mapping) for row in data):
        raise Refusal(
            RefusalCode.VALIDATION_RECEIPT_INCONCLUSIVE,
            "Superset execution did not expose a complete ordered result.",
        )
    ordered_rows = [dict(row) for row in data]
    return {
        "result": normalized["result"],
        "schema": list(normalized["columns"]),
        "rowcount": normalized["rowcount"],
        "sql_rowcount": normalized["sql_rowcount"],
        "ordering_contract": "exact native row order",
        "ordered_output_digest": digest_json(ordered_rows),
        "safe_output_digest": normalized["safe_output_digest"],
        "query_digest": normalized["query_digest"],
    }


def _require_read_only_settings(settings: SupersetSettings) -> None:
    if settings.allow_apply:
        raise Refusal(
            RefusalCode.AUTH_APPLY_DISABLED,
            "Superset gate verification requires a read-only runtime configuration.",
        )


def _require_evidence_source(
    source: Mapping[str, Any],
    maximum_age_seconds: int,
    *,
    plan: Mapping[str, Any],
    expected_principal: str,
) -> None:
    freshness = _mapping(source, "freshness")
    permissions = _mapping(source, "permissions")
    scope = _mapping(source, "scope")
    identity = _mapping(plan, "native_identity")
    expected_source_id = f"superset:{identity['dataset_uuid']}"
    expected_identity = (
        f"dataset:{identity['dataset_id']}:{identity['dataset_uuid']}:"
        f"chart:{identity['chart_id']}:{identity['chart_uuid']}"
    )
    expected_filters = [
        f"dataset_id:{identity['dataset_id']}",
        f"chart_id:{identity['chart_id']}",
    ]
    if (
        source.get("id") != expected_source_id
        or source.get("required") is not True
        or source.get("status") != "COMPLETE"
        or source.get("source_version") != ADAPTER_VERSION
        or source.get("identity") != expected_identity
        or freshness.get("maximum_age_seconds") != maximum_age_seconds
        or permissions.get("principal") != expected_principal
        or permissions.get("effective_scope") != "read-only"
        or scope.get("direction") != "downstream"
        or scope.get("max_hops") != 1
        or scope.get("filters") != expected_filters
        or scope.get("pages") != 1
        or scope.get("reported_total") != 1
        or scope.get("returned_total") != 1
    ):
        raise Refusal(
            RefusalCode.EVIDENCE_REQUIRED_SOURCE_INCOMPLETE,
            "The expected Superset evidence source is not complete and read-only.",
        )


def _mapping(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, Mapping):
        raise Refusal(
            RefusalCode.INTEGRITY_DIGEST_MISMATCH,
            f"Superset gate artifact is missing mapping field {key}.",
        )
    return dict(item)


def _string(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise Refusal(
            RefusalCode.INTEGRITY_DIGEST_MISMATCH,
            f"Superset gate artifact is missing string field {key}.",
        )
    return item


def _positive_int(value: Mapping[str, Any], key: str) -> int:
    item = value.get(key)
    if not isinstance(item, int) or isinstance(item, bool) or item < 1:
        raise Refusal(
            RefusalCode.INTEGRITY_DIGEST_MISMATCH,
            f"Superset gate artifact is missing positive integer field {key}.",
        )
    return item


def _canonical_json_value(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise Refusal(
                RefusalCode.RUNTIME_STATE_DRIFT,
                "Superset returned invalid saved-chart JSON context.",
            ) from exc
        return parsed
    if isinstance(value, (Mapping, list)):
        return value
    raise Refusal(
        RefusalCode.RUNTIME_STATE_DRIFT,
        "Superset returned an unexpected saved-chart context value.",
    )


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
