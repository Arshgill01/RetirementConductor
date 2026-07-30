"""Campaign orchestration for the bounded Git/dbt adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from retirement_conductor.canonical import (
    digest_json,
    verify_digest,
    with_digest,
)
from retirement_conductor.clock import parse_timestamp
from retirement_conductor.datahub import DataHubBoundary, utc_now
from retirement_conductor.errors import Refusal
from retirement_conductor.git_dbt import (
    GitDbtAdapter,
    load_object,
    load_optional_object,
    merge_repository_evidence,
    write_versioned_artifact,
)
from retirement_conductor.records import validate_approval
from retirement_conductor.store import CampaignStore
from retirement_conductor.vocabulary import (
    CampaignState,
    ConsumerDisposition,
    RefusalCode,
)


class GitDbtWorkflow:
    """Connect one adapter operation to the durable campaign state machine."""

    def __init__(
        self,
        *,
        store: CampaignStore,
        adapter: GitDbtAdapter,
        artifact_directory: Path,
        boundary: DataHubBoundary | None = None,
    ) -> None:
        self.store = store
        self.adapter = adapter
        self.artifact_directory = artifact_directory
        self.boundary = boundary

    def preflight(self, campaign_id: str) -> dict[str, Any]:
        """Refresh DataHub, inspect Git/dbt, and bind both named sources."""

        if self.boundary is None:
            raise Refusal(
                RefusalCode.SOURCE_DATAHUB_UNAVAILABLE,
                "Git/dbt preflight requires the live DataHub boundary.",
            )
        projection = self.store.projection(campaign_id)
        if projection.state not in {
            CampaignState.PROPOSED,
            CampaignState.INVENTORIED,
        }:
            raise Refusal(
                RefusalCode.POLICY_ILLEGAL_CAMPAIGN_TRANSITION,
                "Repository evidence can only join a proposed or inventoried campaign.",
                {"state": projection.state},
            )
        specification = self.store.specification(campaign_id)
        datahub_root = (
            self.artifact_directory / campaign_id / "datahub" / "git-dbt-baseline"
        )
        snapshot = self.boundary.inventory(
            specification,
            artifact_root=datahub_root,
        )
        git_root = self._git_root(campaign_id)
        preflight = self.adapter.preflight(
            specification,
            datahub_resolution=snapshot["resolution"],
            known_consumer_urns=[
                str(consumer["datahub_urn"]) for consumer in snapshot["consumers"]
            ],
            artifact_root=git_root,
        )
        selected_id = str(
            next(
                consumer["id"]
                for consumer in snapshot["consumers"]
                if consumer["datahub_urn"] == preflight["mapping"]["datahub_urn"]
            )
        )
        merged = merge_repository_evidence(
            snapshot["evidence_envelope"],
            preflight,
        )
        binding = with_digest(
            {
                "schema_version": "1.0.0",
                "campaign_id": campaign_id,
                "mode": "live",
                "captured_at": preflight["captured_at"],
                "datahub_snapshot_digest": snapshot["snapshot_digest"],
                "git_preflight_digest": preflight["preflight_digest"],
                "selected_consumer_id": selected_id,
                "selected_datahub_urn": preflight["mapping"]["datahub_urn"],
                "evidence_envelope_digest": merged["envelope_digest"],
            },
            "binding_digest",
        )
        write_versioned_artifact(git_root, "inventory-binding", binding)
        manifest = self.store.record_inventory(
            campaign_id,
            evidence_envelope=merged,
            consumers=[
                {
                    "id": consumer["id"],
                    "disposition": consumer["disposition"],
                    "receipt_digest": None,
                }
                for consumer in snapshot["consumers"]
            ],
            snapshot_digest=str(binding["binding_digest"]),
            occurred_at=str(preflight["captured_at"]),
            idempotency_key=f"git-dbt-inventory-{str(binding['binding_digest'])[-16:]}",
        )
        return {
            "result": "PREFLIGHT_OK",
            "preflight": preflight,
            "binding": binding,
            "manifest": manifest,
        }

    def plan(self, campaign_id: str) -> dict[str, Any]:
        specification = self.store.specification(campaign_id)
        preflight = load_object(self._git_root(campaign_id) / "preflight.json")
        plan = self.adapter.plan(
            specification,
            preflight,
            campaign_id=campaign_id,
            artifact_root=self._git_root(campaign_id),
        )
        projection = self.store.projection(campaign_id)
        consumer_id = str(plan["consumer_id"])
        consumer = projection.consumers.get(consumer_id)
        if consumer is None:
            raise Refusal(
                RefusalCode.IDENTITY_NOT_FOUND,
                "The exact Git/dbt consumer is absent from campaign inventory.",
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
                idempotency_key=(
                    f"git-dbt-identify-{str(preflight['preflight_digest'])[-16:]}"
                ),
            )
            disposition = ConsumerDisposition.IDENTIFIED
        if disposition == ConsumerDisposition.CHANGE_PROPOSED:
            current = self.store.projection(campaign_id).consumers[consumer_id]
            if (
                current.get("plan_digest") == plan["plan_digest"]
                and current.get("source_version")
                == plan["repository"]["source_version"]
                and current.get("approved_targets") == [plan["target"]["path"]]
            ):
                write_versioned_artifact(
                    self._git_root(campaign_id),
                    "plan",
                    plan,
                )
                return {
                    "result": "PLANNED",
                    "plan": plan,
                    "apply_confirmation": {
                        "required": True,
                        "argument": "--confirm-plan-digest",
                        "plan_digest": plan["plan_digest"],
                        "authorized_targets": [plan["target"]["path"]],
                    },
                    "manifest": self.store.materialize(campaign_id),
                }
            raise Refusal(
                RefusalCode.POLICY_ILLEGAL_CONSUMER_TRANSITION,
                "A different proposed plan must be made stale before replacement.",
            )
        if disposition not in {
            ConsumerDisposition.IDENTIFIED,
            ConsumerDisposition.STALE,
            ConsumerDisposition.FAILED,
        }:
            raise Refusal(
                RefusalCode.POLICY_ILLEGAL_CONSUMER_TRANSITION,
                "The consumer is not eligible for a new Git/dbt plan.",
                {"disposition": disposition},
            )
        write_versioned_artifact(
            self._git_root(campaign_id),
            "plan",
            plan,
        )
        manifest = self.store.change_consumer_disposition(
            campaign_id,
            consumer_id,
            ConsumerDisposition.CHANGE_PROPOSED,
            occurred_at=occurred_at,
            idempotency_key=f"git-dbt-plan-{str(plan['plan_digest'])[-16:]}",
            plan_digest=str(plan["plan_digest"]),
            source_version=str(plan["repository"]["source_version"]),
            approved_targets=[str(plan["target"]["path"])],
        )
        return {
            "result": "PLANNED",
            "plan": plan,
            "apply_confirmation": {
                "required": True,
                "argument": "--confirm-plan-digest",
                "plan_digest": plan["plan_digest"],
                "authorized_targets": [plan["target"]["path"]],
            },
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
                    f"git-dbt-{campaign_id}-{str(plan['plan_digest'])[-12:]}"
                ),
                "campaign_id": campaign_id,
                "plan_digest": plan["plan_digest"],
                "source_version": plan["repository"]["source_version"],
                "targets": [plan["target"]["path"]],
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
            source_version=str(plan["repository"]["source_version"]),
            targets=[str(plan["target"]["path"])],
            required_scope=["apply", "compensate"],
            trusted_now=parse_timestamp(authorized_at),
            occurred_at=authorized_at,
            idempotency_key=f"git-dbt-approval-{str(approval['approval_digest'])[-16:]}",
        )
        write_versioned_artifact(
            self._git_root(campaign_id),
            "approval",
            approval,
        )
        return {"result": "AUTHORIZED", "approval": approval, "manifest": manifest}

    def apply(
        self,
        campaign_id: str,
        *,
        confirmed_plan_digest: str,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        operation_time = occurred_at or utc_now()
        specification = self.store.specification(campaign_id)
        plan = self._plan(campaign_id)
        if confirmed_plan_digest != plan["plan_digest"]:
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
                "Apply confirmation does not match the exact current plan digest.",
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
                "The Git/dbt consumer is not awaiting apply.",
                {"disposition": disposition},
            )
        self.store.begin_migration_with_claim(
            campaign_id,
            plan["native_identity"],
            plan_digest=str(plan["plan_digest"]),
            source_version=str(plan["repository"]["source_version"]),
            targets=[str(plan["target"]["path"])],
            required_scope=["apply"],
            trusted_now=parse_timestamp(operation_time),
            occurred_at=operation_time,
        )
        apply_record = self.adapter.apply(
            specification,
            plan,
            artifact_root=self._git_root(campaign_id),
            occurred_at=operation_time,
        )
        manifest = self.store.materialize(campaign_id)
        if disposition == ConsumerDisposition.CHANGE_PROPOSED:
            manifest = self.store.change_consumer_disposition(
                campaign_id,
                str(plan["consumer_id"]),
                ConsumerDisposition.APPLIED,
                occurred_at=operation_time,
                idempotency_key=(
                    f"git-dbt-applied-{str(apply_record['apply_digest'])[-16:]}"
                ),
            )
        return {
            "result": "APPLIED",
            "apply": apply_record,
            "confirmed_plan_digest": confirmed_plan_digest,
            "authorized_targets": [plan["target"]["path"]],
            "manifest": manifest,
        }

    def compensate(
        self,
        campaign_id: str,
        *,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        operation_time = occurred_at or utc_now()
        specification = self.store.specification(campaign_id)
        plan = self._plan(campaign_id)
        apply_record = load_object(self._git_root(campaign_id) / "apply.json")
        projection = self.store.projection(campaign_id)
        consumer = self._require_current_plan(projection.consumers, plan)
        disposition = ConsumerDisposition(str(consumer["disposition"]))
        if disposition != ConsumerDisposition.APPLIED:
            raise Refusal(
                RefusalCode.POLICY_ILLEGAL_CONSUMER_TRANSITION,
                "Only an applied Git/dbt consumer can be compensated.",
                {"disposition": disposition},
            )
        validate_approval(
            projection.approvals.get(str(plan["plan_digest"])),
            campaign_id=campaign_id,
            plan_digest=str(plan["plan_digest"]),
            source_version=str(plan["repository"]["source_version"]),
            targets=[str(plan["target"]["path"])],
            required_scope=["compensate"],
            authorization_digest=projection.input_digests["authorization"],
            trusted_now=parse_timestamp(operation_time),
        )
        compensation = self.adapter.compensate(
            specification,
            plan,
            apply_record,
            artifact_root=self._git_root(campaign_id),
            occurred_at=operation_time,
        )
        manifest = self.store.change_consumer_disposition(
            campaign_id,
            str(plan["consumer_id"]),
            ConsumerDisposition.STALE,
            occurred_at=operation_time,
            idempotency_key=(
                f"git-dbt-compensated-{str(compensation['compensation_digest'])[-16:]}"
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
        projection = self.store.projection(campaign_id)
        consumer = self._require_current_plan(projection.consumers, plan)
        disposition = ConsumerDisposition(str(consumer["disposition"]))
        if disposition == ConsumerDisposition.VALIDATED:
            receipt = load_object(self._git_root(campaign_id) / "receipt.json")
            verify_digest(receipt, "receipt_digest")
            return {
                "result": "VALIDATED",
                "validation": load_object(
                    self._git_root(campaign_id) / "native-validation/validation.json"
                ),
                "receipt": receipt,
                "manifest": self.store.materialize(campaign_id),
            }
        if disposition != ConsumerDisposition.APPLIED:
            raise Refusal(
                RefusalCode.POLICY_ILLEGAL_CONSUMER_TRANSITION,
                "Only an applied Git/dbt consumer can enter native validation.",
                {"disposition": disposition},
            )
        validation = self.adapter.validate_project(
            artifact_root=self._git_root(campaign_id) / "native-validation",
        )
        if validation["result"] != "PASSED":
            self.store.change_consumer_disposition(
                campaign_id,
                str(plan["consumer_id"]),
                ConsumerDisposition.FAILED,
                occurred_at=operation_time,
                idempotency_key=(
                    f"git-dbt-validation-failed-"
                    f"{str(validation['validation_digest'])[-16:]}"
                ),
            )
            raise Refusal(
                RefusalCode.VALIDATION_RECEIPT_FAILED,
                "The applied Git/dbt project failed native validation.",
                {"validation_digest": validation["validation_digest"]},
            )
        apply_record = load_object(self._git_root(campaign_id) / "apply.json")
        compensation = load_optional_object(
            self._git_root(campaign_id) / "compensation.json"
        )
        receipt = self.adapter.emit_receipt(
            plan,
            apply_record,
            validation,
            compensation=compensation,
            captured_at=operation_time,
            expires_at=expires_at,
            artifact_root=self._git_root(campaign_id),
        )
        manifest = self.store.accept_receipt(
            campaign_id,
            str(plan["consumer_id"]),
            receipt,
            trusted_now=parse_timestamp(operation_time),
            occurred_at=operation_time,
            idempotency_key=f"git-dbt-receipt-{str(receipt['receipt_digest'])[-16:]}",
        )
        return {
            "result": "VALIDATED",
            "validation": validation,
            "receipt": receipt,
            "manifest": manifest,
        }

    def _git_root(self, campaign_id: str) -> Path:
        return self.artifact_directory / campaign_id / "git-dbt"

    def _plan(self, campaign_id: str) -> dict[str, Any]:
        plan = load_object(self._git_root(campaign_id) / "plan.json")
        verify_digest(plan, "plan_digest")
        if plan["campaign_id"] != campaign_id:
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_CAMPAIGN,
                "The current Git/dbt plan belongs to another campaign.",
            )
        return plan

    @staticmethod
    def _require_current_plan(
        consumers: dict[str, dict[str, Any]],
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        consumer = consumers.get(str(plan["consumer_id"]))
        if consumer is None:
            raise Refusal(
                RefusalCode.IDENTITY_NOT_FOUND,
                "The Git/dbt plan consumer is absent from campaign state.",
            )
        if (
            consumer.get("plan_digest") != plan["plan_digest"]
            or consumer.get("source_version") != plan["repository"]["source_version"]
            or consumer.get("approved_targets") != [plan["target"]["path"]]
        ):
            raise Refusal(
                RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
                "Campaign state is not bound to the current Git/dbt plan.",
                {
                    "consumer_id": plan["consumer_id"],
                    "plan_identity": digest_json(plan),
                },
            )
        return consumer
