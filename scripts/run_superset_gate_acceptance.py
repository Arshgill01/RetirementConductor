#!/usr/bin/env python3
"""Run the CP-02 live-local Superset gate-time drift matrix."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any, cast
from urllib.error import URLError
from urllib.request import urlopen

from retirement_conductor.canonical import digest_json, with_digest, write_json
from retirement_conductor.errors import Refusal
from retirement_conductor.superset import (
    SupersetAdapter,
    SupersetClient,
    inspect_execution,
    snapshot_dataset,
)
from retirement_conductor.superset_config import SupersetSettings
from retirement_conductor.superset_gate import (
    SupersetGateVerifier,
    capture_superset_gate_binding,
    snapshot_chart,
    snapshot_database,
)
from retirement_conductor.vocabulary import RefusalCode

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = ROOT / ".retirement-conductor/superset-gate-refresh"
PUBLIC_ROOT = ROOT / "artifacts/public/superset-gate-refresh"
MAXIMUM_AGE_SECONDS = 300


class AuditedSupersetClient(SupersetClient):
    """Count native object mutation calls made through one client."""

    def __init__(self, settings: SupersetSettings) -> None:
        super().__init__(settings)
        self.calls: list[tuple[str, str]] = []
        self.corrupt_chart_shape = False
        self.server_version_override: str | None = None

    @property
    def mutation_call_count(self) -> int:
        return sum(
            method in {"PUT", "PATCH", "DELETE"}
            or (method == "POST" and path != "/api/v1/security/login")
            for method, path in self.calls
        )

    def get_chart(self, chart_id: int) -> dict[str, Any]:
        chart = super().get_chart(chart_id)
        if self.corrupt_chart_shape:
            chart.pop("uuid", None)
        return chart

    def server_version(self) -> str:
        if self.server_version_override is not None:
            return self.server_version_override
        return super().server_version()

    def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
        *,
        authenticated: bool = True,
        expect_json: bool = True,
    ) -> dict[str, Any] | str:
        self.calls.append((method, path))
        return super()._request(
            method,
            path,
            payload,
            authenticated=authenticated,
            expect_json=expect_json,
        )


def _gate_settings(admin: SupersetSettings) -> SupersetSettings:
    username = os.environ.get("SUPERSET_GATE_USERNAME", "").strip()
    password = os.environ.get("SUPERSET_GATE_PASSWORD", "")
    if not username or not password:
        raise RuntimeError("SUPERSET_GATE_USERNAME and SUPERSET_GATE_PASSWORD required")
    return SupersetSettings(
        base_url=admin.base_url,
        username=username,
        password=password,
        provider=admin.provider,
        principal="local-read-only-verifier",
        version=admin.version,
        allow_apply=False,
        allowed_dataset_ids=admin.allowed_dataset_ids,
        timeout_seconds=2,
    )


def _source(identity: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": f"superset:{identity['dataset_uuid']}",
        "required": True,
        "status": "COMPLETE",
        "source_version": "0.1.0",
        "identity": (
            f"dataset:{identity['dataset_id']}:{identity['dataset_uuid']}:"
            f"chart:{identity['chart_id']}:{identity['chart_uuid']}"
        ),
        "scope": {
            "direction": "downstream",
            "max_hops": 1,
            "filters": [
                f"dataset_id:{identity['dataset_id']}",
                f"chart_id:{identity['chart_id']}",
            ],
            "pages": 1,
            "reported_total": 1,
            "returned_total": 1,
        },
        "freshness": {
            "observed_at": _now(),
            "source_updated_at": None,
            "maximum_age_seconds": MAXIMUM_AGE_SECONDS,
        },
        "permissions": {
            "principal": "local-read-only-verifier",
            "effective_scope": "read-only",
        },
        "limitations": [
            "The official Superset connector supports table-level lineage.",
            "Native SQL and execution establish the exact field fact.",
        ],
        "artifact_ids": [],
    }


def _native_state(client: SupersetClient, identity: Mapping[str, Any]) -> str:
    return digest_json(
        {
            "dataset": snapshot_dataset(
                client.get_dataset(int(identity["dataset_id"]))
            ),
            "chart": snapshot_chart(client.get_chart(int(identity["chart_id"]))),
            "database": snapshot_database(
                client.get_database(int(identity["database_id"]))
            ),
            "execution": inspect_execution(
                client.execute_chart(int(identity["chart_id"]))
            ),
        }
    )


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True, text=True, capture_output=True)


def _sql(container: str, statement: str) -> None:
    _run(
        [
            "docker",
            "exec",
            container,
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "superset",
            "-d",
            "superset",
            "-c",
            statement,
        ]
    )


def _wait_for_health(base_url: str) -> None:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            with urlopen(f"{base_url}/health", timeout=2) as response:
                if response.read().decode("utf-8") == "OK":
                    return
        except (OSError, URLError):
            pass
        time.sleep(1)
    raise RuntimeError("Superset did not return to healthy state")


def run() -> dict[str, Any]:
    PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)
    PUBLIC_ROOT.mkdir(parents=True, exist_ok=True)
    admin_settings = SupersetSettings.from_environment()
    if not admin_settings.allow_apply:
        raise RuntimeError("live acceptance requires SUPERSET_ALLOW_APPLY=true")
    read_settings = _gate_settings(admin_settings)
    app_container = os.environ.get("SUPERSET_APP_CONTAINER", "rc_cp02-app-1")
    database_container = os.environ.get("SUPERSET_DB_CONTAINER", "rc_cp02-db-1")

    admin = SupersetClient(admin_settings)
    admin.authenticate()
    gate = AuditedSupersetClient(read_settings)
    dataset_id = min(admin_settings.allowed_dataset_ids)
    chart_id = int(os.environ.get("SUPERSET_GATE_CHART_ID", "1"))
    dataset = admin.get_dataset(dataset_id)
    database_id = int(cast(Mapping[str, Any], dataset["database"])["id"])
    datahub_urn = (
        "urn:li:dataset:(urn:li:dataPlatform:superset,"
        "CP02.public.ws04_status_by_order,PROD)"
    )
    datahub_identity = {
        "urn": datahub_urn,
        "external_url": (
            f"{admin_settings.base_url}/explore/"
            f"?datasource_type=table&datasource_id={dataset_id}"
        ),
        "mapping_basis": "official connector URL datasource_id plus native UUID",
    }
    adapter = SupersetAdapter(admin_settings, admin)
    preflight = adapter.preflight(
        datahub_entities=[datahub_identity],
        dataset_id=dataset_id,
        chart_id=chart_id,
        legacy_field="legacy_status",
        replacement_field="order_status",
        artifact_root=PRIVATE_ROOT / "accepted/preflight",
    )
    plan = adapter.plan(
        preflight,
        campaign_id="ret-orders-cp02",
        consumer_id="consumer-superset-cp02",
        allow_semantic_change=False,
        artifact_root=PRIVATE_ROOT / "accepted",
    )
    apply_record = adapter.apply(
        plan,
        confirmed_plan_digest=str(plan["plan_digest"]),
        artifact_root=PRIVATE_ROOT / "accepted",
    )
    validation = adapter.validate(
        plan,
        apply_record,
        artifact_root=PRIVATE_ROOT / "accepted/validation",
    )
    receipt = adapter.emit_receipt(
        plan,
        apply_record,
        validation,
        compensation=None,
        artifact_root=PRIVATE_ROOT / "accepted",
    )
    captured_at = _now()
    source = _source(plan["native_identity"])
    binding = capture_superset_gate_binding(
        settings=read_settings,
        client=gate,
        consumer_id=str(plan["consumer_id"]),
        datahub_native_identity=datahub_identity,
        plan=plan,
        receipt=receipt,
        validation=validation,
        expected_evidence_source=source,
        captured_at=captured_at,
        maximum_age_seconds=MAXIMUM_AGE_SECONDS,
        artifact_root=PRIVATE_ROOT / "accepted",
    )
    identity = dict(plan["native_identity"])
    accepted_dataset = admin.get_dataset(dataset_id)
    accepted_chart = admin.get_chart(chart_id)
    state_before = _native_state(admin, identity)
    gate.calls.clear()
    unchanged = SupersetGateVerifier(settings=read_settings, client=gate).verify(
        binding,
        trusted_now=datetime.now(UTC),
        artifact_root=PRIVATE_ROOT / "unchanged-a",
    )
    repeated = SupersetGateVerifier(settings=read_settings, client=gate).verify(
        binding,
        trusted_now=datetime.now(UTC),
        artifact_root=PRIVATE_ROOT / "unchanged-b",
    )
    state_after = _native_state(admin, identity)
    if state_before != state_after:
        raise RuntimeError("read-only unchanged verification changed native state")
    if gate.mutation_call_count != 0:
        raise RuntimeError("gate verifier called a native mutation API")

    try:
        gate.update_dataset(dataset_id, str(accepted_dataset["sql"]))
    except Refusal as exc:
        read_only_mutation_refusal = {
            "code": str(exc.code),
            "http_status": exc.details.get("http_status"),
        }
    else:
        raise RuntimeError("read-only verifier principal unexpectedly mutated dataset")
    gate.calls.clear()

    _run(
        [
            "docker",
            "exec",
            database_container,
            "pg_dump",
            "-U",
            "superset",
            "-d",
            "superset",
            "-Fc",
            "-f",
            "/tmp/cp02-gate-accepted.dump",
        ]
    )
    clients: dict[str, SupersetClient] = {"admin": admin, "gate": gate}
    matrix: list[dict[str, Any]] = []

    def current_admin() -> SupersetClient:
        return clients["admin"]

    def current_gate() -> AuditedSupersetClient:
        return cast(AuditedSupersetClient, clients["gate"])

    def refresh_clients() -> None:
        new_admin = SupersetClient(admin_settings)
        new_admin.authenticate()
        clients["admin"] = new_admin
        clients["gate"] = AuditedSupersetClient(read_settings)

    def verify_current(
        *,
        candidate_binding: Mapping[str, Any] | None = None,
        candidate_client: AuditedSupersetClient | None = None,
        trusted_now: datetime | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> dict[str, Any]:
        verifier = SupersetGateVerifier(
            settings=read_settings,
            client=candidate_client or current_gate(),
            clock=clock,
        )
        return verifier.verify(
            candidate_binding or binding,
            trusted_now=trusted_now or datetime.now(UTC),
        )

    def restore_dataset() -> None:
        current_admin()._request(
            "PUT",
            f"/api/v1/dataset/{dataset_id}",
            {
                "sql": accepted_dataset["sql"],
                "owners": [int(owner["id"]) for owner in accepted_dataset["owners"]],
            },
        )

    def set_dataset_sql(sql: str) -> None:
        current_admin().update_dataset(dataset_id, sql)

    def set_dataset_owners(owner_ids: list[int]) -> None:
        current_admin()._request(
            "PUT", f"/api/v1/dataset/{dataset_id}", {"owners": owner_ids}
        )

    def set_uuid(table: str, native_id: int, value: str) -> None:
        _sql(
            database_container,
            f"UPDATE {table} SET uuid='{value}' WHERE id={native_id};",
        )

    def restore_chart() -> None:
        current_admin()._request(
            "PUT",
            f"/api/v1/chart/{chart_id}",
            {
                "datasource_id": accepted_chart["datasource_id"],
                "datasource_type": accepted_chart.get("datasource_type", "table"),
                "viz_type": accepted_chart.get("viz_type"),
                "params": accepted_chart.get("params"),
                "query_context": accepted_chart.get("query_context"),
                "owners": [int(owner["id"]) for owner in accepted_chart["owners"]],
            },
        )

    def restore_dump() -> None:
        _run(["docker", "stop", app_container])
        try:
            _run(
                [
                    "docker",
                    "exec",
                    database_container,
                    "pg_restore",
                    "--clean",
                    "--if-exists",
                    "--no-owner",
                    "-U",
                    "superset",
                    "-d",
                    "superset",
                    "/tmp/cp02-gate-accepted.dump",
                ]
            )
        finally:
            _run(["docker", "start", app_container])
        _wait_for_health(admin_settings.base_url)
        refresh_clients()

    def refusal_case(
        name: str,
        *,
        inject: Callable[[], None],
        restore: Callable[[], None],
        expected_code: RefusalCode,
        category: str,
        evidence_mode: str = "live native drift",
        candidate_binding: Callable[[], Mapping[str, Any]] | None = None,
        candidate_client: Callable[[], AuditedSupersetClient] | None = None,
        trusted_now: Callable[[], datetime] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        inject()
        refusal: Refusal | None = None
        calls_before = current_gate().mutation_call_count
        try:
            verify_current(
                candidate_binding=(candidate_binding() if candidate_binding else None),
                candidate_client=(candidate_client() if candidate_client else None),
                trusted_now=(trusted_now() if trusted_now else None),
                clock=clock,
            )
        except Refusal as exc:
            refusal = exc
        finally:
            restore()
        if refusal is None or refusal.code != expected_code:
            raise RuntimeError(
                f"{name} expected {expected_code}, observed "
                f"{None if refusal is None else refusal.code}"
            )
        if current_gate().mutation_call_count != calls_before:
            raise RuntimeError(f"{name} caused a verifier mutation call")
        verify_current()
        matrix.append(
            {
                "case": name,
                "result": "REFUSED",
                "refusal_code": str(refusal.code),
                "category": category,
                "evidence_mode": evidence_mode,
                "restored_before_next_case": True,
                "verification_mutation_calls": 0,
            }
        )

    target = dict(plan["target"])
    refusal_case(
        "dataset_sql_changed",
        inject=lambda: set_dataset_sql(f"{target['after_sql']} WHERE id > 0"),
        restore=restore_dataset,
        expected_code=RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
        category="source_mismatch",
    )
    refusal_case(
        "legacy_field_reintroduced",
        inject=lambda: set_dataset_sql(str(target["before_sql"])),
        restore=restore_dataset,
        expected_code=RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
        category="source_mismatch",
    )
    refusal_case(
        "replacement_mapping_changed",
        inject=lambda: set_dataset_sql(
            str(target["after_sql"]).replace("order_status", "amount")
        ),
        restore=restore_dataset,
        expected_code=RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
        category="source_mismatch",
    )

    other_dataset = cast(
        Mapping[str, Any],
        current_admin()._request(
            "POST",
            "/api/v1/dataset/",
            {
                "database": database_id,
                "schema": "public",
                "table_name": "cp02_other_dataset",
                "sql": target["after_sql"],
                "owners": [1],
            },
        ),
    )
    other_dataset_id = int(other_dataset["id"])

    def move_chart() -> None:
        current_admin()._request(
            "PUT",
            f"/api/v1/chart/{chart_id}",
            {"datasource_id": other_dataset_id, "datasource_type": "table"},
        )

    def restore_moved_chart() -> None:
        restore_chart()
        current_admin()._request("DELETE", f"/api/v1/dataset/{other_dataset_id}")

    refusal_case(
        "chart_moved_to_another_dataset",
        inject=move_chart,
        restore=restore_moved_chart,
        expected_code=RefusalCode.IDENTITY_NATIVE_OBJECT_RECREATED,
        category="identity_mismatch",
    )

    def drift_chart_context() -> None:
        context = json.loads(str(accepted_chart["query_context"]))
        context["queries"][0]["row_limit"] = 1
        current_admin()._request(
            "PUT",
            f"/api/v1/chart/{chart_id}",
            {
                "params": json.dumps({"row_limit": 1}),
                "query_context": json.dumps(
                    context, sort_keys=True, separators=(",", ":")
                ),
            },
        )

    refusal_case(
        "chart_context_and_semantic_output_changed",
        inject=drift_chart_context,
        restore=restore_chart,
        expected_code=RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
        category="source_mismatch",
    )

    uuid_drift = "00000000-0000-0000-0000-000000000002"
    for name, table, native_id, restore_uuid in (
        ("dataset_uuid_mismatch", "tables", dataset_id, identity["dataset_uuid"]),
        ("chart_uuid_mismatch", "slices", chart_id, identity["chart_uuid"]),
        (
            "database_uuid_mismatch",
            "dbs",
            database_id,
            identity["database_uuid"],
        ),
    ):
        refusal_case(
            name,
            inject=partial(set_uuid, table, native_id, uuid_drift),
            restore=partial(set_uuid, table, native_id, str(restore_uuid)),
            expected_code=RefusalCode.IDENTITY_NATIVE_OBJECT_RECREATED,
            category="identity_mismatch",
        )

    refusal_case(
        "intervening_owner_edit",
        inject=lambda: set_dataset_owners([1, 2]),
        restore=restore_dataset,
        expected_code=RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
        category="source_mismatch",
    )

    def delete_chart() -> None:
        current_admin()._request("DELETE", f"/api/v1/chart/{chart_id}")

    def delete_dataset() -> None:
        delete_chart()
        current_admin()._request("DELETE", f"/api/v1/dataset/{dataset_id}")

    def delete_database() -> None:
        delete_dataset()
        current_admin()._request("DELETE", f"/api/v1/database/{database_id}")

    for name, delete in (
        ("chart_deleted", delete_chart),
        ("dataset_deleted", delete_dataset),
        ("database_deleted", delete_database),
    ):
        refusal_case(
            name,
            inject=delete,
            restore=restore_dump,
            expected_code=RefusalCode.SOURCE_NOT_FOUND,
            category="source_mismatch",
        )

    wrong_password = SupersetSettings(
        **{**read_settings.__dict__, "password": "deliberately-wrong"}
    )
    refusal_case(
        "authentication_failure",
        inject=lambda: None,
        restore=lambda: None,
        expected_code=RefusalCode.SOURCE_DATAHUB_PERMISSION_DENIED,
        category="source_unavailable",
        candidate_client=lambda: AuditedSupersetClient(wrong_password),
    )

    refusal_case(
        "read_permission_removed",
        inject=lambda: _sql(
            database_container,
            (
                "DELETE FROM ab_user_role USING ab_user "
                "WHERE ab_user_role.user_id=ab_user.id "
                "AND ab_user.username='gate-verifier';"
            ),
        ),
        restore=restore_dump,
        expected_code=RefusalCode.SOURCE_DATAHUB_PERMISSION_DENIED,
        category="source_unavailable",
        candidate_client=lambda: AuditedSupersetClient(read_settings),
    )

    def stop_app() -> None:
        _run(["docker", "stop", app_container])

    def start_app() -> None:
        _run(["docker", "start", app_container])
        _wait_for_health(admin_settings.base_url)
        refresh_clients()

    refusal_case(
        "superset_outage",
        inject=stop_app,
        restore=start_app,
        expected_code=RefusalCode.SOURCE_NOT_FOUND,
        category="source_unavailable",
    )

    refusal_case(
        "superset_timeout",
        inject=lambda: _run(["docker", "pause", app_container]),
        restore=lambda: _run(["docker", "unpause", app_container]),
        expected_code=RefusalCode.RECONCILIATION_REFRESH_TIMEOUT,
        category="source_unavailable",
    )

    malformed = AuditedSupersetClient(read_settings)
    malformed.corrupt_chart_shape = True
    refusal_case(
        "unexpected_response_shape",
        inject=lambda: None,
        restore=lambda: None,
        expected_code=RefusalCode.RUNTIME_STATE_DRIFT,
        category="source_unavailable",
        evidence_mode="live-local response fault injection",
        candidate_client=lambda: malformed,
    )

    tampered_receipt = copy.deepcopy(binding)
    tampered_receipt["accepted_receipt"]["tampered"] = True
    tampered_receipt = with_digest(tampered_receipt, "binding_digest")
    refusal_case(
        "accepted_receipt_tampered",
        inject=lambda: None,
        restore=lambda: None,
        expected_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
        category="evidence_mismatch",
        evidence_mode="artifact integrity fault injection",
        candidate_binding=lambda: tampered_receipt,
    )
    tampered_validation = copy.deepcopy(binding)
    tampered_validation["accepted_validation"]["observed"]["rowcount"] = 7
    tampered_validation = with_digest(tampered_validation, "binding_digest")
    refusal_case(
        "semantic_artifact_tampered",
        inject=lambda: None,
        restore=lambda: None,
        expected_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
        category="evidence_mismatch",
        evidence_mode="artifact integrity fault injection",
        candidate_binding=lambda: tampered_validation,
    )

    version_drift = AuditedSupersetClient(read_settings)
    version_drift.server_version_override = "6.0.1"
    refusal_case(
        "server_version_drift",
        inject=lambda: None,
        restore=lambda: None,
        expected_code=RefusalCode.SOURCE_RECEIPT_VERSION_MISMATCH,
        category="source_mismatch",
        evidence_mode="live-local response fault injection",
        candidate_client=lambda: version_drift,
    )

    stale_observed_at = datetime.now(UTC)
    refusal_case(
        "stale_observation",
        inject=lambda: None,
        restore=lambda: None,
        expected_code=RefusalCode.EVIDENCE_RECEIPT_EXPIRED,
        category="evidence_mismatch",
        trusted_now=lambda: (
            stale_observed_at + timedelta(seconds=MAXIMUM_AGE_SECONDS + 1)
        ),
        clock=lambda: stale_observed_at,
    )

    final_observation = verify_current()
    final_state = _native_state(current_admin(), identity)
    if final_state != state_before:
        raise RuntimeError("drift matrix did not restore the accepted native state")
    compensation = adapter.compensate(
        plan,
        apply_record,
        artifact_root=PRIVATE_ROOT / "compensation",
    )

    verification_calls = [
        {"method": method, "operation": path.split("?")[0]}
        for method, path in gate.calls
        if method == "GET"
    ]
    evidence = with_digest(
        {
            "schema_version": "1.0.0",
            "result": "KEEP",
            "evidence_mode": "live local",
            "superset": {
                "version": "6.0.0",
                "image": (
                    "apache/superset:6.0.0-dev@"
                    "sha256:100af35c5a3c96384d4092ae4bd7fffb8c23d361e9a5a8b94312c50426aa1144"
                ),
                "adapter_version": "0.1.0",
                "endpoint_scope": "loopback disposable Superset",
                "read_only_principal": "local-read-only-verifier",
                "read_only_mutation_probe": read_only_mutation_refusal,
            },
            "accepted": {
                "plan_digest": plan["plan_digest"],
                "receipt_digest": receipt["receipt_digest"],
                "validation_digest": validation["validation_digest"],
                "binding_digest": binding["binding_digest"],
                "post_apply_fingerprint": target["after_fingerprint"],
            },
            "unchanged_control": {
                "observation_digest": unchanged["observation_digest"],
                "repeated_observation_digest": repeated["observation_digest"],
                "final_observation_digest": final_observation["observation_digest"],
                "native_state_before_digest": state_before,
                "native_state_after_digest": state_after,
                "native_state_after_matrix_digest": final_state,
                "all_binding_matches": all(unchanged["binding_matches"].values()),
                "direct_native_reread": True,
                "forced_saved_chart_execution": True,
                "verification_get_calls": verification_calls,
                "verification_mutation_call_count": 0,
            },
            "refusal_matrix": matrix,
            "refusal_case_count": len(matrix),
            "datahub_relationship": {
                "native_identity_digest": digest_json(datahub_identity),
                "binding": (
                    "current DataHub membership and exact Superset identity join "
                    "the accepted receipt to this native observation"
                ),
                "graph_authority": "DataHub membership and cross-system identity",
                "native_authority": "Superset SQL and forced execution",
                "limitation": (
                    "The official connector is table-lineage capable; any exact "
                    "field edge remains corroborative and cannot replace native SQL."
                ),
            },
            "compensation": {
                "result": compensation["result"],
                "digest": compensation["compensation_digest"],
            },
            "sensitive_values_recorded": False,
            "limitations": [
                "Evidence is live-local against a disposable service, not production.",
                (
                    "CP-02 returns evidence only; CP-05 owns deterministic gate "
                    "integration."
                ),
                "DataHub's separate fresh graph inventory remains mandatory.",
                "One unexpected-shape case uses a response-boundary fault injector.",
            ],
        },
        "evidence_digest",
    )
    write_json(PUBLIC_ROOT / "evidence.json", evidence)
    index = with_digest(
        {
            "schema_version": "1.0.0",
            "result": evidence["result"],
            "evidence_digest": evidence["evidence_digest"],
            "files": ["evidence.json", "README.md"],
            "superset_version": "6.0.0",
            "connector_version": "1.6.0",
            "refusal_case_count": len(matrix),
            "verification_mutation_call_count": 0,
            "limitations": evidence["limitations"],
        },
        "index_digest",
    )
    write_json(PUBLIC_ROOT / "index.json", index)
    return index


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def main() -> int:
    result = run()
    print(
        f"{result['result']}: refusals={result['refusal_case_count']} "
        f"index={result['index_digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
