"""Fail-closed producer plan preparation and one-time gate execution."""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from retirement_conductor.canonical import (
    digest_file,
    digest_json,
    verify_digest,
    with_digest,
)
from retirement_conductor.clock import parse_timestamp, validate_trusted_clock
from retirement_conductor.datahub import (
    DataHubBoundary,
    render_campaign_summary,
    timestamp_age_seconds,
    utc_now,
)
from retirement_conductor.errors import Refusal
from retirement_conductor.git_dbt import (
    GitDbtAdapter,
    checked_target_path,
    load_object,
    merge_repository_reconciliation_evidence,
    write_versioned_artifact,
)
from retirement_conductor.policy import default_policy
from retirement_conductor.postgres_producer import (
    ACTION_TYPE as POSTGRES_ACTION_TYPE,
)
from retirement_conductor.postgres_producer import (
    PostgresActionOutcome,
    PostgresClientProtocol,
    PostgresProducerAction,
    target_from_mapping,
)
from retirement_conductor.postgres_producer_config import PostgresTarget
from retirement_conductor.publication import publication_source_manifest
from retirement_conductor.reconciliation import scope_signature
from retirement_conductor.records import (
    require_bound_inputs,
    validate_approval,
    validate_consumer_receipt,
)
from retirement_conductor.schemas import validate_schema
from retirement_conductor.store import CampaignStore
from retirement_conductor.superset_config import SupersetSettings
from retirement_conductor.superset_gate import (
    SupersetGateClient,
    SupersetGateVerifier,
    capture_superset_gate_binding,
)
from retirement_conductor.vocabulary import (
    CampaignState,
    ConsumerDisposition,
    Decision,
    EvidenceStatus,
    RefusalCode,
)

SAFE_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
MAXIMUM_PLAN_LIFETIME = timedelta(minutes=15)


@dataclass(frozen=True)
class TrustedProducerContext:
    """Safe identity facts supplied by the producer workflow trust boundary."""

    run_id: str
    provider: str
    trusted: bool

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> TrustedProducerContext:
        values = os.environ if environment is None else environment
        trusted_text = (
            values.get(
                "RETIREMENT_CONDUCTOR_TRUSTED_CONTEXT",
                "false",
            )
            .strip()
            .lower()
        )
        if trusted_text not in {"true", "false"}:
            raise Refusal(
                RefusalCode.GATE_PROVENANCE_UNTRUSTED,
                "The producer trust marker must be true or false.",
            )
        return cls(
            run_id=values.get(
                "RETIREMENT_CONDUCTOR_TRUSTED_RUN_ID",
                "",
            ).strip(),
            provider=values.get(
                "RETIREMENT_CONDUCTOR_TRUST_PROVIDER",
                "",
            ).strip(),
            trusted=trusted_text == "true",
        )


class ProducerGateWorkflow:
    """Bind and consume one exact harmless producer action."""

    def __init__(
        self,
        *,
        store: CampaignStore,
        artifact_directory: Path,
        producer_repository_root: Path,
        producer_source_marker: Path,
        sentinel_root: Path,
        boundary: DataHubBoundary | None,
        git_dbt: GitDbtAdapter | None,
        postgres_action: PostgresProducerAction | None = None,
        postgres_target: PostgresTarget | None = None,
        mutation_client_factory: Callable[[], PostgresClientProtocol] | None = None,
        superset_settings: SupersetSettings | None = None,
        superset_client: SupersetGateClient | None = None,
    ) -> None:
        self.store = store
        self.artifact_directory = artifact_directory
        self.producer_repository_root = producer_repository_root.resolve()
        self.producer_source_marker = producer_source_marker.resolve()
        self.sentinel_root = sentinel_root.resolve()
        self.boundary = boundary
        self.git_dbt = git_dbt
        self.postgres_action = postgres_action
        self.postgres_target = postgres_target
        self.mutation_client_factory = mutation_client_factory
        self.superset_settings = superset_settings
        self.superset_client = superset_client

    def prepare(
        self,
        campaign_id: str,
        *,
        context: TrustedProducerContext,
        expires_at: str,
        prepared_at: str | None = None,
        action_type: str = "write_public_safe_sentinel",
    ) -> dict[str, Any]:
        """Prepare a short-lived plan after readiness and publication verification."""

        operation_time = prepared_at or utc_now()
        self._require_context_identity(context)
        if not context.trusted:
            raise Refusal(
                RefusalCode.GATE_PROVENANCE_UNTRUSTED,
                "Producer plan preparation requires a trusted run context.",
            )
        self._validate_plan_window(
            prepared_at=operation_time,
            expires_at=expires_at,
            trusted_now=operation_time,
        )
        manifest = self.store.materialize(campaign_id)
        projection = self.store.projection(campaign_id)
        self._require_ready_manifest(manifest)
        publication = self._require_verified_publication(manifest)
        self._verify_campaign_inputs(campaign_id, projection.input_digests)
        self._validate_receipts_and_approvals(
            campaign_id,
            trusted_now=operation_time,
        )
        bindings = self._git_dbt_bindings(campaign_id)
        reconciliation_digest = self._reconciliation_digest(campaign_id)
        producer_source = self._producer_source()
        superset = self._capture_superset_bindings(
            campaign_id,
            trusted_now=operation_time,
        )
        action_identity = digest_json(
            [
                campaign_id,
                context.run_id,
                manifest["manifest_digest"],
                producer_source["version"],
            ]
        ).removeprefix("sha256:")[:20]
        if action_type == "write_public_safe_sentinel":
            if superset:
                raise Refusal(
                    RefusalCode.GATE_PLAN_INVALID,
                    (
                        "A Superset-bound producer plan requires the versioned "
                        "PostgreSQL action in this release."
                    ),
                )
            self._prepare_sentinel_root()
            relative_path = f"{campaign_id}/{context.run_id}-{action_identity}.json"
            action: dict[str, Any] = {
                "type": "write_public_safe_sentinel",
                "action_id": f"producer-sentinel-{action_identity}",
                "sentinel_root_identity": digest_json(str(self.sentinel_root)),
                "relative_path": relative_path,
            }
            schema_version = "1.0.0"
            limitations = [
                (
                    "The trusted run identity is deployment provenance, "
                    "not cryptographic authorship."
                ),
                (
                    "The producer action is a public-safe local sentinel; "
                    "it does not mutate a warehouse."
                ),
            ]
        elif action_type == POSTGRES_ACTION_TYPE:
            native_action, target = self._required_postgres_action()
            observation = native_action.observe(target)
            native_plan = native_action.plan(
                observation,
                actions=[target],
                action_expires_at=expires_at,
            )
            action = {
                "type": POSTGRES_ACTION_TYPE,
                "action_id": f"postgres-retirement-{action_identity}",
                "action_digest": native_plan["action_digest"],
                "postgres_action_plan": native_plan,
            }
            schema_version = "2.0.0"
            limitations = [
                (
                    "The trusted run identity is deployment provenance, "
                    "not cryptographic authorship."
                ),
                (
                    "The PostgreSQL action is confined to one allowlisted "
                    "disposable loopback tuple and never emits CASCADE."
                ),
                (
                    "The final external race is bounded by the native transaction "
                    "lock but cannot be eliminated across DataHub and PostgreSQL."
                ),
            ]
        else:
            raise Refusal(
                RefusalCode.GATE_PLAN_INVALID,
                "The requested producer action type is unsupported.",
                {"action_type": action_type},
            )
        plan = with_digest(
            {
                "schema_version": schema_version,
                "campaign_id": campaign_id,
                "prepared_at": operation_time,
                "expires_at": expires_at,
                "writer_id": self.store.writer_id,
                "trusted_run": {
                    "id": context.run_id,
                    "provider": context.provider,
                },
                "manifest": {
                    "digest": manifest["manifest_digest"],
                    "decision": manifest["decision"],
                    "specification_digest": manifest["specification_digest"],
                    "evidence_envelope_digest": manifest["evidence_envelope"][
                        "envelope_digest"
                    ],
                    "reconciliation_digest": reconciliation_digest,
                    "publication_content_digest": publication["content_digest"],
                    "published_manifest_digest": publication[
                        "published_manifest_digest"
                    ],
                    "input_digests": dict(projection.input_digests),
                    "receipt_digests": list(manifest["receipt_digests"]),
                },
                "producer_source": producer_source,
                "git_dbt": bindings["binding"],
                **({"superset": superset} if schema_version == "2.0.0" else {}),
                "action": action,
                "limitations": limitations,
            },
            "plan_digest",
        )
        self._validate_producer_plan(plan)
        self.store.issue_gate_plan(plan)
        write_versioned_artifact(
            self._producer_artifact_root(campaign_id),
            "plan",
            plan,
        )
        return {
            "result": "PRODUCER_PLAN_PREPARED",
            "plan": plan,
            "manifest": manifest,
        }

    def execute(
        self,
        campaign_id: str,
        *,
        context: TrustedProducerContext,
        plan_path: Path | None = None,
        executed_at: str | None = None,
    ) -> dict[str, Any]:
        """Verify live state, consume one plan, and execute its producer action."""

        operation_time = executed_at or utc_now()
        manifest = self.store.materialize(campaign_id)
        plan: dict[str, Any] | None = None
        intent_claimed = False
        try:
            self._require_ready_manifest(manifest)
            plan = self._load_producer_plan(
                plan_path or self._producer_artifact_root(campaign_id) / "plan.json"
            )
            self.store.require_issued_gate_plan(campaign_id, plan)
            self._verify_plan_context(
                campaign_id,
                manifest=manifest,
                plan=plan,
                context=context,
                trusted_now=operation_time,
            )
            self.store.require_unconsumed_gate_plan(
                campaign_id,
                plan_digest=str(plan["plan_digest"]),
            )
            verification = self._verify_ready_state(
                campaign_id,
                manifest=manifest,
                plan=plan,
                trusted_now=operation_time,
            )
            current_manifest = self.store.materialize(campaign_id)
            if current_manifest["manifest_digest"] != manifest["manifest_digest"]:
                raise Refusal(
                    RefusalCode.GATE_STATE_DRIFT,
                    "Campaign state changed during gate verification.",
                )
            if self._producer_source() != plan["producer_source"]:
                raise Refusal(
                    RefusalCode.GATE_SOURCE_DRIFT,
                    "The producer repository changed after plan preparation.",
                )
            action_type = str(plan["action"]["type"])
            sentinel_target: Path | None = None
            if action_type == "write_public_safe_sentinel":
                sentinel_target = self._sentinel_target(plan)
                if sentinel_target.exists() or sentinel_target.is_symlink():
                    raise Refusal(
                        RefusalCode.GATE_PLAN_REPLAYED,
                        "The exact producer sentinel already exists.",
                    )
            verification_digest = str(
                verification.get(
                    "verification_digest",
                    digest_json(verification),
                )
            )
            intent = self.store.claim_gate_plan(
                campaign_id,
                manifest_digest=str(manifest["manifest_digest"]),
                decision=str(manifest["decision"]),
                plan_digest=str(plan["plan_digest"]),
                trusted_run_id=context.run_id,
                recorded_at=operation_time,
                action_type=action_type,
                action_digest=(
                    str(plan["action"].get("action_digest"))
                    if plan["action"].get("action_digest") is not None
                    else None
                ),
                verification_digest=verification_digest,
            )
            intent_claimed = True
            if action_type == POSTGRES_ACTION_TYPE:
                return self._execute_postgres_action(
                    campaign_id,
                    manifest=manifest,
                    plan=plan,
                    context=context,
                    intent=intent,
                    verification=verification,
                    executed_at=operation_time,
                )
            if action_type != "write_public_safe_sentinel" or sentinel_target is None:
                self.store.complete_gate_not_committed(
                    str(intent["attempt_id"]),
                    action_outcome=None,
                    refusal_code=str(RefusalCode.GATE_PLAN_INVALID),
                    observed_at=operation_time,
                )
                raise Refusal(
                    RefusalCode.GATE_PLAN_INVALID,
                    "The issued producer action type is unsupported.",
                )
            try:
                sentinel = with_digest(
                    {
                        "schema_version": "1.0.0",
                        "result": "PRODUCER_SENTINEL_EXECUTED",
                        "campaign_id": campaign_id,
                        "action_id": plan["action"]["action_id"],
                        "producer_plan_digest": plan["plan_digest"],
                        "manifest_digest": manifest["manifest_digest"],
                        "decision": manifest["decision"],
                        "attempt_digest": intent["attempt_digest"],
                        "trusted_run_id": context.run_id,
                        "writer_id": self.store.writer_id,
                        "executed_at": operation_time,
                    },
                    "content_digest",
                )
                self._write_new_sentinel(sentinel_target, sentinel)
                sentinel_digest = digest_file(sentinel_target)
            except OSError as exc:
                self.store.mark_gate_outcome_unknown(
                    str(intent["attempt_id"]),
                    error_type=type(exc).__name__,
                    observed_at=operation_time,
                )
                raise Refusal(
                    RefusalCode.GATE_ACTION_OUTCOME_UNKNOWN,
                    "The producer sentinel outcome is unknown and cannot be retried.",
                ) from exc
            outcome = self.store.complete_gate_attempt(
                str(intent["attempt_id"]),
                sentinel_digest=sentinel_digest,
                executed_at=operation_time,
            )
            receipt = with_digest(
                {
                    "schema_version": "1.0.0",
                    "result": "EXECUTED",
                    "campaign_id": campaign_id,
                    "manifest_digest": manifest["manifest_digest"],
                    "decision": manifest["decision"],
                    "producer_plan_digest": plan["plan_digest"],
                    "attempt_digest": intent["attempt_digest"],
                    "outcome_digest": outcome["outcome_digest"],
                    "trusted_run_id": context.run_id,
                    "writer_id": self.store.writer_id,
                    "verification": verification,
                    "sentinel": {
                        "relative_path": plan["action"]["relative_path"],
                        "digest": sentinel_digest,
                    },
                    "executed_at": operation_time,
                },
                "receipt_digest",
            )
            validate_schema(
                "gate-receipt",
                receipt,
                refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
            )
            write_versioned_artifact(
                self._producer_artifact_root(campaign_id),
                "gate-receipt",
                receipt,
            )
            return {
                "result": "EXECUTED",
                "decision": manifest["decision"],
                "manifest_digest": manifest["manifest_digest"],
                "gate_receipt": receipt,
            }
        except Refusal as exc:
            if not intent_claimed:
                self._record_refusal(
                    campaign_id,
                    manifest=manifest,
                    refusal=exc,
                    plan=plan,
                    context=context,
                    recorded_at=operation_time,
                )
            raise

    def _execute_postgres_action(
        self,
        campaign_id: str,
        *,
        manifest: Mapping[str, Any],
        plan: Mapping[str, Any],
        context: TrustedProducerContext,
        intent: Mapping[str, Any],
        verification: Mapping[str, Any],
        executed_at: str,
    ) -> dict[str, Any]:
        native_action, _target = self._required_postgres_action()
        if self.mutation_client_factory is None:
            self.store.complete_gate_not_committed(
                str(intent["attempt_id"]),
                action_outcome=None,
                refusal_code=str(RefusalCode.RUNTIME_CONFIGURATION_INCOMPLETE),
                observed_at=executed_at,
            )
            raise Refusal(
                RefusalCode.RUNTIME_CONFIGURATION_INCOMPLETE,
                "The separately privileged PostgreSQL mutation client is unavailable.",
            )
        native_plan = dict(plan["action"]["postgres_action_plan"])
        verify_digest(native_plan, "action_digest")
        if native_plan["action_digest"] != plan["action"]["action_digest"]:
            self.store.complete_gate_not_committed(
                str(intent["attempt_id"]),
                action_outcome=None,
                refusal_code=str(RefusalCode.GATE_PLAN_INVALID),
                observed_at=executed_at,
            )
            raise Refusal(
                RefusalCode.GATE_PLAN_INVALID,
                "The PostgreSQL action digest differs from the issued producer plan.",
            )

        # The factory is intentionally invoked only after claim_gate_plan has
        # committed the single-use intent above.
        try:
            mutation_client = self.mutation_client_factory()
        except (OSError, Refusal) as exc:
            pre_execution = native_action.classify_pre_execution_failure(
                native_plan,
                attempt_id=str(intent["attempt_id"]),
                trusted_now=parse_timestamp(executed_at),
            )
            if pre_execution["outcome"] == str(PostgresActionOutcome.NOT_COMMITTED):
                self.store.complete_gate_not_committed(
                    str(intent["attempt_id"]),
                    action_outcome=pre_execution,
                    refusal_code=str(RefusalCode.GATE_ACTION_NOT_COMMITTED),
                    observed_at=executed_at,
                )
                raise Refusal(
                    RefusalCode.GATE_ACTION_NOT_COMMITTED,
                    (
                        "The privileged PostgreSQL client failed before execution; "
                        "a fresh native reread proved no commit."
                    ),
                    {"error_type": type(exc).__name__},
                ) from exc
            self.store.mark_gate_outcome_unknown(
                str(intent["attempt_id"]),
                error_type=type(exc).__name__,
                observed_at=executed_at,
                action_outcome=pre_execution,
            )
            raise Refusal(
                RefusalCode.GATE_ACTION_OUTCOME_UNKNOWN,
                "The pre-execution failure could not be resolved from native state.",
            ) from exc
        try:
            native_outcome = native_action.apply(
                native_plan,
                mutation_client=mutation_client,
                confirmed_action_digest=str(plan["action"]["action_digest"]),
                attempt_id=str(intent["attempt_id"]),
                trusted_now=parse_timestamp(executed_at),
            )
        except Refusal as exc:
            self.store.complete_gate_not_committed(
                str(intent["attempt_id"]),
                action_outcome=None,
                refusal_code=str(exc.code),
                observed_at=executed_at,
            )
            raise

        outcome = str(native_outcome["outcome"])
        if outcome == str(PostgresActionOutcome.NOT_COMMITTED):
            self.store.complete_gate_not_committed(
                str(intent["attempt_id"]),
                action_outcome=native_outcome,
                refusal_code=str(RefusalCode.GATE_ACTION_NOT_COMMITTED),
                observed_at=executed_at,
            )
            raise Refusal(
                RefusalCode.GATE_ACTION_NOT_COMMITTED,
                "Native PostgreSQL state proved that the action did not commit.",
                {"native_attempt_digest": native_outcome["attempt_digest"]},
            )
        if outcome == str(PostgresActionOutcome.OUTCOME_UNKNOWN):
            self.store.mark_gate_outcome_unknown(
                str(intent["attempt_id"]),
                error_type="PostgresActionOutcomeUnknown",
                observed_at=executed_at,
                action_outcome=native_outcome,
            )
            raise Refusal(
                RefusalCode.GATE_ACTION_OUTCOME_UNKNOWN,
                (
                    "The PostgreSQL result is unknown; the consumed plan cannot "
                    "be retried before explicit native outcome resolution."
                ),
                {"native_attempt_digest": native_outcome["attempt_digest"]},
            )
        if outcome != str(PostgresActionOutcome.COMMITTED):
            self.store.mark_gate_outcome_unknown(
                str(intent["attempt_id"]),
                error_type="UnexpectedPostgresActionOutcome",
                observed_at=executed_at,
                action_outcome=native_outcome,
            )
            raise Refusal(
                RefusalCode.GATE_ACTION_OUTCOME_UNKNOWN,
                "The PostgreSQL action returned an unsupported terminal outcome.",
            )
        ledger_outcome = self.store.complete_gate_action_attempt(
            str(intent["attempt_id"]),
            action_outcome=native_outcome,
            executed_at=executed_at,
        )
        receipt = self._postgres_gate_receipt(
            campaign_id,
            manifest_digest=str(manifest["manifest_digest"]),
            plan=plan,
            context=context,
            attempt_digest=str(intent["attempt_digest"]),
            ledger_outcome=ledger_outcome,
            native_outcome=native_outcome,
            verification=verification,
            executed_at=executed_at,
            result="EXECUTED",
        )
        write_versioned_artifact(
            self._producer_artifact_root(campaign_id),
            "gate-receipt",
            receipt,
        )
        return {
            "result": "EXECUTED",
            "decision": manifest["decision"],
            "manifest_digest": manifest["manifest_digest"],
            "gate_receipt": receipt,
        }

    def _postgres_gate_receipt(
        self,
        campaign_id: str,
        *,
        manifest_digest: str,
        plan: Mapping[str, Any],
        context: TrustedProducerContext,
        attempt_digest: str,
        ledger_outcome: Mapping[str, Any],
        native_outcome: Mapping[str, Any],
        verification: Mapping[str, Any],
        executed_at: str,
        result: str,
    ) -> dict[str, Any]:
        receipt = with_digest(
            {
                "schema_version": "2.0.0",
                "result": result,
                "campaign_id": campaign_id,
                "manifest_digest": manifest_digest,
                "decision": plan["manifest"]["decision"],
                "producer_plan_digest": plan["plan_digest"],
                "attempt_digest": attempt_digest,
                "outcome_digest": ledger_outcome["outcome_digest"],
                "trusted_run_id": context.run_id,
                "writer_id": self.store.writer_id,
                "verification": dict(verification),
                "action": {
                    "type": POSTGRES_ACTION_TYPE,
                    "result": native_outcome["outcome"],
                    "action_digest": native_outcome["action_digest"],
                    "native_attempt_digest": native_outcome["attempt_digest"],
                    "before_schema_fingerprint": native_outcome[
                        "before_schema_fingerprint"
                    ],
                    "after_schema_fingerprint": native_outcome[
                        "after_schema_fingerprint"
                    ],
                    "legacy_column_present": native_outcome["legacy_column_present"],
                    "replacement_column_preserved": native_outcome[
                        "replacement_column_preserved"
                    ],
                    "destructive_statements_attempted": native_outcome[
                        "destructive_statements_attempted"
                    ],
                    "destructive_statements_committed": native_outcome[
                        "destructive_statements_committed"
                    ],
                    "recovery": native_outcome["recovery"],
                },
                "executed_at": executed_at,
            },
            "receipt_digest",
        )
        validate_schema(
            "gate-receipt-v2",
            receipt,
            refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
        )
        return receipt

    def _capture_superset_bindings(
        self,
        campaign_id: str,
        *,
        trusted_now: str,
    ) -> list[dict[str, str]]:
        artifacts = self._accepted_superset_artifacts(campaign_id)
        if not artifacts:
            return []
        if len(artifacts) != 1:
            raise Refusal(
                RefusalCode.GATE_PLAN_INVALID,
                "The concrete gate supports one exact Superset consumer.",
                {"consumer_count": len(artifacts)},
            )
        settings, client = self._required_superset_gate()
        value = artifacts[0]
        projection = self.store.projection(campaign_id)
        baseline = projection.evidence_envelope
        if baseline is None:
            raise Refusal(
                RefusalCode.GATE_STATE_DRIFT,
                "The campaign lacks its reconciled Superset evidence source.",
            )
        source_id = f"superset:{value['plan']['native_identity']['dataset_uuid']}"
        baseline_source = _source(baseline, source_id)
        binding = capture_superset_gate_binding(
            settings=settings,
            client=client,
            consumer_id=str(value["plan"]["consumer_id"]),
            datahub_native_identity={"urn": value["plan"]["datahub_urn"]},
            plan=value["plan"],
            receipt=value["receipt"],
            validation=value["validation"],
            expected_evidence_source=baseline_source,
            captured_at=trusted_now,
            maximum_age_seconds=int(
                baseline_source["freshness"]["maximum_age_seconds"]
            ),
            artifact_root=(self._producer_artifact_root(campaign_id) / "superset-gate"),
        )
        return [
            {
                "consumer_id": str(value["plan"]["consumer_id"]),
                "datahub_urn": str(value["plan"]["datahub_urn"]),
                "binding_digest": str(binding["binding_digest"]),
                "plan_digest": str(value["plan"]["plan_digest"]),
                "receipt_digest": str(value["receipt"]["receipt_digest"]),
                "validation_digest": str(value["validation"]["validation_digest"]),
            }
        ]

    def resolve_postgres_outcome(
        self,
        campaign_id: str,
        *,
        context: TrustedProducerContext,
        plan_path: Path | None = None,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        """Resolve one consumed unknown PostgreSQL attempt by native reread only."""

        operation_time = observed_at or utc_now()
        self._require_context_identity(context)
        if not context.trusted:
            raise Refusal(
                RefusalCode.GATE_PROVENANCE_UNTRUSTED,
                "PostgreSQL outcome resolution requires the trusted producer run.",
            )
        plan = self._load_producer_plan(
            plan_path or self._producer_artifact_root(campaign_id) / "plan.json"
        )
        if plan["action"]["type"] != POSTGRES_ACTION_TYPE:
            raise Refusal(
                RefusalCode.GATE_PLAN_INVALID,
                "Only a PostgreSQL producer plan has a native outcome to resolve.",
            )
        self.store.require_issued_gate_plan(campaign_id, plan)
        if plan["trusted_run"] != {
            "id": context.run_id,
            "provider": context.provider,
        }:
            raise Refusal(
                RefusalCode.GATE_PROVENANCE_UNTRUSTED,
                "The producer plan is bound to another trusted run.",
            )
        attempts = [
            entry
            for entry in self.store.gate_attempts(campaign_id)
            if entry["attempt"].get("plan_digest") == plan["plan_digest"]
            and entry["status"] == "OUTCOME_UNKNOWN"
        ]
        if len(attempts) != 1:
            raise Refusal(
                RefusalCode.GATE_ACTION_OUTCOME_UNKNOWN,
                "The producer plan does not have one unresolved native attempt.",
                {"match_count": len(attempts)},
            )
        entry = attempts[0]
        prior_gate_outcome = entry.get("outcome")
        native_attempt = (
            prior_gate_outcome.get("action_outcome")
            if isinstance(prior_gate_outcome, Mapping)
            else None
        )
        if not isinstance(native_attempt, Mapping):
            raise Refusal(
                RefusalCode.GATE_ACTION_OUTCOME_UNKNOWN,
                "The unresolved gate attempt lacks its native action binding.",
            )
        native_action, _target = self._required_postgres_action()
        native_plan = dict(plan["action"]["postgres_action_plan"])
        resolved = native_action.resolve_outcome(native_plan, native_attempt)
        ledger_outcome = self.store.resolve_gate_outcome(
            str(entry["attempt"]["attempt_id"]),
            action_outcome=resolved,
            observed_at=operation_time,
        )
        write_versioned_artifact(
            self._producer_artifact_root(campaign_id),
            "postgres-outcome-resolution",
            resolved,
        )
        if resolved["outcome"] != str(PostgresActionOutcome.COMMITTED):
            return {
                "result": "NOT_COMMITTED",
                "producer_plan_digest": plan["plan_digest"],
                "native_outcome": resolved,
                "ledger_outcome": ledger_outcome,
            }
        verification = load_object(
            self._producer_artifact_root(campaign_id) / "gate-verification.json"
        )
        verify_digest(verification, "verification_digest")
        receipt = self._postgres_gate_receipt(
            campaign_id,
            manifest_digest=str(plan["manifest"]["digest"]),
            plan=plan,
            context=context,
            attempt_digest=str(entry["attempt"]["attempt_digest"]),
            ledger_outcome=ledger_outcome,
            native_outcome=resolved,
            verification=verification,
            executed_at=operation_time,
            result="RECOVERED_COMMITTED",
        )
        write_versioned_artifact(
            self._producer_artifact_root(campaign_id),
            "gate-receipt",
            receipt,
        )
        return {
            "result": "RECOVERED_COMMITTED",
            "decision": plan["manifest"]["decision"],
            "manifest_digest": plan["manifest"]["digest"],
            "gate_receipt": receipt,
        }

    def _verify_ready_state(
        self,
        campaign_id: str,
        *,
        manifest: Mapping[str, Any],
        plan: Mapping[str, Any],
        trusted_now: str,
    ) -> dict[str, Any]:
        projection = self.store.projection(campaign_id)
        self._verify_campaign_inputs(campaign_id, projection.input_digests)
        self._validate_receipts_and_approvals(
            campaign_id,
            trusted_now=trusted_now,
        )
        bindings = self._git_dbt_bindings(campaign_id)
        if bindings["binding"] != plan["git_dbt"]:
            raise Refusal(
                RefusalCode.GATE_STATE_DRIFT,
                "Git/dbt validation or configuration bindings changed.",
            )
        boundary = self._required_boundary()
        adapter = self._required_git_dbt()
        snapshot = boundary.inventory(
            self.store.specification(campaign_id),
            artifact_root=(
                self._producer_artifact_root(campaign_id)
                / "gate-verification"
                / "datahub"
            ),
        )
        baseline_envelope = projection.evidence_envelope
        if baseline_envelope is None:
            raise Refusal(
                RefusalCode.GATE_STATE_DRIFT,
                "The campaign has no reconciliation evidence envelope.",
            )
        baseline_git = _source(
            baseline_envelope,
            f"git:{adapter.settings.repository_id}",
        )
        source_observation = adapter.reconcile_source(
            self.store.specification(campaign_id),
            bindings["plan"],
            bindings["apply"],
            bindings["receipt"],
            datahub_resolution=snapshot["resolution"],
            artifact_root=(
                self._producer_artifact_root(campaign_id)
                / "gate-verification"
                / "git-dbt"
            ),
        )
        current_envelope = merge_repository_reconciliation_evidence(
            snapshot["evidence_envelope"],
            source_observation,
            baseline_source=baseline_git,
        )
        superset_observations: list[dict[str, str]] = []
        if plan["schema_version"] == "2.0.0":
            current_envelope, superset_observations = (
                self._verify_superset_gate_bindings(
                    campaign_id,
                    plan=plan,
                    envelope=current_envelope,
                    trusted_now=trusted_now,
                )
            )
        if scope_signature(current_envelope) != scope_signature(baseline_envelope):
            raise Refusal(
                RefusalCode.GATE_STATE_DRIFT,
                "Gate-time sources no longer have the reconciled declared scope.",
            )
        observed_ids = sorted(str(item["id"]) for item in snapshot["consumers"])
        observed_by_id = {str(item["id"]): item for item in snapshot["consumers"]}
        for superset_binding in plan.get("superset", []):
            current_consumer = observed_by_id.get(str(superset_binding["consumer_id"]))
            if (
                current_consumer is None
                or current_consumer.get("datahub_urn")
                != superset_binding["datahub_urn"]
            ):
                raise Refusal(
                    RefusalCode.GATE_STATE_DRIFT,
                    (
                        "Current DataHub membership does not match the accepted "
                        "Superset native identity."
                    ),
                )
        if observed_ids != sorted(projection.current_consumer_ids):
            raise Refusal(
                RefusalCode.GATE_STATE_DRIFT,
                "Consumer membership changed after reconciliation.",
                {
                    "added_count": len(
                        set(observed_ids) - set(projection.current_consumer_ids)
                    ),
                    "disappeared_count": len(
                        set(projection.current_consumer_ids) - set(observed_ids)
                    ),
                },
            )
        self._require_fresh_complete_envelope(
            current_envelope,
            trusted_now=trusted_now,
        )
        publication = self._verify_publication(
            campaign_id,
            manifest=manifest,
            plan=plan,
            target_urn=str(snapshot["resolution"]["dataset"]["urn"]),
        )
        verification: dict[str, Any] = {
            "datahub_snapshot_digest": str(snapshot["snapshot_digest"]),
            "git_dbt_reconciliation_digest": str(
                source_observation["reconciliation_digest"]
            ),
            "publication_readback_artifact_id": str(
                publication["readback_artifact_id"]
            ),
        }
        if plan["schema_version"] == "1.0.0":
            return {
                "datahub_snapshot_digest": verification["datahub_snapshot_digest"],
                "source_reconciliation_digest": verification[
                    "git_dbt_reconciliation_digest"
                ],
                "publication_readback_artifact_id": verification[
                    "publication_readback_artifact_id"
                ],
            }
        native_action, _target = self._required_postgres_action()
        producer_observation = native_action.verify_plan_observation(
            plan["action"]["postgres_action_plan"],
            trusted_now=parse_timestamp(trusted_now),
        )
        verification.update(
            {
                "superset_observations": superset_observations,
                "producer_schema_observation_digest": producer_observation[
                    "observation_digest"
                ],
            }
        )
        versioned = with_digest(verification, "verification_digest")
        write_versioned_artifact(
            self._producer_artifact_root(campaign_id),
            "gate-verification",
            versioned,
        )
        return versioned

    def _verify_publication(
        self,
        campaign_id: str,
        *,
        manifest: Mapping[str, Any],
        plan: Mapping[str, Any],
        target_urn: str,
    ) -> dict[str, Any]:
        publication = self._require_verified_publication(manifest)
        if (
            publication["content_digest"]
            != plan["manifest"]["publication_content_digest"]
            or publication["published_manifest_digest"]
            != plan["manifest"]["published_manifest_digest"]
        ):
            raise Refusal(
                RefusalCode.GATE_PUBLICATION_UNVERIFIED,
                "The DataHub publication binding changed after plan preparation.",
            )
        source_manifest = publication_source_manifest(
            self.store,
            campaign_id,
            str(publication["content_digest"]),
        )
        if (
            source_manifest["decision"] != manifest["decision"]
            or source_manifest["specification_digest"]
            != manifest["specification_digest"]
            or source_manifest["receipt_digests"] != manifest["receipt_digests"]
            or source_manifest["evidence_envelope"]["envelope_digest"]
            != manifest["evidence_envelope"]["envelope_digest"]
        ):
            raise Refusal(
                RefusalCode.GATE_PUBLICATION_UNVERIFIED,
                "The published report and current canonical decision disagree.",
            )
        verification = self._required_boundary().verify_summary(
            campaign_id=campaign_id,
            urn=str(publication["urn"]),
            expected_content=render_campaign_summary(source_manifest),
            target_urn=target_urn,
            expected_lifecycle_digest=str(publication["lifecycle_digest_before"]),
            artifact_root=(
                self._producer_artifact_root(campaign_id)
                / "gate-verification"
                / "publication"
            ),
        )
        if verification["content_digest"] != publication["content_digest"]:
            raise Refusal(
                RefusalCode.GATE_PUBLICATION_UNVERIFIED,
                "The live publication content digest did not match.",
            )
        return verification

    def _verify_plan_context(
        self,
        campaign_id: str,
        *,
        manifest: Mapping[str, Any],
        plan: Mapping[str, Any],
        context: TrustedProducerContext,
        trusted_now: str,
    ) -> None:
        self._require_context_identity(context)
        if not context.trusted:
            raise Refusal(
                RefusalCode.GATE_PROVENANCE_UNTRUSTED,
                "The producer invocation did not present a trusted run context.",
            )
        self._validate_plan_window(
            prepared_at=str(plan["prepared_at"]),
            expires_at=str(plan["expires_at"]),
            trusted_now=trusted_now,
        )
        if (
            plan["campaign_id"] != campaign_id
            or plan["writer_id"] != self.store.writer_id
            or plan["trusted_run"]
            != {"id": context.run_id, "provider": context.provider}
        ):
            raise Refusal(
                RefusalCode.GATE_PROVENANCE_UNTRUSTED,
                "The producer plan is bound to another campaign, writer, or run.",
            )
        projection = self.store.projection(campaign_id)
        publication = self._require_verified_publication(manifest)
        expected_manifest = {
            "digest": manifest["manifest_digest"],
            "decision": manifest["decision"],
            "specification_digest": manifest["specification_digest"],
            "evidence_envelope_digest": manifest["evidence_envelope"][
                "envelope_digest"
            ],
            "reconciliation_digest": self._reconciliation_digest(campaign_id),
            "publication_content_digest": publication["content_digest"],
            "published_manifest_digest": publication["published_manifest_digest"],
            "input_digests": dict(projection.input_digests),
            "receipt_digests": list(manifest["receipt_digests"]),
        }
        if plan["manifest"] != expected_manifest:
            raise Refusal(
                RefusalCode.GATE_STATE_DRIFT,
                "The current canonical manifest no longer matches the producer plan.",
            )
        action_type = plan["action"]["type"]
        if action_type == "write_public_safe_sentinel":
            if plan["action"]["sentinel_root_identity"] != digest_json(
                str(self.sentinel_root)
            ):
                raise Refusal(
                    RefusalCode.GATE_PLAN_INVALID,
                    "The producer plan is bound to another sentinel root.",
                )
            return
        if action_type != POSTGRES_ACTION_TYPE:
            raise Refusal(
                RefusalCode.GATE_PLAN_INVALID,
                "The producer plan action type is unsupported.",
            )
        native_action, target = self._required_postgres_action()
        native_plan = plan["action"]["postgres_action_plan"]
        verify_digest(native_plan, "action_digest")
        if (
            plan["action"]["action_digest"] != native_plan["action_digest"]
            or target_from_mapping(native_plan["target"]) != target
            or native_plan["allowlist_configuration_digest"]
            != native_action.settings.allowlist_digest()
        ):
            raise Refusal(
                RefusalCode.GATE_PLAN_INVALID,
                "The PostgreSQL producer action no longer matches its gate binding.",
            )

    def _git_dbt_bindings(self, campaign_id: str) -> dict[str, Any]:
        adapter = self._required_git_dbt()
        root = self.artifact_directory / campaign_id / "git-dbt"
        preflight = load_object(root / "preflight.json")
        migration_plan = load_object(root / "plan.json")
        apply_record = load_object(root / "apply.json")
        validation = load_object(root / "native-validation" / "validation.json")
        receipt = load_object(root / "receipt.json")
        verify_digest(preflight, "preflight_digest")
        verify_digest(migration_plan, "plan_digest")
        verify_digest(apply_record, "apply_digest")
        verify_digest(validation, "validation_digest")
        verify_digest(receipt, "receipt_digest")
        validate_schema(
            "git-dbt-plan",
            migration_plan,
            refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
        )
        if (
            apply_record["plan_digest"] != migration_plan["plan_digest"]
            or receipt["plan"]["digest"] != migration_plan["plan_digest"]
            or receipt["apply"]["native_change_ids"]
            != apply_record["native_change_ids"]
            or receipt["apply"]["actual_targets"] != apply_record["actual_targets"]
        ):
            raise Refusal(
                RefusalCode.GATE_STATE_DRIFT,
                "The Git/dbt plan, apply record, and receipt do not agree.",
            )
        current_versions = adapter.tool_versions()
        if current_versions != preflight["tool_versions"]:
            raise Refusal(
                RefusalCode.GATE_STATE_DRIFT,
                "The native validator toolchain changed after validation.",
            )
        receipt_validation = receipt["validation"]
        if (
            validation["result"] != receipt_validation["result"]
            or validation["validator"] != receipt_validation["validator"]
            or validation["validator_version"]
            != receipt_validation["validator_version"]
            or sorted(validation["artifact_ids"])
            != sorted(receipt_validation["artifact_ids"])
        ):
            raise Refusal(
                RefusalCode.GATE_STATE_DRIFT,
                "The native validation artifact and accepted receipt disagree.",
            )
        projection = self.store.projection(campaign_id)
        consumer = projection.consumers.get(str(migration_plan["consumer_id"]))
        if (
            consumer is None
            or consumer.get("receipt") != receipt
            or consumer.get("receipt_digest") != receipt["receipt_digest"]
        ):
            raise Refusal(
                RefusalCode.GATE_STATE_DRIFT,
                "The accepted campaign receipt differs from the native artifact.",
            )
        required_artifacts = sorted(
            {
                *preflight["artifact_ids"],
                apply_record["diff_artifact_id"],
                *validation["artifact_ids"],
            }
        )
        self._require_artifact_digests(root, required_artifacts)
        validator_binding = {
            "tool_versions": current_versions,
            "validators": list(migration_plan["validators"]),
            "validation": {
                "result": validation["result"],
                "validator": validation["validator"],
                "validator_version": validation["validator_version"],
                "adapter_version": validation["adapter_version"],
            },
        }
        return {
            "binding": {
                "settings_digest": digest_json(adapter.settings.safe_summary()),
                "preflight_digest": preflight["preflight_digest"],
                "migration_plan_digest": migration_plan["plan_digest"],
                "apply_digest": apply_record["apply_digest"],
                "validation_digest": validation["validation_digest"],
                "receipt_digest": receipt["receipt_digest"],
                "validator_binding_digest": digest_json(validator_binding),
                "artifact_set_digest": digest_json(required_artifacts),
            },
            "plan": migration_plan,
            "apply": apply_record,
            "validation": validation,
            "receipt": receipt,
        }

    def _verify_campaign_inputs(
        self,
        campaign_id: str,
        recorded: Mapping[str, str],
    ) -> None:
        specification = self.store.specification(campaign_id)
        source_specification = {
            key: value
            for key, value in specification.items()
            if key != "specification_digest"
        }
        validate_schema(
            "retirement-spec",
            source_specification,
            refusal_code=RefusalCode.GATE_STATE_DRIFT,
        )
        verify_digest(specification, "specification_digest")
        current = {
            "policy": digest_json(default_policy()),
            "validator_configuration": digest_json(specification["validation"]),
            "authorization": digest_json(specification["authorization"]),
        }
        require_bound_inputs(recorded=recorded, current=current)

    def _validate_receipts_and_approvals(
        self,
        campaign_id: str,
        *,
        trusted_now: str,
    ) -> None:
        projection = self.store.projection(campaign_id)
        specification = self.store.specification(campaign_id)
        now = parse_timestamp(trusted_now)
        required_receipt_types = set(
            specification["validation"]["required_receipt_types"]
        )
        for consumer_id, consumer in projection.consumers.items():
            if (
                ConsumerDisposition(str(consumer["disposition"]))
                != ConsumerDisposition.VALIDATED
            ):
                continue
            receipt = consumer.get("receipt")
            if not isinstance(receipt, dict):
                raise Refusal(
                    RefusalCode.GATE_STATE_DRIFT,
                    "A validated consumer no longer has its accepted receipt.",
                )
            receipt_type = (
                "dbt"
                if receipt["adapter"]["name"] == "git-dbt"
                else receipt["adapter"]["name"]
            )
            if receipt_type not in required_receipt_types:
                raise Refusal(
                    RefusalCode.POLICY_INPUT_DRIFT,
                    "The accepted validator type is no longer configured.",
                )
            validate_consumer_receipt(
                receipt,
                campaign_id=campaign_id,
                consumer_id=consumer_id,
                plan_digest=str(consumer["plan_digest"]),
                source_version=str(consumer["source_version"]),
                approved_targets=list(consumer["approved_targets"]),
                require_live=bool(projection.policy["requires_live_evidence"]),
                trusted_now=now,
            )
            validate_approval(
                projection.approvals.get(str(consumer["plan_digest"])),
                campaign_id=campaign_id,
                plan_digest=str(consumer["plan_digest"]),
                source_version=str(consumer["source_version"]),
                targets=list(consumer["approved_targets"]),
                required_scope=["apply"],
                authorization_digest=projection.input_digests["authorization"],
                trusted_now=now,
            )

    def _reconciliation_digest(self, campaign_id: str) -> str:
        projection = self.store.projection(campaign_id)
        if not projection.reconciliations:
            raise Refusal(
                RefusalCode.GATE_STATE_DRIFT,
                "The campaign has no recorded reconciliation comparison.",
            )
        digest = projection.reconciliations[-1].get("comparison_digest")
        comparison = load_object(
            self.artifact_directory / campaign_id / "reconciliation" / "comparison.json"
        )
        verify_digest(comparison, "comparison_digest")
        if digest != comparison["comparison_digest"]:
            raise Refusal(
                RefusalCode.GATE_STATE_DRIFT,
                "The durable reconciliation and comparison artifact disagree.",
            )
        return str(digest)

    def _producer_source(self) -> dict[str, Any]:
        root = self.producer_repository_root
        try:
            relative_marker = self.producer_source_marker.relative_to(root)
        except ValueError as exc:
            raise Refusal(
                RefusalCode.GATE_SOURCE_DRIFT,
                "The producer marker is outside its repository.",
            ) from exc
        marker_path = checked_target_path(
            root,
            relative_marker.as_posix(),
            allowed_paths=[relative_marker.as_posix()],
        )
        branch = self._git(root, "branch", "--show-current") or "DETACHED"
        source = {
            "repository_identity": digest_json(str(root)),
            "remote_identity": digest_json(
                self._git(root, "config", "--get", "remote.origin.url", check=False)
                or "no-origin"
            ),
            "branch": branch,
            "version": self._git(root, "rev-parse", "HEAD"),
            "working_tree_clean": not bool(
                self._git(
                    root,
                    "status",
                    "--porcelain=v1",
                    "--untracked-files=all",
                )
            ),
            "marker_path": relative_marker.as_posix(),
            "marker_digest": digest_file(marker_path),
        }
        if not source["working_tree_clean"]:
            raise Refusal(
                RefusalCode.GATE_SOURCE_DRIFT,
                "The producer repository must be clean.",
            )
        return source

    def _git(
        self,
        root: Path,
        *arguments: str,
        check: bool = True,
    ) -> str:
        adapter = self._required_git_dbt()
        try:
            result = subprocess.run(
                [
                    str(adapter.settings.git_executable),
                    "-C",
                    str(root),
                    *arguments,
                ],
                check=check,
                capture_output=True,
                text=True,
                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8"},
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise Refusal(
                RefusalCode.GATE_SOURCE_DRIFT,
                "The producer Git source could not be verified.",
            ) from exc
        return result.stdout.strip() if result.returncode == 0 else ""

    def _require_artifact_digests(
        self,
        root: Path,
        expected: list[str],
    ) -> None:
        remaining = set(expected)
        try:
            paths = sorted(root.rglob("*"))
        except OSError as exc:
            raise Refusal(
                RefusalCode.GATE_PLAN_MISSING,
                "Required native evidence artifacts are unavailable.",
            ) from exc
        try:
            for path in paths:
                if not remaining:
                    break
                if path.is_symlink():
                    raise Refusal(
                        RefusalCode.GATE_PLAN_INVALID,
                        "Native evidence cannot be supplied through a symlink.",
                    )
                if not path.is_file():
                    continue
                observed = digest_file(path)
                remaining.discard(observed)
        except OSError as exc:
            raise Refusal(
                RefusalCode.GATE_PLAN_MISSING,
                "Required native evidence artifacts could not be verified.",
            ) from exc
        if remaining:
            raise Refusal(
                RefusalCode.GATE_PLAN_MISSING,
                "Required native evidence artifacts are missing or changed.",
                {"missing_count": len(remaining)},
            )

    def _require_fresh_complete_envelope(
        self,
        envelope: Mapping[str, Any],
        *,
        trusted_now: str,
    ) -> None:
        verify_digest(dict(envelope), "envelope_digest")
        now = parse_timestamp(trusted_now)
        for source in envelope["sources"]:
            if not source["required"]:
                continue
            if source["status"] != EvidenceStatus.COMPLETE:
                raise Refusal(
                    RefusalCode.EVIDENCE_REQUIRED_SOURCE_INCOMPLETE,
                    "A required gate-time source is not complete.",
                    {"source_id": source["id"], "status": source["status"]},
                )
            freshness = source["freshness"]
            validate_trusted_clock(
                now=now,
                observed_at=parse_timestamp(str(freshness["observed_at"])),
            )
            validate_trusted_clock(
                now=now,
                observed_at=parse_timestamp(str(freshness["source_updated_at"])),
            )
            age = timestamp_age_seconds(
                str(freshness["source_updated_at"]),
                trusted_now,
            )
            if age > int(freshness["maximum_age_seconds"]):
                raise Refusal(
                    RefusalCode.EVIDENCE_REQUIRED_SOURCE_INCOMPLETE,
                    "A required gate-time source is stale.",
                    {"source_id": source["id"]},
                )

    def _accepted_superset_artifacts(
        self,
        campaign_id: str,
    ) -> list[dict[str, Any]]:
        root = self.artifact_directory / campaign_id / "superset"
        plan_path = root / "plan.json"
        if not plan_path.exists():
            return []
        plan = load_object(plan_path)
        receipt = load_object(root / "receipt.json")
        validation = load_object(root / "native-validation" / "validation.json")
        verify_digest(plan, "plan_digest")
        verify_digest(receipt, "receipt_digest")
        verify_digest(validation, "validation_digest")
        if plan.get("campaign_id") != campaign_id:
            raise Refusal(
                RefusalCode.GATE_STATE_DRIFT,
                "The accepted Superset plan belongs to another campaign.",
            )
        consumer = self.store.projection(campaign_id).consumers.get(
            str(plan.get("consumer_id"))
        )
        if (
            consumer is None
            or ConsumerDisposition(str(consumer["disposition"]))
            != ConsumerDisposition.VALIDATED
            or consumer.get("receipt_digest") != receipt.get("receipt_digest")
            or consumer.get("receipt") != receipt
        ):
            raise Refusal(
                RefusalCode.GATE_STATE_DRIFT,
                "The Superset native artifacts are not the accepted campaign receipt.",
            )
        return [{"plan": plan, "receipt": receipt, "validation": validation}]

    def _verify_superset_gate_bindings(
        self,
        campaign_id: str,
        *,
        plan: Mapping[str, Any],
        envelope: Mapping[str, Any],
        trusted_now: str,
    ) -> tuple[dict[str, Any], list[dict[str, str]]]:
        artifacts = self._accepted_superset_artifacts(campaign_id)
        planned = list(plan.get("superset", []))
        if len(artifacts) != len(planned):
            raise Refusal(
                RefusalCode.GATE_STATE_DRIFT,
                "The accepted Superset consumer set changed after plan preparation.",
            )
        if not planned:
            return dict(envelope), []
        settings, client = self._required_superset_gate()
        verifier = SupersetGateVerifier(settings=settings, client=client)
        sources = [dict(source) for source in envelope["sources"]]
        observations: list[dict[str, str]] = []
        for index, accepted in enumerate(artifacts):
            expected = planned[index]
            binding_path = (
                self._producer_artifact_root(campaign_id)
                / "superset-gate"
                / "gate-binding.json"
            )
            binding = load_object(binding_path)
            verify_digest(binding, "binding_digest")
            if (
                binding["binding_digest"] != expected["binding_digest"]
                or accepted["plan"]["plan_digest"] != expected["plan_digest"]
                or accepted["receipt"]["receipt_digest"] != expected["receipt_digest"]
                or accepted["validation"]["validation_digest"]
                != expected["validation_digest"]
                or accepted["plan"]["consumer_id"] != expected["consumer_id"]
                or accepted["plan"]["datahub_urn"] != expected["datahub_urn"]
            ):
                raise Refusal(
                    RefusalCode.GATE_STATE_DRIFT,
                    "The Superset gate binding differs from the issued plan.",
                )
            observation = verifier.verify(
                binding,
                trusted_now=parse_timestamp(trusted_now),
                artifact_root=(
                    self._producer_artifact_root(campaign_id) / "superset-gate"
                ),
            )
            source_id = str(observation["source_id"])
            sources = [source for source in sources if source["id"] != source_id]
            sources.append(dict(observation["evidence_source"]))
            observations.append(
                {
                    "consumer_id": str(expected["consumer_id"]),
                    "observation_digest": str(observation["observation_digest"]),
                }
            )
        merged = with_digest(
            {
                "schema_version": "1.0.0",
                "captured_at": trusted_now,
                "mode": envelope["mode"],
                "sources": sorted(sources, key=lambda source: str(source["id"])),
            },
            "envelope_digest",
        )
        validate_schema(
            "evidence-envelope",
            merged,
            refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
        )
        return merged, sorted(observations, key=lambda value: value["consumer_id"])

    def _required_superset_gate(
        self,
    ) -> tuple[SupersetSettings, SupersetGateClient]:
        if self.superset_settings is None or self.superset_client is None:
            raise Refusal(
                RefusalCode.RUNTIME_CONFIGURATION_INCOMPLETE,
                "The read-only Superset gate verifier is unavailable.",
            )
        if self.superset_settings.allow_apply:
            raise Refusal(
                RefusalCode.AUTH_APPLY_DISABLED,
                "The gate requires a Superset principal without mutation authority.",
            )
        return self.superset_settings, self.superset_client

    def _required_postgres_action(
        self,
    ) -> tuple[PostgresProducerAction, PostgresTarget]:
        if self.postgres_action is None or self.postgres_target is None:
            raise Refusal(
                RefusalCode.RUNTIME_CONFIGURATION_INCOMPLETE,
                "The bounded PostgreSQL producer action is unavailable.",
            )
        return self.postgres_action, self.postgres_target

    @staticmethod
    def _validate_producer_plan(plan: Mapping[str, Any]) -> None:
        schema_version = plan.get("schema_version")
        schema_name = (
            "producer-plan-v2" if schema_version == "2.0.0" else "producer-plan"
        )
        validate_schema(
            schema_name,
            plan,
            refusal_code=RefusalCode.GATE_PLAN_INVALID,
        )
        verify_digest(dict(plan), "plan_digest")

    def _load_producer_plan(self, path: Path) -> dict[str, Any]:
        if not path.is_file() or path.is_symlink():
            raise Refusal(
                RefusalCode.GATE_PLAN_MISSING,
                "The exact producer plan is unavailable.",
            )
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise Refusal(
                RefusalCode.GATE_PLAN_INVALID,
                "The producer plan could not be parsed.",
            ) from exc
        if not isinstance(value, dict):
            raise Refusal(
                RefusalCode.GATE_PLAN_INVALID,
                "The producer plan is not an object.",
            )
        self._validate_producer_plan(value)
        return value

    def _sentinel_target(self, plan: Mapping[str, Any]) -> Path:
        relative = PurePosixPath(str(plan["action"]["relative_path"]))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise Refusal(
                RefusalCode.GATE_PLAN_INVALID,
                "The sentinel target is not a safe relative path.",
            )
        self._prepare_sentinel_root()
        target = self.sentinel_root.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.parent.resolve(strict=True).relative_to(
                self.sentinel_root.resolve(strict=True)
            )
        except (OSError, ValueError) as exc:
            raise Refusal(
                RefusalCode.GATE_PLAN_INVALID,
                "The sentinel target escaped its configured root.",
            ) from exc
        if any(
            part.is_symlink()
            for part in [self.sentinel_root, *target.parents]
            if part == self.sentinel_root or self.sentinel_root in part.parents
        ):
            raise Refusal(
                RefusalCode.GATE_PLAN_INVALID,
                "The sentinel target cannot traverse a symlink.",
            )
        return target

    def _prepare_sentinel_root(self) -> None:
        try:
            self.sentinel_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise Refusal(
                RefusalCode.GATE_PLAN_INVALID,
                "The sentinel root could not be prepared.",
            ) from exc
        if self.sentinel_root.is_symlink() or not self.sentinel_root.is_dir():
            raise Refusal(
                RefusalCode.GATE_PLAN_INVALID,
                "The sentinel root must be a real directory.",
            )

    @staticmethod
    def _write_new_sentinel(path: Path, value: Mapping[str, Any]) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _record_refusal(
        self,
        campaign_id: str,
        *,
        manifest: Mapping[str, Any],
        refusal: Refusal,
        plan: Mapping[str, Any] | None,
        context: TrustedProducerContext,
        recorded_at: str,
    ) -> None:
        try:
            self.store.record_gate_refusal(
                campaign_id,
                manifest_digest=str(manifest["manifest_digest"]),
                decision=str(manifest["decision"]),
                refusal_code=str(refusal.code),
                recorded_at=recorded_at,
                plan_digest=(str(plan["plan_digest"]) if plan is not None else None),
                trusted_run_id=context.run_id or None,
            )
        except Refusal as ledger_error:
            raise Refusal(
                RefusalCode.GATE_ACTION_OUTCOME_UNKNOWN,
                "The gate refusal could not be durably recorded.",
            ) from ledger_error

    @staticmethod
    def _require_context_identity(context: TrustedProducerContext) -> None:
        if (
            SAFE_RUN_ID.fullmatch(context.run_id) is None
            or SAFE_RUN_ID.fullmatch(context.provider) is None
        ):
            raise Refusal(
                RefusalCode.GATE_PROVENANCE_UNTRUSTED,
                "The producer run identity or trust provider is absent or unsafe.",
            )

    @staticmethod
    def _validate_plan_window(
        *,
        prepared_at: str,
        expires_at: str,
        trusted_now: str,
    ) -> None:
        prepared = parse_timestamp(prepared_at)
        expires = parse_timestamp(expires_at)
        now = parse_timestamp(trusted_now)
        if expires - prepared > MAXIMUM_PLAN_LIFETIME:
            raise Refusal(
                RefusalCode.GATE_PLAN_INVALID,
                "A producer plan cannot remain valid for more than 15 minutes.",
            )
        validate_trusted_clock(
            now=now,
            observed_at=prepared,
            expires_at=expires,
            expiration_code=RefusalCode.GATE_PLAN_EXPIRED,
        )

    @staticmethod
    def _require_ready_manifest(manifest: Mapping[str, Any]) -> None:
        if (
            manifest["campaign"]["state"] != CampaignState.READY
            or manifest["decision"] != Decision.READY_TO_RETIRE
        ):
            raise Refusal(
                RefusalCode.GATE_DECISION_NOT_READY,
                "The canonical campaign decision does not permit retirement.",
                {
                    "state": manifest["campaign"]["state"],
                    "decision": manifest["decision"],
                },
            )

    @staticmethod
    def _require_verified_publication(
        manifest: Mapping[str, Any],
    ) -> dict[str, Any]:
        publication = manifest.get("publication")
        if (
            not isinstance(publication, dict)
            or publication.get("readback_verified") is not True
        ):
            raise Refusal(
                RefusalCode.GATE_PUBLICATION_UNVERIFIED,
                "The stable DataHub campaign summary is not read-back verified.",
            )
        return publication

    def _required_boundary(self) -> DataHubBoundary:
        if self.boundary is None:
            raise Refusal(
                RefusalCode.GATE_PUBLICATION_UNVERIFIED,
                "The live DataHub gate boundary is unavailable.",
            )
        return self.boundary

    def _required_git_dbt(self) -> GitDbtAdapter:
        if self.git_dbt is None:
            raise Refusal(
                RefusalCode.GATE_STATE_DRIFT,
                "The native Git/dbt gate boundary is unavailable.",
            )
        return self.git_dbt

    def _producer_artifact_root(self, campaign_id: str) -> Path:
        return self.artifact_directory / campaign_id / "producer"


def _source(envelope: Mapping[str, Any], source_id: str) -> dict[str, Any]:
    matches = [
        dict(source) for source in envelope["sources"] if source["id"] == source_id
    ]
    if len(matches) != 1:
        raise Refusal(
            RefusalCode.GATE_STATE_DRIFT,
            "The reconciled envelope lacks one exact native source.",
            {"source_id": source_id, "match_count": len(matches)},
        )
    return matches[0]
