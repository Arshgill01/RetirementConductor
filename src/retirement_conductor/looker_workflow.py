"""Durable campaign orchestration for the bounded saved-Look adapter."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from retirement_conductor.canonical import (
    digest_json,
    verify_digest,
    with_digest,
    write_json,
)
from retirement_conductor.clock import parse_timestamp
from retirement_conductor.datahub import ArtifactWriter, utc_now
from retirement_conductor.errors import Refusal
from retirement_conductor.looker import LookerAdapter, merge_looker_evidence
from retirement_conductor.records import validate_approval
from retirement_conductor.store import CampaignStore
from retirement_conductor.vocabulary import (
    CampaignState,
    ConsumerDisposition,
    RefusalCode,
)


class InventoryBoundary(Protocol):
    def inventory(
        self,
        specification: Mapping[str, Any],
        *,
        artifact_root: Path,
    ) -> dict[str, Any]: ...


class LookerWorkflow:
    """Bind one native Looker lifecycle to durable campaign state."""

    def __init__(
        self,
        *,
        store: CampaignStore,
        adapter: LookerAdapter,
        artifact_directory: Path,
        boundary: InventoryBoundary | None = None,
    ) -> None:
        self.store = store
        self.adapter = adapter
        self.artifact_directory = artifact_directory
        self.boundary = boundary

    def preflight(self, campaign_id: str) -> dict[str, Any]:
        if self.boundary is None:
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                "Looker preflight requires a fresh DataHub inventory boundary.",
            )
        projection = self.store.projection(campaign_id)
        if projection.state not in {
            CampaignState.PROPOSED,
            CampaignState.INVENTORIED,
            CampaignState.MIGRATING,
            CampaignState.BLOCKED,
        }:
            raise Refusal(
                RefusalCode.POLICY_ILLEGAL_CAMPAIGN_TRANSITION,
                "Looker evidence cannot join the campaign in its current state.",
                {"state": projection.state},
            )
        specification = self.store.specification(campaign_id)
        self._require_specification_scope(specification)
        root = self._looker_root(campaign_id)
        datahub_snapshot = self.boundary.inventory(
            specification,
            artifact_root=(
                self.artifact_directory / campaign_id / "datahub" / "looker-baseline"
            ),
        )
        if (
            datahub_snapshot["snapshot_digest"]
            != self.adapter.settings.graph_snapshot_digest
        ):
            raise Refusal(
                RefusalCode.SOURCE_FINGERPRINT_MISMATCH,
                "The configured DataHub graph snapshot digest is not the fresh "
                "inventory used for Looker identity.",
                {
                    "configured_graph_snapshot_digest": (
                        self.adapter.settings.graph_snapshot_digest
                    ),
                    "observed_graph_snapshot_digest": datahub_snapshot[
                        "snapshot_digest"
                    ],
                },
            )
        matches = [
            consumer
            for consumer in datahub_snapshot["consumers"]
            if consumer["datahub_urn"] == self.adapter.settings.datahub_urn
        ]
        if len(matches) != 1:
            code = (
                RefusalCode.IDENTITY_NOT_FOUND
                if not matches
                else RefusalCode.IDENTITY_AMBIGUOUS
            )
            raise Refusal(
                code,
                "Fresh DataHub evidence must map the configured URN to exactly "
                "one campaign consumer.",
                {"match_count": len(matches)},
            )
        preflight = self.adapter.preflight()
        if preflight["mode"] != datahub_snapshot["evidence_envelope"]["mode"]:
            raise Refusal(
                RefusalCode.EVIDENCE_MODE_NOT_LIVE,
                "Looker and DataHub evidence modes do not match.",
                {
                    "looker_mode": preflight["mode"],
                    "datahub_mode": datahub_snapshot["evidence_envelope"]["mode"],
                },
            )
        native_snapshot = with_digest(
            self.adapter.snapshot(),
            "snapshot_digest",
        )
        if (
            native_snapshot["native_identity"]["datahub_urn"]
            != matches[0]["datahub_urn"]
        ):
            raise Refusal(
                RefusalCode.IDENTITY_NOT_FOUND,
                "The DataHub consumer and native Look identity do not match.",
            )
        writer = ArtifactWriter(root / "raw")
        artifact_ids = [
            writer.write("capability-preflight", preflight),
            writer.write("native-baseline", native_snapshot),
        ]
        merged = merge_looker_evidence(
            datahub_snapshot["evidence_envelope"],
            preflight,
            native_snapshot,
            artifact_ids=artifact_ids,
            prior_envelope=projection.evidence_envelope,
        )
        binding = with_digest(
            {
                "schema_version": "1.0.0",
                "campaign_id": campaign_id,
                "mode": preflight["mode"],
                "captured_at": native_snapshot["captured_at"],
                "datahub_snapshot_digest": datahub_snapshot["snapshot_digest"],
                "looker_preflight_digest": preflight["preflight_digest"],
                "native_snapshot_digest": native_snapshot["snapshot_digest"],
                "selected_consumer_id": matches[0]["id"],
                "selected_datahub_urn": matches[0]["datahub_urn"],
                "evidence_envelope_digest": merged["envelope_digest"],
                "artifact_ids": artifact_ids,
            },
            "binding_digest",
        )
        _write_artifact(root, "preflight", preflight)
        _write_artifact(root, "native-baseline", native_snapshot)
        _write_artifact(root, "inventory-binding", binding)
        consumers = [
            {
                "id": consumer["id"],
                "disposition": consumer["disposition"],
                "receipt_digest": None,
            }
            for consumer in datahub_snapshot["consumers"]
        ]
        if projection.state == CampaignState.PROPOSED:
            manifest = self.store.record_inventory(
                campaign_id,
                evidence_envelope=merged,
                consumers=consumers,
                snapshot_digest=str(binding["binding_digest"]),
                occurred_at=str(native_snapshot["captured_at"]),
                idempotency_key=(
                    f"looker-inventory-{str(binding['binding_digest'])[-16:]}"
                ),
            )
        else:
            manifest = self.store.extend_inventory(
                campaign_id,
                evidence_envelope=merged,
                consumers=consumers,
                snapshot_digest=str(binding["binding_digest"]),
                occurred_at=str(native_snapshot["captured_at"]),
                idempotency_key=(
                    f"looker-inventory-extension-{str(binding['binding_digest'])[-16:]}"
                ),
            )
        return {
            "result": "PREFLIGHT_OK",
            "preflight": preflight,
            "native_snapshot": native_snapshot,
            "binding": binding,
            "manifest": manifest,
        }

    def plan(self, campaign_id: str) -> dict[str, Any]:
        specification = self.store.specification(campaign_id)
        self._require_specification_scope(specification)
        binding = _load_artifact(
            self._looker_root(campaign_id) / "inventory-binding.json",
            "binding_digest",
        )
        if (
            binding["campaign_id"] != campaign_id
            or binding["selected_datahub_urn"] != self.adapter.settings.datahub_urn
            or binding["datahub_snapshot_digest"]
            != self.adapter.settings.graph_snapshot_digest
        ):
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_SOURCE,
                "The Looker inventory binding is not current for this campaign.",
            )
        fresh_preflight = self.adapter.preflight()
        _write_artifact(
            self._looker_root(campaign_id),
            "preflight",
            fresh_preflight,
        )
        plan = self.adapter.plan(
            campaign_id=campaign_id,
            consumer_id=str(binding["selected_consumer_id"]),
        )
        projection = self.store.projection(campaign_id)
        consumer_id = str(plan["consumer_id"])
        consumer = projection.consumers.get(consumer_id)
        if consumer is None:
            raise Refusal(
                RefusalCode.IDENTITY_NOT_FOUND,
                "The exact Looker consumer is absent from campaign inventory.",
            )
        occurred_at = utc_now()
        disposition = ConsumerDisposition(str(consumer["disposition"]))
        if disposition in {
            ConsumerDisposition.DISCOVERED,
            ConsumerDisposition.OPAQUE,
            ConsumerDisposition.UNRESOLVED,
        }:
            self.store.change_consumer_disposition(
                campaign_id,
                consumer_id,
                ConsumerDisposition.IDENTIFIED,
                occurred_at=occurred_at,
                idempotency_key=(f"looker-identify-{str(plan['plan_digest'])[-16:]}"),
            )
            disposition = ConsumerDisposition.IDENTIFIED
        if disposition == ConsumerDisposition.CHANGE_PROPOSED:
            current = self.store.projection(campaign_id).consumers[consumer_id]
            if (
                current.get("plan_digest") == plan["plan_digest"]
                and current.get("source_version") == plan["source"]["version"]
                and current.get("approved_targets") == plan["target_sets"]["approved"]
            ):
                _write_artifact(self._looker_root(campaign_id), "plan", plan)
                return self._plan_result(campaign_id, plan)
            raise Refusal(
                RefusalCode.POLICY_ILLEGAL_CONSUMER_TRANSITION,
                "A different Looker plan must be made stale before replacement.",
            )
        if disposition not in {
            ConsumerDisposition.IDENTIFIED,
            ConsumerDisposition.STALE,
            ConsumerDisposition.FAILED,
        }:
            raise Refusal(
                RefusalCode.POLICY_ILLEGAL_CONSUMER_TRANSITION,
                "The Looker consumer is not eligible for a new plan.",
                {"disposition": disposition},
            )
        _write_artifact(self._looker_root(campaign_id), "plan", plan)
        self.store.change_consumer_disposition(
            campaign_id,
            consumer_id,
            ConsumerDisposition.CHANGE_PROPOSED,
            occurred_at=occurred_at,
            idempotency_key=f"looker-plan-{str(plan['plan_digest'])[-16:]}",
            plan_digest=str(plan["plan_digest"]),
            source_version=str(plan["source"]["version"]),
            approved_targets=list(plan["target_sets"]["approved"]),
        )
        return self._plan_result(campaign_id, plan)

    def authorize(
        self,
        campaign_id: str,
        *,
        principal: str,
        authorized_at: str,
        expires_at: str,
    ) -> dict[str, Any]:
        if not principal.strip():
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_SCOPE,
                "Looker authorization requires a named operator principal.",
            )
        plan = self._plan(campaign_id)
        projection = self.store.projection(campaign_id)
        self._require_current_plan(projection.consumers, plan)
        approval = with_digest(
            {
                "schema_version": "1.0.0",
                "approval_id": (
                    f"looker-{campaign_id}-{str(plan['plan_digest'])[-12:]}"
                ),
                "campaign_id": campaign_id,
                "plan_digest": plan["plan_digest"],
                "source_version": plan["source"]["version"],
                "targets": plan["target_sets"]["approved"],
                "principal": principal.strip(),
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
            source_version=str(plan["source"]["version"]),
            targets=list(plan["target_sets"]["approved"]),
            required_scope=["apply", "compensate"],
            trusted_now=parse_timestamp(authorized_at),
            occurred_at=authorized_at,
            idempotency_key=(
                f"looker-approval-{str(approval['approval_digest'])[-16:]}"
            ),
        )
        _write_artifact(self._looker_root(campaign_id), "approval", approval)
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
        if confirmed_plan_digest != plan["plan_digest"]:
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
                "Apply confirmation does not match the exact current Looker plan.",
                {
                    "confirmed_plan_digest": confirmed_plan_digest,
                    "current_plan_digest": plan["plan_digest"],
                },
            )
        projection = self.store.projection(campaign_id)
        consumer = self._require_current_plan(projection.consumers, plan)
        disposition = ConsumerDisposition(str(consumer["disposition"]))
        if disposition not in {
            ConsumerDisposition.CHANGE_PROPOSED,
            ConsumerDisposition.APPLIED,
        }:
            raise Refusal(
                RefusalCode.POLICY_ILLEGAL_CONSUMER_TRANSITION,
                "The Looker consumer is not awaiting apply.",
                {"disposition": disposition},
            )
        self.store.begin_migration_with_claim(
            campaign_id,
            plan["native_identity"],
            plan_digest=str(plan["plan_digest"]),
            source_version=str(plan["source"]["version"]),
            targets=list(plan["target_sets"]["approved"]),
            required_scope=["apply"],
            trusted_now=parse_timestamp(operation_time),
            occurred_at=operation_time,
        )
        root = self._looker_root(campaign_id)
        intent = _load_optional_artifact(root / "apply-intent.json", "intent_digest")
        if intent is not None and intent.get("plan_digest") != plan["plan_digest"]:
            intent = None
        if intent is None:
            intent = self.adapter.prepare_apply_intent(
                plan,
                recorded_at=operation_time,
            )
            _write_artifact(root, "apply-intent", intent)
        prior_apply = _load_optional_artifact(root / "apply.json", "apply_digest")
        if (
            prior_apply is not None
            and prior_apply.get("plan_digest") != plan["plan_digest"]
        ):
            prior_apply = None
        try:
            apply_record = self.adapter.apply(
                plan,
                intent,
                prior_apply=prior_apply,
                occurred_at=operation_time,
            )
        except Refusal as exc:
            if exc.code == RefusalCode.APPLY_OUTCOME_UNKNOWN:
                unknown = self.adapter.mark_intent_outcome_unknown(
                    intent,
                    observed_at=operation_time,
                    reason=str(exc.code),
                )
                _write_artifact(root, "apply-intent", unknown)
            raise
        _write_artifact(root, "apply", apply_record)
        resolved = self.adapter.mark_intent_resolved(
            intent,
            apply_digest=str(apply_record["apply_digest"]),
            observed_at=operation_time,
        )
        _write_artifact(root, "apply-intent", resolved)
        manifest = self.store.materialize(campaign_id)
        if disposition == ConsumerDisposition.CHANGE_PROPOSED:
            manifest = self.store.change_consumer_disposition(
                campaign_id,
                str(plan["consumer_id"]),
                ConsumerDisposition.APPLIED,
                occurred_at=operation_time,
                idempotency_key=(
                    f"looker-applied-{str(apply_record['apply_digest'])[-16:]}"
                ),
            )
        return {
            "result": "APPLIED",
            "apply": apply_record,
            "intent": resolved,
            "confirmed_plan_digest": confirmed_plan_digest,
            "authorized_targets": plan["target_sets"]["approved"],
            "manifest": manifest,
        }

    def compensate(
        self,
        campaign_id: str,
        *,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        operation_time = occurred_at or utc_now()
        plan = self._plan(campaign_id)
        root = self._looker_root(campaign_id)
        apply_record = _load_artifact(root / "apply.json", "apply_digest")
        if apply_record.get("plan_digest") != plan["plan_digest"]:
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
                "The current Looker apply record belongs to another plan.",
            )
        projection = self.store.projection(campaign_id)
        consumer = self._require_current_plan(projection.consumers, plan)
        disposition = ConsumerDisposition(str(consumer["disposition"]))
        if disposition != ConsumerDisposition.APPLIED:
            raise Refusal(
                RefusalCode.POLICY_ILLEGAL_CONSUMER_TRANSITION,
                "Only an applied Looker consumer can be compensated.",
                {"disposition": disposition},
            )
        validate_approval(
            projection.approvals.get(str(plan["plan_digest"])),
            campaign_id=campaign_id,
            plan_digest=str(plan["plan_digest"]),
            source_version=str(plan["source"]["version"]),
            targets=list(plan["target_sets"]["approved"]),
            required_scope=["compensate"],
            authorization_digest=projection.input_digests["authorization"],
            trusted_now=parse_timestamp(operation_time),
        )
        compensation = self.adapter.compensate(
            plan,
            apply_record,
            occurred_at=operation_time,
        )
        _write_artifact(root, "compensation", compensation)
        manifest = self.store.change_consumer_disposition(
            campaign_id,
            str(plan["consumer_id"]),
            ConsumerDisposition.STALE,
            occurred_at=operation_time,
            idempotency_key=(
                f"looker-compensated-{str(compensation['compensation_digest'])[-16:]}"
            ),
        )
        return {
            "result": "RESTORED",
            "compensation": compensation,
            "manifest": manifest,
        }

    def validate(
        self,
        campaign_id: str,
        *,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        operation_time = utc_now()
        plan = self._plan(campaign_id)
        root = self._looker_root(campaign_id)
        projection = self.store.projection(campaign_id)
        consumer = self._require_current_plan(projection.consumers, plan)
        disposition = ConsumerDisposition(str(consumer["disposition"]))
        if disposition == ConsumerDisposition.VALIDATED:
            return {
                "result": "VALIDATED",
                "validation": _load_artifact(
                    root / "native-validation.json",
                    "validation_digest",
                ),
                "receipt": _load_artifact(
                    root / "receipt.json",
                    "receipt_digest",
                ),
                "manifest": self.store.materialize(campaign_id),
            }
        if disposition != ConsumerDisposition.APPLIED:
            raise Refusal(
                RefusalCode.POLICY_ILLEGAL_CONSUMER_TRANSITION,
                "Only an applied Looker consumer can enter native validation.",
                {"disposition": disposition},
            )
        apply_record = _load_artifact(root / "apply.json", "apply_digest")
        if apply_record.get("plan_digest") != plan["plan_digest"]:
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
                "The current Looker apply record belongs to another plan.",
            )
        try:
            validation = self.adapter.validate(plan, apply_record)
        except Refusal:
            self.store.change_consumer_disposition(
                campaign_id,
                str(plan["consumer_id"]),
                ConsumerDisposition.FAILED,
                occurred_at=operation_time,
                idempotency_key=(
                    f"looker-validation-failed-{str(plan['plan_digest'])[-16:]}"
                ),
            )
            raise
        writer = ArtifactWriter(root / "raw")
        evidence_id = writer.write("native-validation", validation)
        validation = with_digest(
            {
                **validation,
                "artifact_ids": [evidence_id],
            },
            "validation_digest",
        )
        _write_artifact(root, "native-validation", validation)
        compensation = _load_optional_artifact(
            root / "compensation.json",
            "compensation_digest",
        )
        receipt = self.adapter.emit_receipt(
            plan,
            apply_record,
            validation,
            compensation=compensation,
            captured_at=operation_time,
            expires_at=expires_at,
            artifact_ids=[evidence_id],
        )
        _write_artifact(root, "receipt", receipt)
        manifest = self.store.accept_receipt(
            campaign_id,
            str(plan["consumer_id"]),
            receipt,
            trusted_now=parse_timestamp(operation_time),
            occurred_at=operation_time,
            idempotency_key=(f"looker-receipt-{str(receipt['receipt_digest'])[-16:]}"),
        )
        return {
            "result": "VALIDATED",
            "validation": validation,
            "receipt": receipt,
            "manifest": manifest,
        }

    def _plan_result(
        self,
        campaign_id: str,
        plan: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "result": "PLANNED",
            "plan": plan,
            "apply_confirmation": {
                "required": True,
                "argument": "--confirm-plan-digest",
                "plan_digest": plan["plan_digest"],
                "authorized_targets": plan["target_sets"]["approved"],
            },
            "manifest": self.store.materialize(campaign_id),
        }

    def _plan(self, campaign_id: str) -> dict[str, Any]:
        plan = _load_artifact(
            self._looker_root(campaign_id) / "plan.json",
            "plan_digest",
        )
        if plan["campaign_id"] != campaign_id:
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_CAMPAIGN,
                "The current Looker plan belongs to another campaign.",
            )
        return plan

    def _require_specification_scope(
        self,
        specification: Mapping[str, Any],
    ) -> None:
        target = self.adapter.settings.content_target
        allowed = list(specification["authorization"]["allowed_native_objects"])
        if target not in allowed:
            raise Refusal(
                RefusalCode.SCOPE_TARGET_NOT_ALLOWED,
                "The exact saved Look is absent from allowed_native_objects.",
                {"target": target, "allowed_native_objects": sorted(allowed)},
            )
        required_receipts = specification["validation"]["required_receipt_types"]
        if "looker" not in required_receipts:
            raise Refusal(
                RefusalCode.SPEC_UNSUPPORTED_REPLACEMENT,
                "The campaign specification does not require a Looker receipt.",
            )

    def _looker_root(self, campaign_id: str) -> Path:
        return self.artifact_directory / campaign_id / "looker"

    @staticmethod
    def _require_current_plan(
        consumers: Mapping[str, Mapping[str, Any]],
        plan: Mapping[str, Any],
    ) -> dict[str, Any]:
        consumer = consumers.get(str(plan["consumer_id"]))
        if consumer is None:
            raise Refusal(
                RefusalCode.IDENTITY_NOT_FOUND,
                "The Looker plan consumer is absent from campaign state.",
            )
        value = dict(consumer)
        if (
            value.get("plan_digest") != plan["plan_digest"]
            or value.get("source_version") != plan["source"]["version"]
            or value.get("approved_targets") != plan["target_sets"]["approved"]
        ):
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
                "Campaign state is not bound to the current Looker plan.",
                {
                    "consumer_id": plan["consumer_id"],
                    "plan_identity": digest_json(plan),
                },
            )
        return value


def _write_artifact(
    root: Path,
    name: str,
    value: Mapping[str, Any],
) -> None:
    write_json(root / f"{name}.json", value)
    identity = digest_json(value).removeprefix("sha256:")[:16]
    write_json(root / f"{name}-{identity}.json", value)


def _load_artifact(path: Path, digest_field: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Refusal(
            RefusalCode.SOURCE_LOOKER_UNAVAILABLE,
            "A required Looker campaign artifact could not be read.",
            {"artifact": path.name, "error_type": type(exc).__name__},
        ) from exc
    if not isinstance(value, dict):
        raise Refusal(
            RefusalCode.INTEGRITY_DIGEST_MISMATCH,
            "A required Looker campaign artifact is not a JSON object.",
            {"artifact": path.name},
        )
    verify_digest(value, digest_field)
    return value


def _load_optional_artifact(
    path: Path,
    digest_field: str,
) -> dict[str, Any] | None:
    return _load_artifact(path, digest_field) if path.is_file() else None
