"""Bounded Apache Superset identity, mutation, validation, and recovery."""

from __future__ import annotations

import json
import re
import socket
from collections.abc import Mapping, Sequence
from contextlib import suppress
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener

from retirement_conductor.canonical import (
    digest_json,
    verify_digest,
    with_digest,
    write_json,
)
from retirement_conductor.datahub import ArtifactWriter, utc_now
from retirement_conductor.errors import Refusal
from retirement_conductor.schemas import validate_schema
from retirement_conductor.superset_config import SupersetSettings
from retirement_conductor.vocabulary import RefusalCode

ADAPTER_VERSION = "0.1.0"
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DOLLAR_QUOTE = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$")


class SupersetClientProtocol(Protocol):
    def authenticate(self) -> None: ...

    def health(self) -> str: ...

    def get_dataset(self, dataset_id: int) -> dict[str, Any]: ...

    def update_dataset(self, dataset_id: int, sql: str) -> dict[str, Any]: ...

    def get_chart(self, chart_id: int) -> dict[str, Any]: ...

    def execute_chart(self, chart_id: int) -> dict[str, Any]: ...


class SupersetClient:
    """Small authenticated client for only the Superset APIs this executor uses."""

    def __init__(self, settings: SupersetSettings) -> None:
        self.settings = settings
        self._opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self._token = ""
        self._csrf = ""

    def authenticate(self) -> None:
        response = cast(
            dict[str, Any],
            self._request(
                "POST",
                "/api/v1/security/login",
                {
                    "username": self.settings.username,
                    "password": self.settings.password,
                    "provider": self.settings.provider,
                    "refresh": True,
                },
                authenticated=False,
            ),
        )
        token = response.get("access_token")
        if not isinstance(token, str) or not token:
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_PERMISSION_DENIED,
                "Superset authentication did not return a bearer token.",
            )
        self._token = token
        csrf = cast(
            dict[str, Any],
            self._request("GET", "/api/v1/security/csrf_token/"),
        ).get("result")
        if not isinstance(csrf, str) or not csrf:
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_PERMISSION_DENIED,
                "Superset authentication did not return a CSRF token.",
            )
        self._csrf = csrf

    def health(self) -> str:
        value = self._request("GET", "/health", expect_json=False)
        return str(value)

    def get_dataset(self, dataset_id: int) -> dict[str, Any]:
        value = cast(
            dict[str, Any], self._request("GET", f"/api/v1/dataset/{dataset_id}")
        )
        return self._result(value)

    def update_dataset(self, dataset_id: int, sql: str) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            self._request("PUT", f"/api/v1/dataset/{dataset_id}", {"sql": sql}),
        )

    def get_chart(self, chart_id: int) -> dict[str, Any]:
        value = cast(dict[str, Any], self._request("GET", f"/api/v1/chart/{chart_id}"))
        return self._result(value)

    def get_database(self, database_id: int) -> dict[str, Any]:
        value = cast(
            dict[str, Any],
            self._request("GET", f"/api/v1/database/{database_id}"),
        )
        return self._result(value)

    def server_version(self) -> str:
        value = cast(dict[str, Any], self._request("GET", "/static/version_info.json"))
        version = value.get("version")
        if not isinstance(version, str) or not version.strip():
            raise Refusal(
                RefusalCode.RUNTIME_STATE_DRIFT,
                "Superset returned an unexpected server-version response.",
            )
        return version.strip()

    def execute_chart(self, chart_id: int) -> dict[str, Any]:
        value = cast(
            dict[str, Any],
            self._request("GET", f"/api/v1/chart/{chart_id}/data/?force=true"),
        ).get("result")
        if (
            not isinstance(value, list)
            or len(value) != 1
            or not isinstance(value[0], dict)
        ):
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_INCONCLUSIVE,
                "Superset returned an unexpected chart execution envelope.",
            )
        return dict(value[0])

    @staticmethod
    def _result(value: Mapping[str, Any]) -> dict[str, Any]:
        result = value.get("result")
        if not isinstance(result, dict):
            raise Refusal(
                RefusalCode.SOURCE_NOT_FOUND,
                "Superset returned an unexpected native object envelope.",
            )
        return dict(result)

    def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
        *,
        authenticated: bool = True,
        expect_json: bool = True,
    ) -> dict[str, Any] | str:
        headers = {"Accept": "application/json"}
        if authenticated and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if method in {"POST", "PUT", "PATCH", "DELETE"} and self._csrf:
            headers["X-CSRFToken"] = self._csrf
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.settings.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with self._opener.open(
                request, timeout=self.settings.timeout_seconds
            ) as response:
                raw = cast(bytes, response.read())
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise Refusal(
                    RefusalCode.SOURCE_DATAHUB_PERMISSION_DENIED,
                    "The Superset principal lacks the required native API capability.",
                    {"http_status": exc.code, "operation": f"{method} {path}"},
                ) from exc
            if exc.code == 404:
                raise Refusal(
                    RefusalCode.SOURCE_NOT_FOUND,
                    "The exact Superset native object was not found.",
                    {"operation": f"{method} {path}"},
                ) from exc
            raise Refusal(
                RefusalCode.RUNTIME_STATE_DRIFT,
                "Superset rejected the bounded native API operation.",
                {"http_status": exc.code, "operation": f"{method} {path}"},
            ) from exc
        except TimeoutError as exc:
            raise TimeoutError(f"{method} {path}") from exc
        except URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise TimeoutError(f"{method} {path}") from exc
            raise Refusal(
                RefusalCode.SOURCE_NOT_FOUND,
                "The disposable Superset endpoint is unavailable.",
            ) from exc
        if not expect_json:
            return raw.decode("utf-8", errors="replace")
        try:
            value = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise Refusal(
                RefusalCode.RUNTIME_STATE_DRIFT,
                "Superset returned a non-JSON native API response.",
            ) from exc
        if not isinstance(value, dict):
            raise Refusal(
                RefusalCode.RUNTIME_STATE_DRIFT,
                "Superset returned a non-object native API response.",
            )
        return cast(dict[str, Any], value)


class SupersetAdapter:
    """One exact virtual dataset mutation with forced chart validation."""

    def __init__(
        self,
        settings: SupersetSettings,
        client: SupersetClientProtocol | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or SupersetClient(settings)

    def preflight(
        self,
        *,
        datahub_entities: Sequence[Mapping[str, Any]],
        dataset_id: int,
        chart_id: int,
        legacy_field: str,
        replacement_field: str,
        artifact_root: Path,
    ) -> dict[str, Any]:
        self._validate_fields(legacy_field, replacement_field)
        self._require_allowed(dataset_id)
        self.client.authenticate()
        if self.client.health().strip() != "OK":
            raise Refusal(
                RefusalCode.SOURCE_NOT_FOUND,
                "Superset health did not return the expected native result.",
            )
        matches = [
            dict(entity)
            for entity in datahub_entities
            if dataset_id_from_datahub(entity) == dataset_id
        ]
        if len(matches) != 1:
            code = (
                RefusalCode.IDENTITY_NOT_FOUND
                if not matches
                else RefusalCode.IDENTITY_AMBIGUOUS
            )
            raise Refusal(
                code,
                "DataHub did not map one-to-one to the requested Superset dataset.",
                {"match_count": len(matches), "dataset_id": dataset_id},
            )
        dataset = self.client.get_dataset(dataset_id)
        chart = self.client.get_chart(chart_id)
        if int(chart.get("datasource_id", 0)) != dataset_id:
            raise Refusal(
                RefusalCode.IDENTITY_AMBIGUOUS,
                "The selected chart does not use the exact allowlisted dataset.",
            )
        snapshot = snapshot_dataset(dataset)
        sql = str(snapshot["content"]["sql"])
        if identifier_occurrences(sql, legacy_field) != 1:
            raise Refusal(
                RefusalCode.IDENTITY_FIELD_AMBIGUOUS,
                (
                    "The native dataset SQL must contain exactly one legacy "
                    "field reference."
                ),
                {"occurrences": identifier_occurrences(sql, legacy_field)},
            )
        execution = inspect_execution(self.client.execute_chart(chart_id))
        if execution["result"] != "PASSED":
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_FAILED,
                "The before-state chart failed forced native execution.",
            )
        writer = ArtifactWriter(artifact_root)
        snapshot_artifact = writer.write("superset-before-snapshot", snapshot)
        execution_artifact = writer.write("superset-before-execution", execution)
        datahub = matches[0]
        result = with_digest(
            {
                "schema_version": "1.0.0",
                "mode": "live",
                "captured_at": utc_now(),
                "source_version": self.settings.version,
                "principal": self.settings.principal,
                "capabilities": {
                    "read": True,
                    "plan": True,
                    "apply": self.settings.allow_apply,
                    "validate": True,
                    "compensate": self.settings.allow_apply,
                },
                "native_identity": {
                    "dataset_id": dataset_id,
                    "dataset_uuid": snapshot["identity"]["uuid"],
                    "database_id": snapshot["identity"]["database_id"],
                    "database_uuid": snapshot["identity"]["database_uuid"],
                    "chart_id": chart_id,
                    "chart_uuid": str(chart.get("uuid", "")),
                },
                "datahub_identity": {
                    "urn": datahub["urn"],
                    "external_url": datahub["external_url"],
                    "mapping_basis": (
                        "connector URL datasource_id followed by native UUID reread"
                    ),
                    "match_count": 1,
                },
                "legacy_field": legacy_field,
                "replacement_field": replacement_field,
                "snapshot": snapshot,
                "baseline_execution": execution,
                "limitations": [
                    (
                        "DataHub documents Superset table-level lineage as the "
                        "supported capability"
                    ),
                    (
                        "Any observed parser-derived field edge is corroboration "
                        "for this SQL only"
                    ),
                    (
                        "Direct native dataset SQL is authoritative for exact "
                        "field dependence"
                    ),
                ],
                "artifact_ids": [snapshot_artifact, execution_artifact],
            },
            "preflight_digest",
        )
        write_artifact(artifact_root, "preflight", result)
        return result

    def plan(
        self,
        preflight: Mapping[str, Any],
        *,
        campaign_id: str,
        consumer_id: str,
        allow_semantic_change: bool,
        artifact_root: Path,
    ) -> dict[str, Any]:
        verify_digest(dict(preflight), "preflight_digest")
        before = dict(preflight["snapshot"])
        before_content = dict(before["content"])
        legacy = str(preflight["legacy_field"])
        replacement = str(preflight["replacement_field"])
        after_sql = replace_identifier_once(
            str(before_content["sql"]), legacy, replacement
        )
        after_content = {**before_content, "sql": after_sql}
        after_fingerprint = digest_json(
            {"identity": before["identity"], "content": after_content}
        )
        identity = dict(preflight["native_identity"])
        target = native_target(identity)
        plan = with_digest(
            {
                "schema_version": "1.0.0",
                "campaign_id": campaign_id,
                "consumer_id": consumer_id,
                "datahub_urn": preflight["datahub_identity"]["urn"],
                "source_version": preflight["source_version"],
                "native_identity": identity,
                "target": {
                    "native_object": target,
                    "before_sql": before_content["sql"],
                    "after_sql": after_sql,
                    "before_fingerprint": before["fingerprint"],
                    "after_fingerprint": after_fingerprint,
                    "legacy_field": legacy,
                    "replacement_field": replacement,
                },
                "validation": {
                    "chart_id": identity["chart_id"],
                    "baseline": preflight["baseline_execution"],
                    "allow_semantic_change": allow_semantic_change,
                },
                "compensation": {
                    "requires_fingerprint": after_fingerprint,
                    "restores_fingerprint": before["fingerprint"],
                },
                "proposed_targets": [target],
                "limitations": list(preflight["limitations"]),
            },
            "plan_digest",
        )
        write_artifact(artifact_root, "plan", plan)
        return plan

    def apply(
        self,
        plan: Mapping[str, Any],
        *,
        confirmed_plan_digest: str,
        artifact_root: Path,
    ) -> dict[str, Any]:
        verify_digest(dict(plan), "plan_digest")
        self.client.authenticate()
        if not self.settings.allow_apply:
            raise Refusal(
                RefusalCode.AUTH_APPLY_DISABLED,
                "Superset apply is disabled by configuration.",
            )
        if confirmed_plan_digest != plan["plan_digest"]:
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
                "Apply confirmation does not match the exact Superset plan digest.",
            )
        identity = dict(plan["native_identity"])
        dataset_id = int(identity["dataset_id"])
        self._require_allowed(dataset_id)
        current = snapshot_dataset(self.client.get_dataset(dataset_id))
        self._require_identity(identity, current)
        target = dict(plan["target"])
        if current["fingerprint"] != target["before_fingerprint"]:
            raise Refusal(
                RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
                "The Superset dataset changed after planning.",
                {"actual_fingerprint": current["fingerprint"]},
            )
        recovered_after_timeout = False
        try:
            self.client.update_dataset(dataset_id, str(target["after_sql"]))
        except TimeoutError:
            recovered_after_timeout = True
        observed = snapshot_dataset(self.client.get_dataset(dataset_id))
        self._require_identity(identity, observed)
        if observed["fingerprint"] != target["after_fingerprint"]:
            code = (
                RefusalCode.APPLY_OUTCOME_UNKNOWN
                if recovered_after_timeout
                else RefusalCode.SCOPE_RECEIPT_TARGET_MISMATCH
            )
            raise Refusal(
                code,
                "Native reread did not establish the exact planned Superset state.",
                {"actual_fingerprint": observed["fingerprint"]},
            )
        actual_target = native_target(identity)
        if [actual_target] != list(plan["proposed_targets"]):
            raise Refusal(
                RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                "The actual Superset target set differed from the plan.",
            )
        record = with_digest(
            {
                "schema_version": "1.0.0",
                "result": "APPLIED",
                "campaign_id": plan["campaign_id"],
                "consumer_id": plan["consumer_id"],
                "plan_digest": plan["plan_digest"],
                "actual_targets": [actual_target],
                "before_fingerprint": target["before_fingerprint"],
                "after_fingerprint": target["after_fingerprint"],
                "native_change_ids": [
                    f"dataset:{dataset_id}:changed_on:{observed['source_updated_at']}"
                ],
                "recovered_after_timeout": recovered_after_timeout,
                "captured_at": utc_now(),
            },
            "apply_digest",
        )
        write_artifact(artifact_root, "apply", record)
        return record

    def validate(
        self,
        plan: Mapping[str, Any],
        apply_record: Mapping[str, Any],
        *,
        artifact_root: Path,
    ) -> dict[str, Any]:
        verify_digest(dict(plan), "plan_digest")
        verify_digest(dict(apply_record), "apply_digest")
        self._require_apply_binding(plan, apply_record)
        self.client.authenticate()
        identity = dict(plan["native_identity"])
        current = snapshot_dataset(self.client.get_dataset(int(identity["dataset_id"])))
        self._require_identity(identity, current)
        if current["fingerprint"] != plan["target"]["after_fingerprint"]:
            raise Refusal(
                RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
                "The Superset dataset changed before native validation.",
            )
        self._require_chart_identity(
            identity,
            self.client.get_chart(int(identity["chart_id"])),
        )
        execution = inspect_execution(
            self.client.execute_chart(int(plan["validation"]["chart_id"]))
        )
        baseline = dict(plan["validation"]["baseline"])
        parity = execution_semantically_equal(baseline, execution)
        passed = execution["result"] == "PASSED" and (
            parity or bool(plan["validation"]["allow_semantic_change"])
        )
        execution_artifact = ArtifactWriter(artifact_root).write(
            "superset-chart-execution", execution
        )
        result = with_digest(
            {
                "schema_version": "1.0.0",
                "result": "PASSED" if passed else "FAILED",
                "campaign_id": plan["campaign_id"],
                "consumer_id": plan["consumer_id"],
                "plan_digest": plan["plan_digest"],
                "apply_digest": apply_record["apply_digest"],
                "validator": (
                    "Superset forced saved-chart execution and semantic comparison"
                ),
                "validator_version": self.settings.version,
                "operation": (
                    "GET /api/v1/chart/"
                    f"{plan['validation']['chart_id']}/data/?force=true"
                ),
                "semantic_parity": parity,
                "semantic_change_approved": bool(
                    plan["validation"]["allow_semantic_change"]
                ),
                "baseline_output_digest": baseline["safe_output_digest"],
                "observed": execution,
                "artifact_ids": [execution_artifact],
                "captured_at": utc_now(),
            },
            "validation_digest",
        )
        write_artifact(artifact_root, "validation", result)
        if not passed:
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_FAILED,
                "Superset native execution or semantic parity failed.",
                {"validation_digest": result["validation_digest"]},
            )
        return result

    def compensate(
        self,
        plan: Mapping[str, Any],
        apply_record: Mapping[str, Any],
        *,
        artifact_root: Path,
    ) -> dict[str, Any]:
        verify_digest(dict(plan), "plan_digest")
        verify_digest(dict(apply_record), "apply_digest")
        self._require_apply_binding(plan, apply_record)
        self.client.authenticate()
        if not self.settings.allow_apply:
            raise Refusal(
                RefusalCode.AUTH_APPLY_DISABLED,
                "Superset compensation is disabled by configuration.",
            )
        identity = dict(plan["native_identity"])
        dataset_id = int(identity["dataset_id"])
        current = snapshot_dataset(self.client.get_dataset(dataset_id))
        self._require_identity(identity, current)
        if current["fingerprint"] != plan["target"]["after_fingerprint"]:
            raise Refusal(
                RefusalCode.COMPENSATION_CONFLICT,
                "Compensation preserved an intervening Superset owner change.",
                {"actual_fingerprint": current["fingerprint"]},
            )
        with suppress(TimeoutError):
            self.client.update_dataset(dataset_id, str(plan["target"]["before_sql"]))
        restored = snapshot_dataset(self.client.get_dataset(dataset_id))
        if restored["fingerprint"] != plan["target"]["before_fingerprint"]:
            raise Refusal(
                RefusalCode.COMPENSATION_CONFLICT,
                "Native reread did not establish the exact Superset before state.",
            )
        execution = inspect_execution(
            self.client.execute_chart(int(plan["validation"]["chart_id"]))
        )
        if execution["result"] != "PASSED" or not execution_semantically_equal(
            dict(plan["validation"]["baseline"]), execution
        ):
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_FAILED,
                "The restored Superset state failed native execution.",
            )
        result = with_digest(
            {
                "schema_version": "1.0.0",
                "result": "RESTORED",
                "campaign_id": plan["campaign_id"],
                "consumer_id": plan["consumer_id"],
                "plan_digest": plan["plan_digest"],
                "restored_fingerprint": restored["fingerprint"],
                "native_verification": execution,
                "captured_at": utc_now(),
            },
            "compensation_digest",
        )
        write_artifact(artifact_root, "compensation", result)
        return result

    def emit_receipt(
        self,
        plan: Mapping[str, Any],
        apply_record: Mapping[str, Any],
        validation: Mapping[str, Any],
        *,
        compensation: Mapping[str, Any] | None,
        artifact_root: Path,
        captured_at: str | None = None,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        verify_digest(dict(plan), "plan_digest")
        verify_digest(dict(apply_record), "apply_digest")
        verify_digest(dict(validation), "validation_digest")
        self._require_apply_binding(plan, apply_record)
        if (
            validation["result"] != "PASSED"
            or validation.get("campaign_id") != plan["campaign_id"]
            or validation.get("consumer_id") != plan["consumer_id"]
            or validation.get("plan_digest") != plan["plan_digest"]
            or validation.get("apply_digest") != apply_record["apply_digest"]
        ):
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_FAILED,
                "Superset validation is not passed and bound to the exact apply.",
            )
        if compensation is not None:
            verify_digest(dict(compensation), "compensation_digest")
        receipt = with_digest(
            {
                "schema_version": "1.0.0",
                "receipt_id": (
                    f"superset-{plan['consumer_id']}-"
                    f"{str(apply_record['apply_digest'])[-12:]}"
                ),
                "campaign_id": plan["campaign_id"],
                "consumer_id": plan["consumer_id"],
                "datahub_urn": plan["datahub_urn"],
                "native_identity": dict(plan["native_identity"]),
                "adapter": {
                    "name": "superset",
                    "version": ADAPTER_VERSION,
                    "mode": "live",
                },
                "source_before": {
                    "version": plan["source_version"],
                    "fingerprint": plan["target"]["before_fingerprint"],
                },
                "plan": {
                    "digest": plan["plan_digest"],
                    "proposed_targets": list(plan["proposed_targets"]),
                    "approved_targets": list(plan["proposed_targets"]),
                },
                "apply": {
                    "result": "APPLIED",
                    "actual_targets": list(apply_record["actual_targets"]),
                    "before_fingerprint": apply_record["before_fingerprint"],
                    "after_fingerprint": apply_record["after_fingerprint"],
                    "native_change_ids": list(apply_record["native_change_ids"]),
                },
                "validation": {
                    "result": "PASSED",
                    "validator": validation["validator"],
                    "validator_version": validation["validator_version"],
                    "artifact_ids": list(validation["artifact_ids"]),
                },
                "compensation": {
                    "available": True,
                    "exercised": compensation is not None,
                    "result": "RESTORED" if compensation is not None else "NOT_NEEDED",
                },
                "captured_at": captured_at or utc_now(),
                "expires_at": expires_at,
                "limitations": list(plan["limitations"]),
                "terminal_disposition": "VALIDATED",
            },
            "receipt_digest",
        )
        validate_schema(
            "consumer-receipt",
            receipt,
            refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
        )
        write_artifact(artifact_root, "receipt", receipt)
        return receipt

    def reconcile_source(
        self,
        plan: Mapping[str, Any],
        receipt: Mapping[str, Any],
        datahub_observation: Mapping[str, Any],
        *,
        artifact_root: Path,
    ) -> dict[str, Any]:
        verify_digest(dict(plan), "plan_digest")
        verify_digest(dict(receipt), "receipt_digest")
        receipt_plan = receipt.get("plan")
        receipt_apply = receipt.get("apply")
        receipt_validation = receipt.get("validation")
        if (
            not isinstance(receipt_plan, Mapping)
            or not isinstance(receipt_apply, Mapping)
            or not isinstance(receipt_validation, Mapping)
            or receipt.get("campaign_id") != plan["campaign_id"]
            or receipt.get("consumer_id") != plan["consumer_id"]
            or receipt.get("datahub_urn") != plan["datahub_urn"]
            or receipt_plan.get("digest") != plan["plan_digest"]
            or receipt_apply.get("actual_targets") != plan["proposed_targets"]
            or receipt_apply.get("after_fingerprint")
            != plan["target"]["after_fingerprint"]
            or receipt_validation.get("result") != "PASSED"
        ):
            raise Refusal(
                RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                "The Superset receipt is not bound to the exact migration plan.",
            )
        self.client.authenticate()
        identity = dict(plan["native_identity"])
        current = snapshot_dataset(self.client.get_dataset(int(identity["dataset_id"])))
        self._require_identity(identity, current)
        if current["fingerprint"] != plan["target"]["after_fingerprint"]:
            raise Refusal(
                RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
                "The Superset source changed after native validation.",
            )
        self._require_chart_identity(
            identity,
            self.client.get_chart(int(identity["chart_id"])),
        )
        if datahub_observation.get("dataset_urn") != plan[
            "datahub_urn"
        ] or dataset_id_from_datahub(
            {
                "urn": datahub_observation.get("dataset_urn"),
                "external_url": datahub_observation.get("dataset_external_url"),
            }
        ) != int(identity["dataset_id"]):
            raise Refusal(
                RefusalCode.RECONCILIATION_SCOPE_MISMATCH,
                "Fresh DataHub identity no longer maps to the exact Superset dataset.",
            )
        field_urns = [
            str(item) for item in datahub_observation.get("upstream_field_urns", [])
        ]
        replacement = str(plan["target"]["replacement_field"])
        legacy = str(plan["target"]["legacy_field"])
        has_replacement = any(
            value.endswith(f",{replacement})") for value in field_urns
        )
        has_legacy = any(value.endswith(f",{legacy})") for value in field_urns)
        if (
            bool(datahub_observation.get("table_only"))
            or not has_replacement
            or has_legacy
        ):
            raise Refusal(
                RefusalCode.RECONCILIATION_SCOPE_MISMATCH,
                (
                    "Fresh DataHub evidence did not corroborate the exact "
                    "replacement field."
                ),
                {
                    "table_only": bool(datahub_observation.get("table_only")),
                    "replacement_observed": has_replacement,
                    "legacy_observed": has_legacy,
                },
            )
        execution = inspect_execution(
            self.client.execute_chart(int(identity["chart_id"]))
        )
        if execution["result"] != "PASSED" or not execution_semantically_equal(
            dict(plan["validation"]["baseline"]), execution
        ):
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_FAILED,
                "Fresh Superset native revalidation failed.",
            )
        validation = with_digest(
            {
                "schema_version": "1.0.0",
                "result": "PASSED",
                "campaign_id": plan["campaign_id"],
                "consumer_id": plan["consumer_id"],
                "plan_digest": plan["plan_digest"],
                "receipt_digest": receipt["receipt_digest"],
                "validator": "Superset forced saved-chart revalidation",
                "validator_version": self.settings.version,
                "observed": execution,
                "captured_at": utc_now(),
            },
            "validation_digest",
        )
        write_artifact(artifact_root / "native-revalidation", "validation", validation)
        observation = with_digest(
            {
                "schema_version": "1.0.0",
                "mode": "live",
                "captured_at": utc_now(),
                "plan_digest": plan["plan_digest"],
                "receipt_digest": receipt["receipt_digest"],
                "native_fingerprint": current["fingerprint"],
                "datahub": dict(datahub_observation),
                "native_execution": execution,
                "validation_digest": validation["validation_digest"],
                "limitations": list(plan["limitations"]),
            },
            "reconciliation_digest",
        )
        write_artifact(artifact_root, "source-reconciliation", observation)
        return observation

    def _require_allowed(self, dataset_id: int) -> None:
        if dataset_id not in self.settings.allowed_dataset_ids:
            raise Refusal(
                RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                "The Superset dataset is absent from the explicit apply allowlist.",
                {"dataset_id": dataset_id},
            )

    @staticmethod
    def _require_identity(
        identity: Mapping[str, Any], snapshot: Mapping[str, Any]
    ) -> None:
        current = snapshot["identity"]
        if (
            int(current["id"]) != int(identity["dataset_id"])
            or str(current["uuid"]) != str(identity["dataset_uuid"])
            or int(current["database_id"]) != int(identity["database_id"])
            or str(current["database_uuid"]) != str(identity["database_uuid"])
        ):
            raise Refusal(
                RefusalCode.IDENTITY_NATIVE_OBJECT_RECREATED,
                (
                    "The Superset object ID now resolves to a different immutable "
                    "identity."
                ),
            )

    @staticmethod
    def _require_chart_identity(
        identity: Mapping[str, Any], chart: Mapping[str, Any]
    ) -> None:
        if (
            int(chart.get("id", 0)) != int(identity["chart_id"])
            or str(chart.get("uuid", "")) != str(identity["chart_uuid"])
            or int(chart.get("datasource_id", 0)) != int(identity["dataset_id"])
        ):
            raise Refusal(
                RefusalCode.IDENTITY_NATIVE_OBJECT_RECREATED,
                "The Superset chart identity or dataset binding changed.",
            )

    @staticmethod
    def _require_apply_binding(
        plan: Mapping[str, Any], apply_record: Mapping[str, Any]
    ) -> None:
        target = plan["target"]
        if (
            apply_record.get("campaign_id") != plan["campaign_id"]
            or apply_record.get("consumer_id") != plan["consumer_id"]
            or apply_record.get("plan_digest") != plan["plan_digest"]
            or apply_record.get("actual_targets") != plan["proposed_targets"]
            or apply_record.get("before_fingerprint") != target["before_fingerprint"]
            or apply_record.get("after_fingerprint") != target["after_fingerprint"]
            or apply_record.get("result") != "APPLIED"
        ):
            raise Refusal(
                RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                "The Superset apply record is not bound to the exact plan.",
            )

    @staticmethod
    def _validate_fields(legacy: str, replacement: str) -> None:
        if (
            legacy == replacement
            or not IDENTIFIER.fullmatch(legacy)
            or not IDENTIFIER.fullmatch(replacement)
        ):
            raise Refusal(
                RefusalCode.SPEC_UNSUPPORTED_REPLACEMENT,
                "Superset supports one distinct unquoted SQL identifier replacement.",
            )


def snapshot_dataset(dataset: Mapping[str, Any]) -> dict[str, Any]:
    database = dataset.get("database")
    if not isinstance(database, Mapping):
        raise Refusal(
            RefusalCode.IDENTITY_NOT_FOUND,
            "Superset did not expose the dataset database identity.",
        )
    identity = {
        "id": int(dataset["id"]),
        "uuid": str(dataset["uuid"]),
        "database_id": int(database["id"]),
        "database_uuid": str(database["uuid"]),
    }
    content = {
        "schema": dataset.get("schema"),
        "table_name": dataset.get("table_name"),
        "sql": dataset.get("sql"),
        "owners": sorted(int(owner["id"]) for owner in dataset.get("owners", [])),
        "columns": sorted(
            (
                int(column["id"]),
                str(column["uuid"]),
                str(column["column_name"]),
                str(column.get("type", "")),
            )
            for column in dataset.get("columns", [])
        ),
        "metrics": sorted(
            (
                int(metric["id"]),
                str(metric["uuid"]),
                str(metric["metric_name"]),
                str(metric.get("expression", "")),
            )
            for metric in dataset.get("metrics", [])
        ),
    }
    if not isinstance(content["sql"], str) or not content["sql"].strip():
        raise Refusal(
            RefusalCode.SPEC_UNSUPPORTED_REPLACEMENT,
            (
                "Only a Superset virtual dataset with directly inspectable SQL "
                "is supported."
            ),
        )
    return {
        "identity": identity,
        "content": content,
        "source_updated_at": str(dataset.get("changed_on", "")),
        "fingerprint": digest_json({"identity": identity, "content": content}),
    }


def inspect_execution(value: Mapping[str, Any]) -> dict[str, Any]:
    data = value.get("data")
    columns = value.get("colnames")
    rowcount = value.get("rowcount")
    sql_rowcount = value.get("sql_rowcount")
    complete = (
        isinstance(data, list)
        and isinstance(columns, list)
        and isinstance(rowcount, int)
        and isinstance(sql_rowcount, int)
        and len(data) == rowcount == sql_rowcount
    )
    safe_rows = (
        sorted(
            (dict(row) for row in data if isinstance(row, Mapping)),
            key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")),
        )
        if isinstance(data, list)
        else []
    )
    passed = (
        value.get("status") == "success" and value.get("error") is None and complete
    )
    return {
        "result": "PASSED" if passed else "FAILED",
        "status": value.get("status"),
        "rowcount": rowcount if isinstance(rowcount, int) else 0,
        "sql_rowcount": sql_rowcount if isinstance(sql_rowcount, int) else 0,
        "returned_rows": len(data) if isinstance(data, list) else 0,
        "columns": [str(item) for item in columns] if isinstance(columns, list) else [],
        "is_cached": value.get("is_cached"),
        "error_present": value.get("error") is not None,
        "safe_output_digest": digest_json(safe_rows),
        "query_digest": digest_json(str(value.get("query", ""))),
    }


def execution_semantically_equal(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> bool:
    return all(
        before.get(key) == after.get(key)
        for key in ("rowcount", "sql_rowcount", "columns", "safe_output_digest")
    )


def identifier_occurrences(sql: str, identifier: str) -> int:
    return len(_unquoted_identifier_spans(sql, identifier))


def replace_identifier_once(sql: str, before: str, after: str) -> str:
    spans = _unquoted_identifier_spans(sql, before)
    if len(spans) != 1:
        raise Refusal(
            RefusalCode.IDENTITY_FIELD_AMBIGUOUS,
            (
                "The exact unquoted legacy field token was not unique in "
                "executable native SQL."
            ),
        )
    start, end = spans[0]
    return f"{sql[:start]}{after}{sql[end:]}"


def _unquoted_identifier_spans(sql: str, identifier: str) -> list[tuple[int, int]]:
    """Find executable unquoted identifier tokens without parsing arbitrary SQL."""

    spans: list[tuple[int, int]] = []
    index = 0
    state = "code"
    dollar_delimiter = ""
    while index < len(sql):
        if state == "line-comment":
            if sql[index] in "\r\n":
                state = "code"
            index += 1
            continue
        if state == "block-comment":
            if sql.startswith("*/", index):
                state = "code"
                index += 2
            else:
                index += 1
            continue
        if state == "single-quote":
            if sql.startswith("''", index):
                index += 2
            elif sql[index] == "'":
                state = "code"
                index += 1
            else:
                index += 1
            continue
        if state in {"double-quote", "backtick"}:
            quote = '"' if state == "double-quote" else "`"
            if sql.startswith(quote * 2, index):
                index += 2
            elif sql[index] == quote:
                state = "code"
                index += 1
            else:
                index += 1
            continue
        if state == "bracket":
            if sql.startswith("]]", index):
                index += 2
            elif sql[index] == "]":
                state = "code"
                index += 1
            else:
                index += 1
            continue
        if state == "dollar-quote":
            if sql.startswith(dollar_delimiter, index):
                state = "code"
                index += len(dollar_delimiter)
            else:
                index += 1
            continue

        if sql.startswith("--", index):
            state = "line-comment"
            index += 2
            continue
        if sql.startswith("/*", index):
            state = "block-comment"
            index += 2
            continue
        if sql[index] == "'":
            state = "single-quote"
            index += 1
            continue
        if sql[index] == '"':
            state = "double-quote"
            index += 1
            continue
        if sql[index] == "`":
            state = "backtick"
            index += 1
            continue
        if sql[index] == "[":
            state = "bracket"
            index += 1
            continue
        if sql[index] == "$":
            match = DOLLAR_QUOTE.match(sql, index)
            if match is not None:
                dollar_delimiter = match.group(0)
                state = "dollar-quote"
                index = match.end()
                continue
        end = index + len(identifier)
        if (
            sql.startswith(identifier, index)
            and (index == 0 or not _identifier_character(sql[index - 1]))
            and (end == len(sql) or not _identifier_character(sql[end]))
        ):
            spans.append((index, end))
            index = end
            continue
        index += 1

    if state not in {"code", "line-comment"}:
        raise Refusal(
            RefusalCode.SPEC_UNSUPPORTED_REPLACEMENT,
            "Superset refused SQL with an unterminated quote or comment.",
        )
    return spans


def _identifier_character(value: str) -> bool:
    return value.isalnum() or value == "_"


def dataset_id_from_datahub(entity: Mapping[str, Any]) -> int | None:
    urn = entity.get("urn")
    external_url = entity.get("external_url")
    if not isinstance(urn, str) or "dataPlatform:superset" not in urn:
        return None
    if not isinstance(external_url, str):
        return None
    values = parse_qs(urlparse(external_url).query).get("datasource_id", [])
    if len(values) != 1:
        return None
    try:
        return int(values[0])
    except ValueError:
        return None


def native_target(identity: Mapping[str, Any]) -> str:
    return f"superset:dataset:{identity['dataset_id']}:{identity['dataset_uuid']}"


def write_artifact(root: Path, name: str, value: Mapping[str, Any]) -> None:
    write_json(root / f"{name}.json", dict(value))
