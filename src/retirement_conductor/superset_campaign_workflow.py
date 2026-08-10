"""Bind the concrete Superset executor to canonical campaign state."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import verify_digest, with_digest
from retirement_conductor.clock import parse_timestamp
from retirement_conductor.datahub import utc_now
from retirement_conductor.errors import Refusal
from retirement_conductor.git_dbt import load_object, write_versioned_artifact
from retirement_conductor.schemas import validate_schema
from retirement_conductor.store import CampaignStore
from retirement_conductor.superset import SupersetAdapter
from retirement_conductor.superset_workflow import SupersetWorkflow
from retirement_conductor.vocabulary import (
    CampaignState,
    ConsumerDisposition,
    RefusalCode,
)


class SupersetCampaignWorkflow:
    """Close one exact Superset consumer through the shared campaign protocol."""

    def __init__(
        self,
        *,
        store: CampaignStore,
        adapter: SupersetAdapter,
        artifact_directory: Path,
    ) -> None:
        self.store = store
        self.adapter = adapter
        self.artifact_directory = artifact_directory
        self.native = SupersetWorkflow(adapter, artifact_directory)

    def plan(
        self,
        campaign_id: str,
        *,
        consumer_id: str,
        datahub_entities: Sequence[Mapping[str, Any]],
        dataset_id: int,
        chart_id: int,
        legacy_field: str,
        replacement_field: str,
        allow_semantic_change: bool = False,
    ) -> dict[str, Any]:
        projection = self.store.projection(campaign_id)
        if projection.state not in {
            CampaignState.INVENTORIED,
            CampaignState.BLOCKED,
        }:
            raise Refusal(
                RefusalCode.POLICY_ILLEGAL_CAMPAIGN_TRANSITION,
                "Superset planning requires a frozen campaign inventory.",
                {"state": projection.state},
            )
        if projection.evidence_envelope is None:
            raise Refusal(
                RefusalCode.EVIDENCE_REQUIRED_SOURCE_INCOMPLETE,
                "Superset planning requires a campaign evidence envelope.",
            )
        root = self._root(campaign_id)
        preflight = self.adapter.preflight(
            datahub_entities=datahub_entities,
            dataset_id=dataset_id,
            chart_id=chart_id,
            legacy_field=legacy_field,
            replacement_field=replacement_field,
            artifact_root=root / "preflight",
        )
        plan = self.adapter.plan(
            preflight,
            campaign_id=campaign_id,
            consumer_id=consumer_id,
            allow_semantic_change=allow_semantic_change,
            artifact_root=root,
        )
        consumer = projection.consumers.get(consumer_id)
        if consumer is None:
            raise Refusal(
                RefusalCode.IDENTITY_NOT_FOUND,
                "The exact Superset consumer is absent from campaign inventory.",
                {"consumer_id": consumer_id},
            )
        envelope = merge_superset_evidence(projection.evidence_envelope, preflight)
        self.store.extend_inventory(
            campaign_id,
            evidence_envelope=envelope,
            consumers=[
                {
                    "id": consumer_id,
                    "disposition": str(consumer["disposition"]),
                    "receipt_digest": consumer.get("receipt_digest"),
                }
            ],
            snapshot_digest=str(preflight["preflight_digest"]),
            occurred_at=str(preflight["captured_at"]),
            idempotency_key=(
                f"superset-evidence-{str(preflight['preflight_digest'])[-16:]}"
            ),
        )
        current = ConsumerDisposition(
            str(
                self.store.projection(campaign_id).consumers[consumer_id]["disposition"]
            )
        )
        if current in {
            ConsumerDisposition.DISCOVERED,
            ConsumerDisposition.OPAQUE,
            ConsumerDisposition.UNRESOLVED,
        }:
            self.store.change_consumer_disposition(
                campaign_id,
                consumer_id,
                ConsumerDisposition.IDENTIFIED,
                occurred_at=str(preflight["captured_at"]),
                idempotency_key=(
                    f"superset-identify-{str(preflight['preflight_digest'])[-16:]}"
                ),
            )
            current = ConsumerDisposition.IDENTIFIED
        if current not in {
            ConsumerDisposition.IDENTIFIED,
            ConsumerDisposition.STALE,
            ConsumerDisposition.FAILED,
        }:
            raise Refusal(
                RefusalCode.POLICY_ILLEGAL_CONSUMER_TRANSITION,
                "The Superset consumer is not eligible for a new plan.",
                {"disposition": current},
            )
        manifest = self.store.change_consumer_disposition(
            campaign_id,
            consumer_id,
            ConsumerDisposition.CHANGE_PROPOSED,
            occurred_at=str(preflight["captured_at"]),
            idempotency_key=f"superset-plan-{str(plan['plan_digest'])[-16:]}",
            plan_digest=str(plan["plan_digest"]),
            source_version=str(plan["source_version"]),
            approved_targets=[str(item) for item in plan["proposed_targets"]],
        )
        return {
            "result": "PLANNED",
            "preflight": preflight,
            "plan": plan,
            "manifest": manifest,
        }

    def authorize(
        self,
        campaign_id: str,
        *,
        principal: str,
        authorized_at: str,
        expires_at: str,
    ) -> dict[str, Any]:
        plan = self._plan(campaign_id)
        projection = self.store.projection(campaign_id)
        self._require_current_plan(projection.consumers, plan)
        approval = with_digest(
            {
                "schema_version": "1.0.0",
                "approval_id": (
                    f"superset-{campaign_id}-{str(plan['plan_digest'])[-12:]}"
                ),
                "campaign_id": campaign_id,
                "plan_digest": plan["plan_digest"],
                "source_version": plan["source_version"],
                "targets": list(plan["proposed_targets"]),
                "principal": principal,
                "scope": ["apply", "compensate"],
                "authorization_digest": projection.input_digests["authorization"],
                "authorized_at": authorized_at,
                "expires_at": expires_at,
            },
            "approval_digest",
        )
        manifest = self.store.record_approval(
            campaign_id,
            approval,
            plan_digest=str(plan["plan_digest"]),
            source_version=str(plan["source_version"]),
            targets=[str(item) for item in plan["proposed_targets"]],
            required_scope=["apply", "compensate"],
            trusted_now=parse_timestamp(authorized_at),
            occurred_at=authorized_at,
            idempotency_key=(
                f"superset-approval-{str(approval['approval_digest'])[-16:]}"
            ),
        )
        write_versioned_artifact(self._root(campaign_id), "approval", approval)
        return {"result": "AUTHORIZED", "approval": approval, "manifest": manifest}

    def apply(
        self,
        campaign_id: str,
        *,
        confirmed_plan_digest: str,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        operation_time = occurred_at or utc_now()
        plan = self._plan(campaign_id)
        projection = self.store.projection(campaign_id)
        consumer = self._require_current_plan(projection.consumers, plan)
        disposition = ConsumerDisposition(str(consumer["disposition"]))
        if disposition != ConsumerDisposition.CHANGE_PROPOSED:
            raise Refusal(
                RefusalCode.POLICY_ILLEGAL_CONSUMER_TRANSITION,
                "The Superset consumer is not awaiting apply.",
                {"disposition": disposition},
            )
        approval = projection.approvals.get(str(plan["plan_digest"]))
        self.store.begin_migration_with_claim(
            campaign_id,
            plan["native_identity"],
            plan_digest=str(plan["plan_digest"]),
            source_version=str(plan["source_version"]),
            targets=[str(item) for item in plan["proposed_targets"]],
            required_scope=["apply"],
            trusted_now=parse_timestamp(operation_time),
            occurred_at=operation_time,
        )
        apply_record = self.native.apply(
            plan,
            approval=approval,
            authorization_digest=projection.input_digests["authorization"],
            confirmed_plan_digest=confirmed_plan_digest,
            trusted_now=parse_timestamp(operation_time),
        )
        manifest = self.store.change_consumer_disposition(
            campaign_id,
            str(plan["consumer_id"]),
            ConsumerDisposition.APPLIED,
            occurred_at=operation_time,
            idempotency_key=(
                f"superset-applied-{str(apply_record['apply_digest'])[-16:]}"
            ),
        )
        return {"result": "APPLIED", "apply": apply_record, "manifest": manifest}

    def validate(
        self,
        campaign_id: str,
        *,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        plan = self._plan(campaign_id)
        projection = self.store.projection(campaign_id)
        consumer = self._require_current_plan(projection.consumers, plan)
        if (
            ConsumerDisposition(str(consumer["disposition"]))
            != ConsumerDisposition.APPLIED
        ):
            raise Refusal(
                RefusalCode.POLICY_ILLEGAL_CONSUMER_TRANSITION,
                "Only an applied Superset consumer can enter native validation.",
            )
        apply_record = load_object(self._root(campaign_id) / "apply.json")
        accepted = self.native.validate_and_emit_receipt(
            plan,
            apply_record,
            expires_at=expires_at,
        )
        receipt = accepted["receipt"]
        manifest = self.store.accept_receipt(
            campaign_id,
            str(plan["consumer_id"]),
            receipt,
            trusted_now=parse_timestamp(str(receipt["captured_at"])),
            occurred_at=str(receipt["captured_at"]),
            idempotency_key=(
                f"superset-receipt-{str(receipt['receipt_digest'])[-16:]}"
            ),
        )
        return {**accepted, "manifest": manifest}

    def compensate(
        self,
        campaign_id: str,
        *,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        """Restore the exact before state and make its accepted receipt stale."""

        operation_time = occurred_at or utc_now()
        plan = self._plan(campaign_id)
        projection = self.store.projection(campaign_id)
        consumer = self._require_current_plan(projection.consumers, plan)
        if (
            ConsumerDisposition(str(consumer["disposition"]))
            != ConsumerDisposition.VALIDATED
        ):
            raise Refusal(
                RefusalCode.POLICY_ILLEGAL_CONSUMER_TRANSITION,
                "Only a validated Superset consumer can be compensated.",
            )
        apply_record = load_object(self._root(campaign_id) / "apply.json")
        compensation = self.native.compensate(
            plan,
            apply_record,
            approval=projection.approvals.get(str(plan["plan_digest"])),
            authorization_digest=projection.input_digests["authorization"],
            trusted_now=parse_timestamp(operation_time),
        )
        manifest = self.store.change_consumer_disposition(
            campaign_id,
            str(plan["consumer_id"]),
            ConsumerDisposition.STALE,
            occurred_at=operation_time,
            idempotency_key=(
                f"superset-compensated-{str(compensation['compensation_digest'])[-16:]}"
            ),
        )
        return {
            "result": "RESTORED",
            "compensation": compensation,
            "manifest": manifest,
        }

    def reconcile_source(
        self,
        campaign_id: str,
        datahub_observation: Mapping[str, Any],
    ) -> dict[str, Any]:
        plan = self._plan(campaign_id)
        receipt = load_object(self._root(campaign_id) / "receipt.json")
        projection = self.store.projection(campaign_id)
        if projection.evidence_envelope is None:
            raise Refusal(
                RefusalCode.EVIDENCE_REQUIRED_SOURCE_INCOMPLETE,
                "Superset reconciliation requires a campaign evidence envelope.",
            )
        baseline_source = _source(
            projection.evidence_envelope,
            superset_source_id(plan),
        )
        try:
            observation = self.native.reconcile(plan, receipt, datahub_observation)
        except Refusal:
            current = self.store.projection(campaign_id).consumers[
                str(plan["consumer_id"])
            ]
            if (
                ConsumerDisposition(str(current["disposition"]))
                == ConsumerDisposition.VALIDATED
            ):
                self.store.change_consumer_disposition(
                    campaign_id,
                    str(plan["consumer_id"]),
                    ConsumerDisposition.STALE,
                    occurred_at=utc_now(),
                    idempotency_key=f"superset-stale-{str(receipt['receipt_digest'])[-16:]}",
                )
            raise
        envelope = merge_superset_reconciliation_evidence(
            projection.evidence_envelope,
            observation,
            baseline_source=baseline_source,
            plan=plan,
        )
        return {
            "result": "RECONCILED",
            "observation": observation,
            "evidence_envelope": envelope,
        }

    def _root(self, campaign_id: str) -> Path:
        return self.artifact_directory / campaign_id / "superset"

    def _plan(self, campaign_id: str) -> dict[str, Any]:
        plan = load_object(self._root(campaign_id) / "plan.json")
        verify_digest(plan, "plan_digest")
        if plan["campaign_id"] != campaign_id:
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_CAMPAIGN,
                "The current Superset plan belongs to another campaign.",
            )
        return plan

    @staticmethod
    def _require_current_plan(
        consumers: Mapping[str, Mapping[str, Any]],
        plan: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        consumer = consumers.get(str(plan["consumer_id"]))
        if consumer is None:
            raise Refusal(
                RefusalCode.IDENTITY_NOT_FOUND,
                "The Superset plan consumer is absent from campaign state.",
            )
        if (
            consumer.get("plan_digest") != plan["plan_digest"]
            or consumer.get("source_version") != plan["source_version"]
            or consumer.get("approved_targets") != plan["proposed_targets"]
        ):
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
                "Campaign state is not bound to the current Superset plan.",
            )
        return consumer


def superset_source_id(plan: Mapping[str, Any]) -> str:
    return f"superset:{plan['native_identity']['dataset_uuid']}"


def merge_superset_evidence(
    evidence_envelope: Mapping[str, Any],
    preflight: Mapping[str, Any],
) -> dict[str, Any]:
    """Add exact Superset native scope to a live campaign envelope."""

    verify_digest(dict(evidence_envelope), "envelope_digest")
    verify_digest(dict(preflight), "preflight_digest")
    identity = preflight["native_identity"]
    source_id = f"superset:{identity['dataset_uuid']}"
    sources = [
        dict(source)
        for source in evidence_envelope["sources"]
        if source["id"] != source_id
    ]
    capabilities = preflight["capabilities"]
    effective = [
        capability
        for capability in ("read", "plan", "apply", "validate", "compensate")
        if capabilities[capability]
    ]
    sources.append(
        {
            "id": source_id,
            "required": True,
            "status": "COMPLETE",
            "source_version": preflight["source_version"],
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
                "observed_at": preflight["captured_at"],
                "source_updated_at": preflight["snapshot"]["source_updated_at"],
                "maximum_age_seconds": 3600,
            },
            "permissions": {
                "principal": preflight["principal"],
                "effective_scope": ",".join(effective),
            },
            "limitations": list(preflight["limitations"]),
            "artifact_ids": list(preflight["artifact_ids"]),
        }
    )
    merged = with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": preflight["captured_at"],
            "mode": evidence_envelope["mode"],
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


def merge_superset_reconciliation_evidence(
    evidence_envelope: Mapping[str, Any],
    observation: Mapping[str, Any],
    *,
    baseline_source: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Refresh Superset evidence without widening its declared scope."""

    verify_digest(dict(evidence_envelope), "envelope_digest")
    verify_digest(dict(observation), "reconciliation_digest")
    source_id = superset_source_id(plan)
    sources = [
        dict(source)
        for source in evidence_envelope["sources"]
        if source["id"] != source_id
    ]
    sources.append(
        {
            **dict(baseline_source),
            "status": "COMPLETE",
            "freshness": {
                **dict(baseline_source["freshness"]),
                "observed_at": observation["captured_at"],
                "source_updated_at": observation["captured_at"],
            },
            "limitations": list(observation["limitations"]),
            "artifact_ids": [observation["reconciliation_digest"]],
        }
    )
    merged = with_digest(
        {
            "schema_version": "1.0.0",
            "captured_at": observation["captured_at"],
            "mode": evidence_envelope["mode"],
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


def _source(envelope: Mapping[str, Any], source_id: str) -> dict[str, Any]:
    matches = [
        dict(source) for source in envelope["sources"] if source["id"] == source_id
    ]
    if len(matches) != 1:
        raise Refusal(
            RefusalCode.EVIDENCE_REQUIRED_SOURCE_INCOMPLETE,
            "The campaign envelope did not contain one Superset source.",
            {"source_id": source_id, "match_count": len(matches)},
        )
    return matches[0]
