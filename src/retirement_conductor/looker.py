"""Fail-closed adapter for one exact saved Look through documented API 4.0."""

from __future__ import annotations

import json
import re
import ssl
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from retirement_conductor.canonical import (
    digest_json,
    verify_digest,
    with_digest,
)
from retirement_conductor.clock import parse_timestamp
from retirement_conductor.datahub import utc_now
from retirement_conductor.errors import Refusal
from retirement_conductor.looker_config import LookerSettings
from retirement_conductor.records import validate_consumer_receipt
from retirement_conductor.schemas import validate_schema
from retirement_conductor.vocabulary import (
    ConsumerDisposition,
    RefusalCode,
)

ADAPTER_VERSION = "0.1.0"
LOOKER_API_VERSION = "4.0.26.12"

# These permissions cover the exact reads and the one-property saved-Look update.
# DataHub ingestion has its own documented, separately checked recipe boundary.
REQUIRED_PERMISSIONS = {
    "access_data",
    "explore",
    "save_content",
    "see_lookml",
    "see_looks",
    "see_queries",
    "see_schedules",
    "see_users",
}
DATAHUB_INGESTION_PERMISSIONS = {
    "access_data",
    "explore",
    "manage_models",
    "see_datagroups",
    "see_lookml",
    "see_lookml_dashboards",
    "see_looks",
    "see_pdts",
    "see_queries",
    "see_schedules",
    "see_sql",
    "see_system_activity",
    "see_user_dashboards",
    "see_users",
}
QUERY_CREATE_FIELDS = (
    "model",
    "view",
    "fields",
    "pivots",
    "fill_fields",
    "filters",
    "filter_expression",
    "sorts",
    "limit",
    "column_limit",
    "total",
    "row_total",
    "subtotals",
    "vis_config",
    "dynamic_fields",
    "query_timezone",
    "filter_config",
)


class LookerClient(Protocol):
    """Minimal injectable API surface used by the deterministic adapter."""

    def login(self) -> dict[str, Any]: ...

    def request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        form: Mapping[str, str] | None = None,
        authenticated: bool = True,
        mutation: bool = False,
    ) -> Any: ...


class LookerApiClient:
    """Small API 4.0 client with bounded read retries and redacted failures."""

    def __init__(
        self,
        settings: LookerSettings,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        base = settings.base_url.rstrip("/")
        self.api_root = base if base.endswith("/api/4.0") else f"{base}/api/4.0"
        self._token: str | None = None
        self._sleep = sleep

    def login(self) -> dict[str, Any]:
        response = self.request(
            "POST",
            "/login",
            form={
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
            },
            authenticated=False,
        )
        value = _object(response, operation="Looker login")
        token = value.get("access_token")
        if not isinstance(token, str) or not token:
            raise Refusal(
                RefusalCode.SOURCE_LOOKER_UNAVAILABLE,
                "Looker authentication did not return an access token.",
            )
        self._token = token
        return {
            "authenticated": True,
            "token_type": str(value.get("token_type") or "Bearer"),
        }

    def request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        form: Mapping[str, str] | None = None,
        authenticated: bool = True,
        mutation: bool = False,
    ) -> Any:
        if authenticated and self._token is None:
            self.login()
        url = f"{self.api_root}{path}"
        if query:
            encoded = urlencode(
                [
                    (key, item)
                    for key, value in query.items()
                    for item in _query_items(value)
                ]
            )
            url = f"{url}?{encoded}"
        headers = {"Accept": "application/json"}
        data: bytes | None = None
        if body is not None:
            data = json.dumps(
                body,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
            headers["Content-Type"] = "application/json"
        elif form is not None:
            data = urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if authenticated and self._token is not None:
            headers["Authorization"] = f"token {self._token}"
        context = (
            ssl.create_default_context()
            if self.settings.verify_tls
            else ssl._create_unverified_context()
        )
        attempts = 1 if mutation else self.settings.max_retries + 1
        for attempt in range(attempts):
            request = Request(url, data=data, headers=headers, method=method)
            try:
                with urlopen(
                    request,
                    context=context,
                    timeout=self.settings.timeout_seconds,
                ) as response:
                    payload = response.read()
                    return json.loads(payload) if payload else None
            except HTTPError as exc:
                if not mutation and exc.code == 429 and attempt + 1 < attempts:
                    retry_after = exc.headers.get("Retry-After", "0")
                    try:
                        delay = min(max(float(retry_after), 0.0), 2.0)
                    except ValueError:
                        delay = 0.0
                    self._sleep(delay)
                    continue
                raise _http_refusal(
                    exc.code,
                    method=method,
                    path=path,
                    retry_count=attempt,
                    mutation=mutation,
                ) from exc
            except (TimeoutError, URLError, json.JSONDecodeError) as exc:
                if mutation:
                    raise Refusal(
                        RefusalCode.APPLY_OUTCOME_UNKNOWN,
                        "The Looker mutation response was lost; native reread is "
                        "required before any retry.",
                        {
                            "method": method,
                            "path": path,
                            "error_type": type(exc).__name__,
                        },
                    ) from exc
                raise Refusal(
                    RefusalCode.SOURCE_LOOKER_UNAVAILABLE,
                    "The Looker API read failed.",
                    {
                        "method": method,
                        "path": path,
                        "error_type": type(exc).__name__,
                    },
                ) from exc
        raise AssertionError("bounded Looker request loop exhausted")


class LookerAdapter:
    """Inventory, mutate, validate, and compensate one exact saved Look."""

    def __init__(
        self,
        settings: LookerSettings,
        client: LookerClient | None = None,
        *,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.settings = settings
        self.client = client or LookerApiClient(settings)
        self.clock = clock
        self._preflight: dict[str, Any] | None = None

    def preflight(self) -> dict[str, Any]:
        authentication = self.client.login()
        user = _object(
            self.client.request(
                "GET",
                "/user",
                query={"fields": "id,display_name"},
            ),
            operation="read authenticated Looker principal",
        )
        user_id = _required_string(user, "id", operation="Looker principal")
        roles = _array(
            self.client.request(
                "GET",
                f"/users/{user_id}/roles",
                query={"fields": "id,permission_set,model_set"},
            ),
            operation="read authenticated Looker roles",
        )
        permissions = sorted(
            {
                str(permission)
                for role_value in roles
                for permission in _nested_sequence(
                    role_value,
                    "permission_set",
                    "permissions",
                )
            }
        )
        models = sorted(
            {
                str(model)
                for role_value in roles
                for model in _nested_sequence(role_value, "model_set", "models")
            }
        )
        missing = sorted(REQUIRED_PERMISSIONS - set(permissions))
        if missing:
            raise Refusal(
                RefusalCode.SOURCE_LOOKER_PERMISSION_DENIED,
                "The authenticated Looker principal lacks required adapter "
                "permissions.",
                {"missing_permissions": missing},
            )
        if self.settings.model_id not in models and "*" not in models:
            raise Refusal(
                RefusalCode.SOURCE_LOOKER_PERMISSION_DENIED,
                "The authenticated Looker principal cannot access the configured "
                "model.",
                {"required_model": self.settings.model_id},
            )
        self._preflight = with_digest(
            {
                "schema_version": "1.0.0",
                "captured_at": self.clock(),
                "mode": self.settings.mode,
                "api_version": LOOKER_API_VERSION,
                "authentication": authentication,
                "principal": {
                    "id_digest": digest_json(user_id),
                    "display_name_digest": digest_json(
                        str(user.get("display_name") or "")
                    ),
                },
                "effective_permissions": permissions,
                "effective_models_digest": digest_json(models),
                "required_model": self.settings.model_id,
                "required_permissions": sorted(REQUIRED_PERMISSIONS),
                "datahub_ingestion_permission_check": {
                    "required": sorted(DATAHUB_INGESTION_PERMISSIONS),
                    "missing": sorted(DATAHUB_INGESTION_PERMISSIONS - set(permissions)),
                    "separate_principal_allowed": True,
                },
                "capabilities": {
                    "read": True,
                    "plan": True,
                    "apply": self.settings.allow_apply,
                    "validate": True,
                    "compensate": self.settings.allow_apply,
                },
                "configuration": self.settings.safe_summary(),
            },
            "preflight_digest",
        )
        return self._preflight

    def snapshot(
        self,
        *,
        expected_identity: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a query-safe native snapshot without private query content."""

        public, _ = self._snapshot_bundle(expected_identity=expected_identity)
        return public

    def plan(self, *, campaign_id: str, consumer_id: str) -> dict[str, Any]:
        preflight = self._preflight or self.preflight()
        snapshot, query_body = self._snapshot_bundle()
        compatibility = self._replacement_evidence()
        discovery = self._scan_folder_targets(self.settings.legacy_reference)
        approved = [self.settings.content_target]
        if discovery["targets"] != approved:
            raise Refusal(
                RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                "Folder discovery did not equal the one exact allowlisted target.",
                {
                    "approved_targets": approved,
                    "discovered_targets": discovery["targets"],
                },
            )
        self._require_safe_relevance(snapshot)
        legacy_count = _reference_count(
            query_body,
            self.settings.legacy_reference,
        )
        if legacy_count < 1:
            raise Refusal(
                RefusalCode.IDENTITY_FIELD_NOT_FOUND,
                "The exact saved Look query does not reference the legacy field.",
            )
        if _reference_count(query_body, self.settings.replacement_reference):
            raise Refusal(
                RefusalCode.SPEC_REPLACEMENT_INCOMPATIBLE,
                "The saved Look already mixes the legacy and replacement fields.",
            )
        changed_fields = _changed_query_fields(
            query_body,
            legacy=self.settings.legacy_reference,
            replacement=self.settings.replacement_reference,
        )
        if not changed_fields:
            raise Refusal(
                RefusalCode.IDENTITY_FIELD_NOT_FOUND,
                "No documented query property contains the legacy reference.",
            )
        replacement_query = _replace_reference(
            query_body,
            self.settings.legacy_reference,
            self.settings.replacement_reference,
        )
        before_validation = self._content_validation()
        if before_validation["error_count"]:
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_FAILED,
                "Scoped Looker Content Validation failed before mutation.",
                {"error_count": before_validation["error_count"]},
            )
        before_execution = self._run_look()
        after_query_fingerprint = digest_json(replacement_query)
        after_fingerprint = _content_fingerprint(
            identity=snapshot["native_identity"],
            look=snapshot["look"],
            query_fingerprint=after_query_fingerprint,
            schedules=snapshot["schedules"],
            relevance=snapshot["relevance"],
        )
        plan = with_digest(
            {
                "schema_version": "1.0.0",
                "campaign_id": campaign_id,
                "consumer_id": consumer_id,
                "datahub_urn": self.settings.datahub_urn,
                "graph_snapshot_digest": self.settings.graph_snapshot_digest,
                "adapter": {
                    "name": "looker",
                    "version": ADAPTER_VERSION,
                    "api_version": LOOKER_API_VERSION,
                    "mode": self.settings.mode,
                },
                "native_identity": snapshot["native_identity"],
                "source": {
                    "version": snapshot["source_version"],
                    "fingerprint": snapshot["content_fingerprint"],
                    "query_id": snapshot["look"]["query_id"],
                    "query_fingerprint": snapshot["query"]["fingerprint"],
                    "schedule_fingerprint": snapshot["schedules"]["fingerprint"],
                    "look_state_fingerprint": snapshot["look"]["state_fingerprint"],
                },
                "replacement": compatibility,
                "references": {
                    "legacy": self.settings.legacy_reference,
                    "replacement": self.settings.replacement_reference,
                    "legacy_occurrences": legacy_count,
                    "changed_query_fields": changed_fields,
                    "after_query_fingerprint": after_query_fingerprint,
                    "after_fingerprint": after_fingerprint,
                },
                "target_sets": {
                    "proposed": approved,
                    "approved": approved,
                    "discovered": discovery["targets"],
                },
                "discovery": discovery,
                "relevance": snapshot["relevance"],
                "before_validation": before_validation,
                "before_execution": before_execution,
                "mutation": {
                    "create_query": "POST /queries",
                    "update_saved_look": (
                        f"PATCH /looks/{self.settings.look_id} with query_id only"
                    ),
                    "create_query_idempotency": (
                        "identical query bodies return the existing immutable query"
                    ),
                    "automatic_mutation_retries": False,
                    "actual_changed_fields": ["query_id"],
                },
                "preflight_digest": preflight["preflight_digest"],
                "limitations": [
                    "Content Validation checks reference integrity, not business "
                    "equivalence.",
                    (
                        "Native query comparison is bounded to "
                        f"{self.settings.query_limit} rows."
                    ),
                    "The supported native object is one saved Look; dashboards "
                    "and merged results are outside this mutation path.",
                    "DataHub completeness and freshness remain separately bounded.",
                ],
            },
            "plan_digest",
        )
        validate_schema(
            "looker-plan",
            plan,
            refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
        )
        return plan

    def prepare_apply_intent(
        self,
        plan: Mapping[str, Any],
        *,
        recorded_at: str,
    ) -> dict[str, Any]:
        self._validate_plan(plan)
        return with_digest(
            {
                "schema_version": "1.0.0",
                "campaign_id": plan["campaign_id"],
                "plan_digest": plan["plan_digest"],
                "target": self.settings.content_target,
                "native_identity_digest": digest_json(plan["native_identity"]),
                "before_fingerprint": plan["source"]["fingerprint"],
                "before_query_id": plan["source"]["query_id"],
                "after_fingerprint": plan["references"]["after_fingerprint"],
                "after_query_fingerprint": plan["references"][
                    "after_query_fingerprint"
                ],
                "status": "PENDING",
                "outcome_reason": None,
                "recorded_at": recorded_at,
            },
            "intent_digest",
        )

    def mark_intent_outcome_unknown(
        self,
        intent: Mapping[str, Any],
        *,
        observed_at: str,
        reason: str,
    ) -> dict[str, Any]:
        value = dict(intent)
        verify_digest(value, "intent_digest")
        value.update(
            {
                "status": "OUTCOME_UNKNOWN",
                "outcome_reason": reason,
                "observed_at": observed_at,
            }
        )
        return with_digest(value, "intent_digest")

    def mark_intent_resolved(
        self,
        intent: Mapping[str, Any],
        *,
        apply_digest: str,
        observed_at: str,
    ) -> dict[str, Any]:
        value = dict(intent)
        verify_digest(value, "intent_digest")
        value.update(
            {
                "status": "RESOLVED",
                "outcome_reason": "native_state_matches_planned_after",
                "observed_at": observed_at,
                "apply_digest": apply_digest,
            }
        )
        return with_digest(value, "intent_digest")

    def apply(
        self,
        plan: Mapping[str, Any],
        intent: Mapping[str, Any],
        *,
        prior_apply: Mapping[str, Any] | None = None,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        self._validate_plan(plan)
        self._validate_intent(plan, intent)
        if not self.settings.allow_apply:
            raise Refusal(
                RefusalCode.AUTH_APPLY_DISABLED,
                "Looker apply is disabled by configuration.",
                {"required_reference": "LOOKER_ALLOW_APPLY"},
            )
        snapshot, query_body = self._snapshot_bundle(
            expected_identity=_mapping(plan["native_identity"])
        )
        if prior_apply is not None:
            prior = dict(prior_apply)
            verify_digest(prior, "apply_digest")
            if (
                prior.get("plan_digest") == plan["plan_digest"]
                and self._matches_after(plan, snapshot)
                and snapshot["look"]["query_id"] == prior.get("after_query_id")
            ):
                return prior
        if self._matches_after(plan, snapshot):
            return self._apply_record(
                plan,
                snapshot,
                before_query_id=str(plan["source"]["query_id"]),
                after_query_id=str(snapshot["look"]["query_id"]),
                occurred_at=occurred_at or self.clock(),
                recovery="native_reread",
            )
        if not self._matches_before(plan, snapshot):
            code = (
                RefusalCode.APPLY_OUTCOME_UNKNOWN
                if intent["status"] == "OUTCOME_UNKNOWN"
                else RefusalCode.SOURCE_FINGERPRINT_MISMATCH
            )
            raise Refusal(
                code,
                "The exact saved Look is neither the approved before state nor the "
                "planned after state.",
                {
                    "expected_before_fingerprint": plan["source"]["fingerprint"],
                    "expected_after_fingerprint": plan["references"][
                        "after_fingerprint"
                    ],
                    "actual_fingerprint": snapshot["content_fingerprint"],
                },
            )
        if snapshot["source_version"] != plan["source"]["version"]:
            raise Refusal(
                RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
                "The saved Look native source version changed after planning.",
                {
                    "expected_source_version": plan["source"]["version"],
                    "actual_source_version": snapshot["source_version"],
                },
            )
        if (
            snapshot["schedules"]["fingerprint"]
            != plan["source"]["schedule_fingerprint"]
        ):
            raise Refusal(
                RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
                "The saved Look schedule set changed before apply.",
            )
        self._require_safe_relevance(snapshot)
        discovery = self._scan_folder_targets(self.settings.legacy_reference)
        if discovery["targets"] != plan["target_sets"]["approved"]:
            raise Refusal(
                RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                "The actual Looker target set changed after authorization.",
                {
                    "approved_targets": plan["target_sets"]["approved"],
                    "actual_targets": discovery["targets"],
                },
            )
        compatibility = self._replacement_evidence()
        if compatibility["evidence_digest"] != plan["replacement"]["evidence_digest"]:
            raise Refusal(
                RefusalCode.SPEC_REPLACEMENT_INCOMPATIBLE,
                "Looker field compatibility changed after planning.",
            )
        replacement_query = _replace_reference(
            query_body,
            self.settings.legacy_reference,
            self.settings.replacement_reference,
        )
        replacement_fingerprint = digest_json(replacement_query)
        if replacement_fingerprint != plan["references"]["after_query_fingerprint"]:
            raise Refusal(
                RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                "The deterministic Looker query mutation changed after planning.",
            )
        created = _object(
            self.client.request(
                "POST",
                "/queries",
                body=replacement_query,
                mutation=True,
            ),
            operation="create or reuse replacement Looker query",
        )
        after_query_id = _required_string(
            created,
            "id",
            operation="replacement Looker query",
        )
        created_query = _object(
            self.client.request("GET", f"/queries/{after_query_id}"),
            operation="reread replacement Looker query",
        )
        if digest_json(_query_body(created_query)) != replacement_fingerprint:
            raise Refusal(
                RefusalCode.APPLY_OUTCOME_UNKNOWN,
                "The query returned by Looker does not match the planned immutable "
                "query body.",
            )
        self.client.request(
            "PATCH",
            f"/looks/{self.settings.look_id}",
            body={"query_id": after_query_id},
            mutation=True,
        )
        after, _ = self._snapshot_bundle(
            expected_identity=_mapping(plan["native_identity"])
        )
        if (
            not self._matches_after(plan, after)
            or after["look"]["query_id"] != after_query_id
        ):
            raise Refusal(
                RefusalCode.APPLY_OUTCOME_UNKNOWN,
                "Looker returned from mutation without the exact planned native "
                "state; a later native reread is required.",
            )
        return self._apply_record(
            plan,
            after,
            before_query_id=str(plan["source"]["query_id"]),
            after_query_id=after_query_id,
            occurred_at=occurred_at or self.clock(),
            recovery=(
                "idempotent_query_reuse_after_unknown"
                if intent["status"] == "OUTCOME_UNKNOWN"
                else None
            ),
        )

    def validate(
        self,
        plan: Mapping[str, Any],
        apply_record: Mapping[str, Any],
        *,
        artifact_ids: Sequence[str] = (),
    ) -> dict[str, Any]:
        self._validate_plan(plan)
        apply_value = dict(apply_record)
        verify_digest(apply_value, "apply_digest")
        if apply_value.get("plan_digest") != plan["plan_digest"]:
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
                "The Looker validation input belongs to another plan.",
            )
        snapshot, query_body = self._snapshot_bundle(
            expected_identity=_mapping(plan["native_identity"])
        )
        if (
            not self._matches_after(plan, snapshot)
            or snapshot["look"]["query_id"] != apply_value["after_query_id"]
        ):
            raise Refusal(
                RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
                "The applied saved Look changed before native validation.",
            )
        if _contains_reference(query_body, self.settings.legacy_reference):
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_FAILED,
                "The legacy field remains in the saved Look query.",
            )
        if not _contains_reference(
            query_body,
            self.settings.replacement_reference,
        ):
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_FAILED,
                "The replacement field is absent from the saved Look query.",
            )
        self._require_safe_relevance(snapshot)
        remaining = self._scan_folder_targets(self.settings.legacy_reference)
        if remaining["targets"]:
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_FAILED,
                "Legacy Looker targets remain inside the fully paged folder scope.",
                {"remaining_targets": remaining["targets"]},
            )
        native = self._content_validation()
        if native["error_count"]:
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_FAILED,
                "Scoped Looker Content Validation failed after apply.",
                {"error_count": native["error_count"]},
            )
        execution = self._run_look()
        if execution["semantic_digest"] != plan["before_execution"]["semantic_digest"]:
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_FAILED,
                "The bounded Looker query result changed under the predeclared "
                "semantic comparison.",
                {
                    "before_digest": plan["before_execution"]["semantic_digest"],
                    "after_digest": execution["semantic_digest"],
                },
            )
        return with_digest(
            {
                "schema_version": "1.0.0",
                "result": "PASSED",
                "captured_at": self.clock(),
                "validator": (
                    "Looker Content Validation plus bounded saved-Look execution"
                ),
                "validator_version": LOOKER_API_VERSION,
                "scope": native["scope"],
                "content_validation": native,
                "query_execution": execution,
                "remaining_legacy_targets": 0,
                "relevance": snapshot["relevance"],
                "artifact_ids": sorted(set(artifact_ids)),
            },
            "validation_digest",
        )

    def reconcile_source(
        self,
        plan: Mapping[str, Any],
        apply_record: Mapping[str, Any],
        receipt: Mapping[str, Any],
        *,
        legacy_snapshot: Mapping[str, Any],
        replacement_snapshot: Mapping[str, Any],
        require_live: bool = True,
    ) -> dict[str, Any]:
        """Reread native state and compare exact legacy/replacement graph edges."""

        self._validate_plan(plan)
        apply_value = dict(apply_record)
        receipt_value = dict(receipt)
        verify_digest(apply_value, "apply_digest")
        verify_digest(receipt_value, "receipt_digest")
        if apply_value.get("plan_digest") != plan["plan_digest"]:
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
                "The Looker reconciliation apply record belongs to another plan.",
            )
        validate_consumer_receipt(
            receipt_value,
            campaign_id=str(plan["campaign_id"]),
            consumer_id=str(plan["consumer_id"]),
            plan_digest=str(plan["plan_digest"]),
            source_version=str(plan["source"]["version"]),
            approved_targets=list(plan["target_sets"]["approved"]),
            require_live=require_live,
            trusted_now=parse_timestamp(self.clock()),
        )
        if (
            receipt_value["native_identity"] != plan["native_identity"]
            or receipt_value["datahub_urn"] != plan["datahub_urn"]
            or receipt_value["apply"]["before_fingerprint"]
            != apply_value["before_fingerprint"]
            or receipt_value["apply"]["after_fingerprint"]
            != apply_value["after_fingerprint"]
            or receipt_value["apply"]["native_change_ids"]
            != apply_value["native_change_ids"]
        ):
            raise Refusal(
                RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                "The accepted Looker receipt is not bound to the native apply record.",
            )
        preflight = self.preflight()
        if require_live and preflight["mode"] != "live":
            raise Refusal(
                RefusalCode.EVIDENCE_MODE_NOT_LIVE,
                "Live reconciliation requires a live Looker capability receipt.",
            )
        compatibility = self._replacement_evidence()
        if compatibility["evidence_digest"] != plan["replacement"]["evidence_digest"]:
            raise Refusal(
                RefusalCode.SPEC_REPLACEMENT_INCOMPATIBLE,
                "Looker replacement compatibility drifted before reconciliation.",
            )
        validation = self.validate(plan, apply_value)
        snapshot, _ = self._snapshot_bundle(
            expected_identity=_mapping(plan["native_identity"])
        )
        if (
            not self._matches_after(plan, snapshot)
            or snapshot["look"]["query_id"] != apply_value["after_query_id"]
        ):
            raise Refusal(
                RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
                "The validated saved Look changed during reconciliation.",
            )
        legacy = _datahub_edge_observation(
            legacy_snapshot,
            datahub_urn=str(plan["datahub_urn"]),
            expected_campaign_id=str(plan["campaign_id"]),
            expected_field=_reference_field(str(plan["references"]["legacy"])),
            require_live=require_live,
        )
        replacement = _datahub_edge_observation(
            replacement_snapshot,
            datahub_urn=str(plan["datahub_urn"]),
            expected_campaign_id=str(plan["campaign_id"]),
            expected_field=_reference_field(str(plan["references"]["replacement"])),
            require_live=require_live,
        )
        if legacy["state"] == "FIELD_EDGE_PRESENT":
            raise Refusal(
                RefusalCode.RECONCILIATION_SCOPE_MISMATCH,
                "Fresh DataHub evidence still contains the exact legacy field edge.",
                {
                    "datahub_urn": plan["datahub_urn"],
                    "legacy_snapshot_digest": legacy["snapshot_digest"],
                },
            )
        field_closure = (
            "SUPPORTED_BY_NATIVE_AND_EXACT_REPLACEMENT_EDGE"
            if replacement["state"] == "FIELD_EDGE_PRESENT"
            else "NOT_CLAIMED_CONNECTOR_LIMITATION"
        )
        limitations = list(plan["limitations"])
        if legacy["state"] != "NOT_OBSERVED":
            limitations.append(
                "Legacy dependency remains visible only at table level; its "
                "field-level state is unproven."
            )
        if replacement["state"] != "FIELD_EDGE_PRESENT":
            limitations.append(
                "DataHub did not expose an exact replacement field edge; native "
                "validation remains separate and no graph closure is claimed."
            )
        capabilities = preflight["capabilities"]
        effective = [
            capability
            for capability in ("read", "plan", "apply", "validate", "compensate")
            if capabilities[capability]
        ]
        return with_digest(
            {
                "schema_version": "1.0.0",
                "result": "PASSED",
                "mode": preflight["mode"],
                "captured_at": snapshot["captured_at"],
                "source": {
                    "id": (
                        f"looker:{snapshot['native_identity']['platform_instance']}"
                    ),
                    "required": True,
                    "identity": preflight["configuration"]["base_url_identity"],
                    "source_version": snapshot["source_version"],
                    "source_updated_at": (
                        snapshot["look"]["updated_at"] or snapshot["captured_at"]
                    ),
                    "principal": preflight["principal"]["id_digest"],
                    "effective_capabilities": effective,
                },
                "native_identity": snapshot["native_identity"],
                "native_state": {
                    "content_fingerprint": snapshot["content_fingerprint"],
                    "query_id": snapshot["look"]["query_id"],
                    "query_fingerprint": snapshot["query"]["fingerprint"],
                    "schedule_fingerprint": snapshot["schedules"]["fingerprint"],
                },
                "plan_digest": plan["plan_digest"],
                "apply_digest": apply_value["apply_digest"],
                "receipt_digest": receipt_value["receipt_digest"],
                "preflight_digest": preflight["preflight_digest"],
                "native_validation": validation,
                "datahub_edges": {
                    "legacy": legacy,
                    "replacement": replacement,
                    "field_closure": field_closure,
                    "disappearance_alone_is_closure": False,
                },
                "limitations": sorted(set(limitations)),
            },
            "reconciliation_digest",
        )

    def compensate(
        self,
        plan: Mapping[str, Any],
        apply_record: Mapping[str, Any],
        *,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        self._validate_plan(plan)
        apply_value = dict(apply_record)
        verify_digest(apply_value, "apply_digest")
        if apply_value.get("plan_digest") != plan["plan_digest"]:
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
                "The Looker compensation input belongs to another plan.",
            )
        if not self.settings.allow_apply:
            raise Refusal(
                RefusalCode.AUTH_APPLY_DISABLED,
                "Looker compensation is disabled by configuration.",
            )
        current, _ = self._snapshot_bundle(
            expected_identity=_mapping(plan["native_identity"])
        )
        before_query_id = str(apply_value["before_query_id"])
        if (
            self._matches_before(plan, current)
            and current["look"]["query_id"] == before_query_id
        ):
            return self._compensation_record(
                plan,
                apply_value,
                current,
                occurred_at=occurred_at or self.clock(),
                recovery="native_reread",
            )
        if (
            not self._matches_after(plan, current)
            or current["look"]["query_id"] != apply_value["after_query_id"]
        ):
            raise Refusal(
                RefusalCode.COMPENSATION_CONFLICT,
                "The saved Look changed after apply; compensation preserved the "
                "intervening native edit.",
                {
                    "expected_fingerprint": apply_value["after_fingerprint"],
                    "actual_fingerprint": current["content_fingerprint"],
                },
            )
        self.client.request(
            "PATCH",
            f"/looks/{self.settings.look_id}",
            body={"query_id": before_query_id},
            mutation=True,
        )
        restored, _ = self._snapshot_bundle(
            expected_identity=_mapping(plan["native_identity"])
        )
        if (
            not self._matches_before(plan, restored)
            or restored["look"]["query_id"] != before_query_id
        ):
            raise Refusal(
                RefusalCode.APPLY_OUTCOME_UNKNOWN,
                "Looker compensation returned without the exact original query "
                "state; a later native reread is required.",
            )
        return self._compensation_record(
            plan,
            apply_value,
            restored,
            occurred_at=occurred_at or self.clock(),
            recovery=None,
        )

    def emit_receipt(
        self,
        plan: Mapping[str, Any],
        apply_record: Mapping[str, Any],
        validation: Mapping[str, Any],
        *,
        compensation: Mapping[str, Any] | None,
        captured_at: str,
        expires_at: str | None,
        artifact_ids: Sequence[str],
    ) -> dict[str, Any]:
        self._validate_plan(plan)
        apply_value = dict(apply_record)
        validation_value = dict(validation)
        verify_digest(apply_value, "apply_digest")
        verify_digest(validation_value, "validation_digest")
        if apply_value.get("plan_digest") != plan["plan_digest"]:
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
                "The Looker receipt apply record belongs to another plan.",
            )
        if validation_value["result"] != "PASSED":
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_FAILED,
                "Only passing native Looker validation can emit a receipt.",
            )
        compensation_value = {
            "available": True,
            "exercised": compensation is not None,
            "result": "NOT_NEEDED",
        }
        if compensation is not None:
            compensation_record = dict(compensation)
            verify_digest(compensation_record, "compensation_digest")
            if (
                compensation_record.get("plan_digest") != plan["plan_digest"]
                or compensation_record.get("apply_digest")
                != apply_value["apply_digest"]
            ):
                raise Refusal(
                    RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
                    "The Looker compensation record belongs to another plan or "
                    "apply operation.",
                )
            compensation_value["result"] = (
                "RESTORED" if compensation_record["result"] == "RESTORED" else "FAILED"
            )
        receipt = with_digest(
            {
                "schema_version": "1.0.0",
                "receipt_id": (
                    f"looker-{plan['consumer_id']}-"
                    f"{str(apply_value['after_query_id'])[:16]}"
                ),
                "campaign_id": plan["campaign_id"],
                "consumer_id": plan["consumer_id"],
                "datahub_urn": plan["datahub_urn"],
                "native_identity": plan["native_identity"],
                "adapter": {
                    "name": "looker",
                    "version": ADAPTER_VERSION,
                    "mode": self.settings.mode,
                },
                "source_before": {
                    "version": plan["source"]["version"],
                    "fingerprint": plan["source"]["fingerprint"],
                },
                "plan": {
                    "digest": plan["plan_digest"],
                    "proposed_targets": plan["target_sets"]["proposed"],
                    "approved_targets": plan["target_sets"]["approved"],
                },
                "apply": {
                    "result": "APPLIED",
                    "actual_targets": apply_value["actual_targets"],
                    "before_fingerprint": apply_value["before_fingerprint"],
                    "after_fingerprint": apply_value["after_fingerprint"],
                    "native_change_ids": apply_value["native_change_ids"],
                },
                "validation": {
                    "result": "PASSED",
                    "validator": validation_value["validator"],
                    "validator_version": validation_value["validator_version"],
                    "artifact_ids": sorted(set(artifact_ids)),
                },
                "compensation": compensation_value,
                "captured_at": captured_at,
                "expires_at": expires_at,
                "limitations": list(plan["limitations"]),
                "terminal_disposition": ConsumerDisposition.VALIDATED,
            },
            "receipt_digest",
        )
        validate_schema(
            "consumer-receipt",
            receipt,
            refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
        )
        return receipt

    def _snapshot_bundle(
        self,
        *,
        expected_identity: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        look = _object(
            self.client.request("GET", f"/looks/{self.settings.look_id}"),
            operation="read exact saved Look",
        )
        query_value = look.get("query")
        if isinstance(query_value, Mapping):
            query = dict(query_value)
        else:
            query_id = _required_string(
                look,
                "query_id",
                operation="saved Look query identity",
            )
            query = _object(
                self.client.request("GET", f"/queries/{query_id}"),
                operation="read immutable Look query",
            )
        identity = self._native_identity(look, query)
        if expected_identity is not None and identity != dict(expected_identity):
            raise Refusal(
                RefusalCode.IDENTITY_NATIVE_OBJECT_RECREATED,
                "The current saved Look does not match the immutable authorized "
                "native identity.",
                {
                    "expected_identity_digest": digest_json(expected_identity),
                    "actual_identity_digest": digest_json(identity),
                },
            )
        query_body = _query_body(query)
        schedules = self._schedules()
        merge_query_id = look.get("merge_query_id")
        dynamic_fields = query_body.get("dynamic_fields")
        has_calculations = bool(
            query.get("has_table_calculations")
            or dynamic_fields not in (None, "", "[]", [])
        )
        relevance = {
            "schedules": {
                "status": "EVALUATED",
                "count": schedules["count"],
                "policy": "must_be_empty",
            },
            "filters": {
                "status": "EVALUATED",
                "present": bool(
                    query_body.get("filters")
                    or query_body.get("filter_expression")
                    or query_body.get("filter_config")
                ),
                "included_in_query_fingerprint": True,
            },
            "calculations": {
                "status": "EVALUATED",
                "present": has_calculations,
                "policy": "unsupported_and_refused",
            },
            "alerts": {
                "status": "NOT_APPLICABLE",
                "reason": (
                    "Looker API alerts are dashboard-scoped, not saved-Look scoped"
                ),
            },
            "merged_result": {
                "status": "EVALUATED",
                "present": bool(merge_query_id),
                "policy": "unsupported_and_refused",
            },
        }
        query_fingerprint = digest_json(query_body)
        look_public = {
            "id": _required_string(look, "id", operation="saved Look"),
            "content_metadata_id": _required_string(
                look,
                "content_metadata_id",
                operation="saved Look immutable identity",
            ),
            "created_at": _required_string(
                look,
                "created_at",
                operation="saved Look immutable identity",
            ),
            "updated_at": str(look.get("updated_at") or ""),
            "folder_id": _required_string(
                look,
                "folder_id",
                operation="saved Look folder",
            ),
            "query_id": _required_string(
                look,
                "query_id",
                operation="saved Look query identity",
            ),
            "deleted": bool(look.get("deleted", False)),
            "title_digest": digest_json(str(look.get("title") or "")),
        }
        look_public["state_fingerprint"] = digest_json(
            {
                "id": look_public["id"],
                "content_metadata_id": look_public["content_metadata_id"],
                "created_at": look_public["created_at"],
                "folder_id": look_public["folder_id"],
                "deleted": look_public["deleted"],
                "title_digest": look_public["title_digest"],
            }
        )
        content_fingerprint = _content_fingerprint(
            identity=identity,
            look=look_public,
            query_fingerprint=query_fingerprint,
            schedules=schedules,
            relevance=relevance,
        )
        public = {
            "schema_version": "1.0.0",
            "captured_at": self.clock(),
            "native_identity": identity,
            "look": look_public,
            "query": {
                "fingerprint": query_fingerprint,
                "model": str(query.get("model") or ""),
                "view": str(query.get("view") or ""),
                "legacy_occurrences": _reference_count(
                    query_body,
                    self.settings.legacy_reference,
                ),
                "replacement_occurrences": _reference_count(
                    query_body,
                    self.settings.replacement_reference,
                ),
            },
            "schedules": schedules,
            "relevance": relevance,
            "content_fingerprint": content_fingerprint,
            "source_version": (
                f"{look_public['updated_at']}:{look_public['query_id']}"
            ),
        }
        return public, query_body

    def _native_identity(
        self,
        look: Mapping[str, Any],
        query: Mapping[str, Any],
    ) -> dict[str, Any]:
        query_model = _required_string(query, "model", operation="Looker query")
        query_explore = _required_string(query, "view", operation="Looker query")
        model = _object(
            self.client.request(
                "GET",
                f"/lookml_models/{query_model}",
                query={"fields": "name,project_name"},
            ),
            operation="read LookML model identity",
        )
        identity = {
            "source_domain": "looker",
            "content_type": "look",
            "platform_instance": self.settings.platform_instance,
            "project_id": _required_string(
                model,
                "project_name",
                operation="LookML project identity",
            ),
            "model_id": query_model,
            "explore_id": query_explore,
            "folder_id": _required_string(
                look,
                "folder_id",
                operation="saved Look folder",
            ),
            "content_id": _required_string(
                look,
                "id",
                operation="saved Look identity",
            ),
            "content_metadata_id": _required_string(
                look,
                "content_metadata_id",
                operation="saved Look immutable identity",
            ),
            "created_at": _required_string(
                look,
                "created_at",
                operation="saved Look immutable identity",
            ),
            "datahub_urn": self.settings.datahub_urn,
        }
        expected = {
            "project_id": self.settings.project_id,
            "model_id": self.settings.model_id,
            "explore_id": self.settings.explore_id,
            "folder_id": self.settings.folder_id,
            "content_id": self.settings.look_id,
        }
        actual = {key: identity[key] for key in expected}
        if actual != expected:
            raise Refusal(
                RefusalCode.IDENTITY_NOT_FOUND,
                "The configured DataHub consumer did not resolve to the exact "
                "native saved Look scope.",
                {
                    "expected_scope_digest": digest_json(expected),
                    "actual_scope_digest": digest_json(actual),
                },
            )
        return identity

    def _replacement_evidence(self) -> dict[str, Any]:
        explore = _object(
            self.client.request(
                "GET",
                (
                    f"/lookml_models/{self.settings.model_id}/explores/"
                    f"{self.settings.explore_id}"
                ),
                query={"fields": "id,name,fields"},
            ),
            operation="read LookML Explore fields",
        )
        fields = _flatten_explore_fields(explore.get("fields"))
        target = _exact_field(fields, self.settings.legacy_reference)
        replacement = _exact_field(fields, self.settings.replacement_reference)
        target_shape = _field_shape(target)
        replacement_shape = _field_shape(replacement)
        compatible = (
            target_shape["category"] == replacement_shape["category"]
            and target_shape["type"] == replacement_shape["type"]
            and target_shape["is_numeric"] == replacement_shape["is_numeric"]
        )
        if not compatible:
            raise Refusal(
                RefusalCode.SPEC_REPLACEMENT_INCOMPATIBLE,
                "The LookML Explore fields are not intentionally compatible.",
                {
                    "target_shape": target_shape,
                    "replacement_shape": replacement_shape,
                },
            )
        evidence = {
            "target": target_shape,
            "replacement": replacement_shape,
            "compatible": True,
            "explore_field_count": len(fields),
        }
        return {
            **evidence,
            "evidence_digest": digest_json(evidence),
        }

    def _schedules(self) -> dict[str, Any]:
        values = _array(
            self.client.request(
                "GET",
                f"/scheduled_plans/look/{self.settings.look_id}",
                query={
                    "fields": (
                        "id,look_id,query_id,enabled,run_as_recipient,"
                        "filters_string,created_at,updated_at"
                    )
                },
            ),
            operation="read saved Look schedules",
        )
        normalized = sorted(
            [
                {
                    "id": _required_string(
                        schedule,
                        "id",
                        operation="scheduled plan",
                    ),
                    "look_id": str(schedule.get("look_id") or ""),
                    "query_id": str(schedule.get("query_id") or ""),
                    "enabled": bool(schedule.get("enabled", False)),
                    "run_as_recipient": bool(schedule.get("run_as_recipient", False)),
                    "filters_digest": digest_json(
                        str(schedule.get("filters_string") or "")
                    ),
                    "created_at": str(schedule.get("created_at") or ""),
                    "updated_at": str(schedule.get("updated_at") or ""),
                }
                for schedule in values
            ],
            key=lambda item: str(item["id"]),
        )
        return {
            "count": len(normalized),
            "items": normalized,
            "fingerprint": digest_json(normalized),
        }

    def _scan_folder_targets(self, reference: str) -> dict[str, Any]:
        targets: set[str] = set()
        pages: list[dict[str, int]] = []
        offset = 0
        for _ in range(self.settings.max_pages):
            values = _array(
                self.client.request(
                    "GET",
                    "/looks/search",
                    query={
                        "folder_id": self.settings.folder_id,
                        "limit": self.settings.page_size,
                        "offset": offset,
                        "fields": (
                            "id,folder_id,query_id,query,content_metadata_id,"
                            "created_at,deleted"
                        ),
                    },
                ),
                operation="page saved Looks in exact folder",
            )
            pages.append({"offset": offset, "returned": len(values)})
            for value in values:
                look = _object(value, operation="folder Look result")
                query_value = look.get("query")
                if isinstance(query_value, Mapping):
                    query = dict(query_value)
                else:
                    query_id = _required_string(
                        look,
                        "query_id",
                        operation="folder Look query identity",
                    )
                    query = _object(
                        self.client.request("GET", f"/queries/{query_id}"),
                        operation="read folder Look query",
                    )
                if _contains_reference(_query_body(query), reference):
                    targets.add(
                        f"look:{_required_string(look, 'id', operation='folder Look')}"
                    )
            if len(values) < self.settings.page_size:
                return {
                    "targets": sorted(targets),
                    "pages": pages,
                    "page_count": len(pages),
                    "returned_total": sum(page["returned"] for page in pages),
                    "pagination_complete": True,
                    "folder_id": self.settings.folder_id,
                }
            offset += len(values)
        raise Refusal(
            RefusalCode.EVIDENCE_PAGINATION_FAILED,
            "Looker folder discovery exceeded the configured page bound.",
            {
                "page_size": self.settings.page_size,
                "max_pages": self.settings.max_pages,
            },
        )

    def _content_validation(self) -> dict[str, Any]:
        value = _object(
            self.client.request(
                "GET",
                "/content_validation",
                query={
                    "project_names": [self.settings.project_id],
                    "space_ids": [self.settings.folder_id],
                },
            ),
            operation="run scoped Looker Content Validation",
        )
        errors = value.get("content_with_errors")
        error_values = list(errors) if isinstance(errors, list) else []
        return {
            "scope": {
                "project_names": [self.settings.project_id],
                "space_ids": [self.settings.folder_id],
            },
            "error_count": len(error_values),
            "errors_digest": digest_json(error_values),
            "total_looks_validated": _integer_value(value.get("total_looks_validated")),
            "total_dashboard_elements_validated": _integer_value(
                value.get("total_dashboard_elements_validated")
            ),
            "total_dashboards_validated": _integer_value(
                value.get("total_dashboards_validated")
            ),
            "computation_time": value.get("computation_time"),
        }

    def _run_look(self) -> dict[str, Any]:
        result = self.client.request(
            "GET",
            f"/looks/{self.settings.look_id}/run/json",
            query={
                "limit": self.settings.query_limit,
                "cache": "false",
                "force_production": "true",
            },
        )
        row_count = len(result) if isinstance(result, list) else None
        normalized = _replace_reference(
            result,
            self.settings.replacement_reference,
            self.settings.legacy_reference,
        )
        return {
            "row_count": row_count,
            "row_limit": self.settings.query_limit,
            "cache": False,
            "force_production": True,
            "semantic_digest": digest_json(normalized),
            "raw_result_retained": False,
        }

    def _require_safe_relevance(self, snapshot: Mapping[str, Any]) -> None:
        relevance = _mapping(snapshot["relevance"])
        schedules = _mapping(relevance["schedules"])
        calculations = _mapping(relevance["calculations"])
        merged = _mapping(relevance["merged_result"])
        if schedules["count"]:
            raise Refusal(
                RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                "Saved Look schedules require a broader owner-managed migration.",
                {"schedule_count": schedules["count"]},
            )
        if calculations["present"]:
            raise Refusal(
                RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                "Table calculations or dynamic fields are outside the bounded "
                "saved-Look mutation contract.",
            )
        if merged["present"]:
            raise Refusal(
                RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                "Merged-result content is outside the bounded saved-Look mutation "
                "contract.",
            )

    def _validate_plan(self, plan: Mapping[str, Any]) -> None:
        value = dict(plan)
        validate_schema(
            "looker-plan",
            value,
            refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
        )
        verify_digest(value, "plan_digest")
        if (
            value["datahub_urn"] != self.settings.datahub_urn
            or value["graph_snapshot_digest"] != self.settings.graph_snapshot_digest
            or value["target_sets"]["approved"] != [self.settings.content_target]
            or value["references"]["legacy"] != self.settings.legacy_reference
            or value["references"]["replacement"] != self.settings.replacement_reference
            or value["adapter"]["mode"] != self.settings.mode
        ):
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
                "The Looker configuration is not bound to the current plan.",
            )

    @staticmethod
    def _validate_intent(
        plan: Mapping[str, Any],
        intent: Mapping[str, Any],
    ) -> None:
        value = dict(intent)
        verify_digest(value, "intent_digest")
        if (
            value.get("plan_digest") != plan["plan_digest"]
            or value.get("campaign_id") != plan["campaign_id"]
            or value.get("native_identity_digest")
            != digest_json(plan["native_identity"])
            or value.get("before_fingerprint") != plan["source"]["fingerprint"]
            or value.get("after_fingerprint") != plan["references"]["after_fingerprint"]
            or value.get("status")
            not in {
                "PENDING",
                "OUTCOME_UNKNOWN",
                "RESOLVED",
            }
        ):
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
                "The durable Looker mutation intent is not bound to the plan.",
            )

    @staticmethod
    def _matches_before(
        plan: Mapping[str, Any],
        snapshot: Mapping[str, Any],
    ) -> bool:
        return bool(
            snapshot["content_fingerprint"] == plan["source"]["fingerprint"]
            and snapshot["look"]["query_id"] == plan["source"]["query_id"]
            and snapshot["query"]["fingerprint"] == plan["source"]["query_fingerprint"]
            and snapshot["schedules"]["fingerprint"]
            == plan["source"]["schedule_fingerprint"]
            and snapshot["look"]["state_fingerprint"]
            == plan["source"]["look_state_fingerprint"]
        )

    @staticmethod
    def _matches_after(
        plan: Mapping[str, Any],
        snapshot: Mapping[str, Any],
    ) -> bool:
        return bool(
            snapshot["content_fingerprint"] == plan["references"]["after_fingerprint"]
            and snapshot["query"]["fingerprint"]
            == plan["references"]["after_query_fingerprint"]
            and snapshot["schedules"]["fingerprint"]
            == plan["source"]["schedule_fingerprint"]
            and snapshot["look"]["state_fingerprint"]
            == plan["source"]["look_state_fingerprint"]
        )

    def _apply_record(
        self,
        plan: Mapping[str, Any],
        snapshot: Mapping[str, Any],
        *,
        before_query_id: str,
        after_query_id: str,
        occurred_at: str,
        recovery: str | None,
    ) -> dict[str, Any]:
        return with_digest(
            {
                "schema_version": "1.0.0",
                "result": "APPLIED",
                "campaign_id": plan["campaign_id"],
                "consumer_id": plan["consumer_id"],
                "plan_digest": plan["plan_digest"],
                "actual_targets": [self.settings.content_target],
                "actual_changed_fields": ["query_id"],
                "before_fingerprint": plan["source"]["fingerprint"],
                "after_fingerprint": snapshot["content_fingerprint"],
                "before_query_id": before_query_id,
                "after_query_id": after_query_id,
                "native_change_ids": [after_query_id],
                "source_version_after": snapshot["source_version"],
                "recovery": recovery,
                "automatic_mutation_retry": False,
                "occurred_at": occurred_at,
            },
            "apply_digest",
        )

    def _compensation_record(
        self,
        plan: Mapping[str, Any],
        apply_record: Mapping[str, Any],
        snapshot: Mapping[str, Any],
        *,
        occurred_at: str,
        recovery: str | None,
    ) -> dict[str, Any]:
        return with_digest(
            {
                "schema_version": "1.0.0",
                "result": "RESTORED",
                "campaign_id": plan["campaign_id"],
                "consumer_id": plan["consumer_id"],
                "plan_digest": plan["plan_digest"],
                "apply_digest": apply_record["apply_digest"],
                "target": self.settings.content_target,
                "restored_query_id": snapshot["look"]["query_id"],
                "restored_fingerprint": snapshot["content_fingerprint"],
                "verified": True,
                "recovery": recovery,
                "occurred_at": occurred_at,
            },
            "compensation_digest",
        )


def merge_looker_evidence(
    datahub_envelope: Mapping[str, Any],
    preflight: Mapping[str, Any],
    native_snapshot: Mapping[str, Any],
    *,
    artifact_ids: Sequence[str],
    prior_envelope: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Join fresh Looker evidence while making unreread prior sources stale."""

    datahub_value = dict(datahub_envelope)
    preflight_value = dict(preflight)
    snapshot_value = dict(native_snapshot)
    verify_digest(datahub_value, "envelope_digest")
    verify_digest(preflight_value, "preflight_digest")
    verify_digest(snapshot_value, "snapshot_digest")
    source_id = f"looker:{snapshot_value['native_identity']['platform_instance']}"
    sources = [
        dict(source) for source in datahub_value["sources"] if source["id"] != source_id
    ]
    if prior_envelope is not None:
        prior_value = dict(prior_envelope)
        verify_digest(prior_value, "envelope_digest")
        incoming_ids = {str(source["id"]) for source in sources}
        for raw_source in prior_value["sources"]:
            prior_source = dict(raw_source)
            prior_id = str(prior_source["id"])
            if prior_id in incoming_ids or prior_id == source_id:
                continue
            sources.append(
                {
                    **prior_source,
                    "status": "STALE",
                    "freshness": {
                        **dict(prior_source["freshness"]),
                        "observed_at": snapshot_value["captured_at"],
                    },
                    "limitations": sorted(
                        {
                            *prior_source["limitations"],
                            (
                                "This prior source was not reread during the "
                                "Looker inventory extension"
                            ),
                        }
                    ),
                }
            )
    capabilities = preflight_value["capabilities"]
    effective = [
        capability
        for capability in ("read", "plan", "apply", "validate", "compensate")
        if capabilities[capability]
    ]
    missing_ingestion = preflight_value["datahub_ingestion_permission_check"]["missing"]
    limitations = [
        "The native scope contains exactly one saved Look.",
        "Looker query results are never retained by the adapter.",
    ]
    if missing_ingestion:
        limitations.append(
            "The adapter principal does not itself satisfy the separate DataHub "
            "Looker ingestion permission set."
        )
    sources.append(
        {
            "id": source_id,
            "required": True,
            "status": "COMPLETE",
            "source_version": snapshot_value["source_version"],
            "identity": preflight_value["configuration"]["base_url_identity"],
            "scope": {
                "direction": "downstream",
                "max_hops": 1,
                "filters": [
                    (
                        "instance:"
                        f"{snapshot_value['native_identity']['platform_instance']}"
                    ),
                    f"project:{snapshot_value['native_identity']['project_id']}",
                    f"model:{snapshot_value['native_identity']['model_id']}",
                    f"explore:{snapshot_value['native_identity']['explore_id']}",
                    f"folder:{snapshot_value['native_identity']['folder_id']}",
                    f"target:look:{snapshot_value['native_identity']['content_id']}",
                ],
                "pages": 1,
                "reported_total": 1,
                "returned_total": 1,
            },
            "freshness": {
                "observed_at": snapshot_value["captured_at"],
                "source_updated_at": (
                    snapshot_value["look"]["updated_at"]
                    or snapshot_value["captured_at"]
                ),
                "maximum_age_seconds": 86_400,
            },
            "permissions": {
                "principal": preflight_value["principal"]["id_digest"],
                "effective_scope": ",".join(effective),
            },
            "limitations": limitations,
            "artifact_ids": sorted(set(artifact_ids)),
        }
    )
    merged = with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": snapshot_value["captured_at"],
            "mode": datahub_value["mode"],
            "sources": sorted(sources, key=lambda source: str(source["id"])),
        },
        "envelope_digest",
    )
    validate_schema(
        "evidence-envelope",
        merged,
        refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
    )
    return merged


def merge_looker_reconciliation_evidence(
    evidence_envelope: Mapping[str, Any],
    observation: Mapping[str, Any],
    *,
    baseline_source: Mapping[str, Any],
) -> dict[str, Any]:
    """Join a fresh native Looker reread without changing declared scope."""

    envelope_value = dict(evidence_envelope)
    observation_value = dict(observation)
    verify_digest(envelope_value, "envelope_digest")
    verify_digest(observation_value, "reconciliation_digest")
    source = _mapping(observation_value["source"])
    source_id = str(source["id"])
    if (
        source_id != baseline_source["id"]
        or source["identity"] != baseline_source["identity"]
        or bool(source["required"]) != bool(baseline_source["required"])
    ):
        raise Refusal(
            RefusalCode.RECONCILIATION_SCOPE_MISMATCH,
            "The native Looker source identity changed during reconciliation.",
        )
    sources = [
        dict(item) for item in envelope_value["sources"] if item["id"] != source_id
    ]
    sources.append(
        {
            "id": source_id,
            "required": bool(baseline_source["required"]),
            "status": "COMPLETE",
            "source_version": source["source_version"],
            "identity": source["identity"],
            "scope": dict(baseline_source["scope"]),
            "freshness": {
                "observed_at": observation_value["captured_at"],
                "source_updated_at": source["source_updated_at"],
                "maximum_age_seconds": baseline_source["freshness"][
                    "maximum_age_seconds"
                ],
            },
            "permissions": {
                "principal": source["principal"],
                "effective_scope": ",".join(source["effective_capabilities"]),
            },
            "limitations": list(observation_value["limitations"]),
            "artifact_ids": sorted(
                {
                    observation_value["reconciliation_digest"],
                    observation_value["native_validation"]["validation_digest"],
                }
            ),
        }
    )
    merged = with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": observation_value["captured_at"],
            "mode": envelope_value["mode"],
            "sources": sorted(sources, key=lambda item: str(item["id"])),
        },
        "envelope_digest",
    )
    validate_schema(
        "evidence-envelope",
        merged,
        refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
    )
    return merged


def _reference_field(reference: str) -> str:
    if "." not in reference:
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            "Looker field references must use view.field identity.",
        )
    return reference.rsplit(".", 1)[1]


def _datahub_edge_observation(
    snapshot: Mapping[str, Any],
    *,
    datahub_urn: str,
    expected_campaign_id: str,
    expected_field: str,
    require_live: bool,
) -> dict[str, Any]:
    value = dict(snapshot)
    verify_digest(value, "snapshot_digest")
    envelope = _mapping(value["evidence_envelope"])
    verify_digest(envelope, "envelope_digest")
    if value.get("campaign_id") != expected_campaign_id:
        raise Refusal(
            RefusalCode.AUTH_APPROVAL_WRONG_CAMPAIGN,
            "The DataHub edge snapshot belongs to another campaign.",
        )
    if require_live and envelope.get("mode") != "live":
        raise Refusal(
            RefusalCode.EVIDENCE_MODE_NOT_LIVE,
            "Live Looker reconciliation requires live DataHub edge evidence.",
        )
    datahub_sources = [
        _mapping(source)
        for source in envelope["sources"]
        if source.get("id") == "datahub"
    ]
    if (
        len(datahub_sources) != 1
        or datahub_sources[0].get("status") != "COMPLETE"
        or _mapping(value["pagination"]).get("status") != "COMPLETE"
    ):
        raise Refusal(
            RefusalCode.EVIDENCE_REQUIRED_SOURCE_INCOMPLETE,
            "The DataHub edge snapshot is incomplete or stale.",
        )
    target_field = _mapping(_mapping(value["resolution"])["target_field"])
    if target_field.get("fieldPath") != expected_field:
        raise Refusal(
            RefusalCode.IDENTITY_FIELD_NOT_FOUND,
            "The DataHub edge snapshot resolved a different field.",
            {
                "expected_field": expected_field,
                "observed_field": target_field.get("fieldPath"),
            },
        )
    dataset_urn = str(_mapping(_mapping(value["resolution"])["dataset"])["urn"])
    expected_claim_object = f"urn:li:schemaField:({dataset_urn},{expected_field})"
    matches = [
        _mapping(consumer)
        for consumer in value["consumers"]
        if consumer.get("datahub_urn") == datahub_urn
    ]
    if len(matches) > 1:
        raise Refusal(
            RefusalCode.IDENTITY_AMBIGUOUS,
            "The exact Looker URN appeared more than once in DataHub evidence.",
            {"match_count": len(matches)},
        )
    claims_by_id = {
        str(claim["claim_id"]): _mapping(claim)
        for claim in value["claims"]
        if isinstance(claim, Mapping) and isinstance(claim.get("claim_id"), str)
    }
    matching_claims: list[dict[str, Any]] = []
    if matches:
        for claim_id in matches[0].get("evidence_claim_ids", []):
            claim = claims_by_id.get(str(claim_id))
            if claim is not None and claim.get("subject") == datahub_urn:
                matching_claims.append(claim)
    exact_claims = [
        claim
        for claim in matching_claims
        if claim.get("confidence_basis") == "column_lineage_edge"
        and claim.get("object") == expected_claim_object
    ]
    if exact_claims:
        state = "FIELD_EDGE_PRESENT"
        limitations: list[str] = []
    elif matches:
        state = "TABLE_EDGE_ONLY"
        limitations = [
            "DataHub exposed only table-level lineage for the exact Looker URN."
        ]
    else:
        state = "NOT_OBSERVED"
        limitations = [
            "Absence is bounded by the recorded DataHub source and scope and is "
            "not native closure evidence."
        ]
    return with_digest(
        {
            "state": state,
            "datahub_urn": datahub_urn,
            "field": expected_field,
            "snapshot_digest": value["snapshot_digest"],
            "consumer_match_count": len(matches),
            "field_claim_count": len(exact_claims),
            "limitations": limitations,
        },
        "edge_digest",
    )


def _query_items(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _http_refusal(
    status: int,
    *,
    method: str,
    path: str,
    retry_count: int,
    mutation: bool,
) -> Refusal:
    details = {
        "status": status,
        "method": method,
        "path": path,
        "retry_count": retry_count,
    }
    if mutation and (status >= 500 or status in {408, 425}):
        return Refusal(
            RefusalCode.APPLY_OUTCOME_UNKNOWN,
            "Looker returned an ambiguous mutation failure; native reread is required.",
            details,
        )
    if status in {401, 403}:
        return Refusal(
            RefusalCode.SOURCE_LOOKER_PERMISSION_DENIED,
            "Looker denied the requested capability.",
            details,
        )
    if status == 404:
        return Refusal(
            RefusalCode.IDENTITY_NOT_FOUND,
            "The exact Looker native object was not found.",
            details,
        )
    if status == 422:
        return Refusal(
            RefusalCode.VALIDATION_RECEIPT_FAILED,
            "Looker rejected the documented request as invalid.",
            details,
        )
    return Refusal(
        RefusalCode.SOURCE_LOOKER_UNAVAILABLE,
        "The Looker API request failed.",
        details,
    )


def _object(value: Any, *, operation: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise Refusal(
            RefusalCode.SOURCE_LOOKER_UNAVAILABLE,
            f"Looker returned an invalid object while attempting to {operation}.",
        )
    return dict(value)


def _array(value: Any, *, operation: str) -> list[Any]:
    if not isinstance(value, list):
        raise Refusal(
            RefusalCode.SOURCE_LOOKER_UNAVAILABLE,
            f"Looker returned an invalid list while attempting to {operation}.",
        )
    return value


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _required_string(
    value: Mapping[str, Any],
    key: str,
    *,
    operation: str,
) -> str:
    result = value.get(key)
    if not isinstance(result, (str, int)) or not str(result):
        raise Refusal(
            RefusalCode.IDENTITY_NOT_FOUND,
            f"Looker omitted {key} while resolving {operation}.",
        )
    return str(result)


def _nested_sequence(
    value: Any,
    outer: str,
    inner: str,
) -> list[Any]:
    mapping = _mapping(value)
    nested = _mapping(mapping.get(outer))
    result = nested.get(inner)
    return list(result) if isinstance(result, list) else []


def _query_body(query: Mapping[str, Any]) -> dict[str, Any]:
    return {key: query[key] for key in QUERY_CREATE_FIELDS if key in query}


def _reference_pattern(reference: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Za-z0-9_]){re.escape(reference)}(?![A-Za-z0-9_])")


def _contains_reference(value: Any, reference: str) -> bool:
    if isinstance(value, str):
        return _reference_pattern(reference).search(value) is not None
    if isinstance(value, list):
        return any(_contains_reference(item, reference) for item in value)
    if isinstance(value, Mapping):
        return any(
            _contains_reference(key, reference) or _contains_reference(item, reference)
            for key, item in value.items()
        )
    return False


def _reference_count(value: Any, reference: str) -> int:
    pattern = _reference_pattern(reference)
    if isinstance(value, str):
        return len(pattern.findall(value))
    if isinstance(value, list):
        return sum(_reference_count(item, reference) for item in value)
    if isinstance(value, Mapping):
        return sum(
            _reference_count(key, reference) + _reference_count(item, reference)
            for key, item in value.items()
        )
    return 0


def _replace_reference(value: Any, legacy: str, replacement: str) -> Any:
    pattern = _reference_pattern(legacy)
    if isinstance(value, str):
        return pattern.sub(replacement, value)
    if isinstance(value, list):
        return [_replace_reference(item, legacy, replacement) for item in value]
    if isinstance(value, Mapping):
        return {
            _replace_reference(key, legacy, replacement): _replace_reference(
                item,
                legacy,
                replacement,
            )
            for key, item in value.items()
        }
    return value


def _changed_query_fields(
    query: Mapping[str, Any],
    *,
    legacy: str,
    replacement: str,
) -> list[str]:
    return sorted(
        key
        for key, value in query.items()
        if _replace_reference(value, legacy, replacement) != value
        or _replace_reference(key, legacy, replacement) != key
    )


def _content_fingerprint(
    *,
    identity: Mapping[str, Any],
    look: Mapping[str, Any],
    query_fingerprint: str,
    schedules: Mapping[str, Any],
    relevance: Mapping[str, Any],
) -> str:
    return digest_json(
        {
            "native_identity": identity,
            "look_state_fingerprint": look["state_fingerprint"],
            "query_fingerprint": query_fingerprint,
            "schedule_fingerprint": schedules["fingerprint"],
            "relevance": relevance,
        }
    )


def _flatten_explore_fields(value: Any) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        for group in value.values():
            if isinstance(group, list):
                fields.extend(dict(item) for item in group if isinstance(item, Mapping))
    elif isinstance(value, list):
        fields.extend(dict(item) for item in value if isinstance(item, Mapping))
    return fields


def _exact_field(
    fields: Sequence[Mapping[str, Any]],
    reference: str,
) -> dict[str, Any]:
    matches = [dict(field) for field in fields if field.get("name") == reference]
    if not matches:
        raise Refusal(
            RefusalCode.IDENTITY_FIELD_NOT_FOUND,
            "The configured LookML field was not found in the exact Explore.",
            {"field_reference": reference, "available_field_count": len(fields)},
        )
    if len(matches) != 1:
        raise Refusal(
            RefusalCode.IDENTITY_FIELD_AMBIGUOUS,
            "The configured LookML field resolved more than once.",
            {"field_reference": reference, "match_count": len(matches)},
        )
    return matches[0]


def _field_shape(field: Mapping[str, Any]) -> dict[str, Any]:
    name = str(field.get("name") or "")
    category = str(field.get("category") or "")
    field_type = str(field.get("type") or "")
    if not name or not category or not field_type:
        raise Refusal(
            RefusalCode.SPEC_REPLACEMENT_INCOMPATIBLE,
            "Looker field metadata is insufficient for a compatibility decision.",
        )
    return {
        "name": name,
        "category": category,
        "type": field_type,
        "is_numeric": bool(field.get("is_numeric", False)),
    }


def _integer_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError) as exc:
        raise Refusal(
            RefusalCode.SOURCE_LOOKER_UNAVAILABLE,
            "Looker Content Validation returned a non-numeric count.",
        ) from exc
