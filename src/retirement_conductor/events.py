"""Tamper-evident campaign events and deterministic projection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from retirement_conductor.canonical import (
    canonical_json,
    digest_json,
    verify_digest,
    with_digest,
)
from retirement_conductor.clock import parse_timestamp, validate_trusted_clock
from retirement_conductor.errors import Refusal
from retirement_conductor.policy import PolicyResult, evaluate_policy
from retirement_conductor.records import require_bound_inputs
from retirement_conductor.schemas import validate_schema
from retirement_conductor.state import (
    require_campaign_transition,
    require_consumer_transition,
)
from retirement_conductor.vocabulary import (
    CampaignState,
    ConsumerDisposition,
    Decision,
    RefusalCode,
)


@dataclass
class CampaignProjection:
    campaign_id: str
    name: str
    state: CampaignState
    specification_digest: str
    target: dict[str, Any]
    replacement: dict[str, Any]
    policy: dict[str, Any]
    input_digests: dict[str, str]
    evidence_envelope: dict[str, Any] | None = None
    inventory_consumer_ids: list[str] = field(default_factory=list)
    current_consumer_ids: list[str] = field(default_factory=list)
    consumers: dict[str, dict[str, Any]] = field(default_factory=dict)
    snapshot_digests: list[str] = field(default_factory=list)
    receipt_digests: list[str] = field(default_factory=list)
    approvals: dict[str, dict[str, Any]] = field(default_factory=dict)
    waivers: dict[str, dict[str, Any]] = field(default_factory=dict)
    reconciliations: list[dict[str, Any]] = field(default_factory=list)
    reconciled: bool = False
    publication: dict[str, Any] | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    last_policy_result: PolicyResult | None = None
    generated_at: str = ""


def build_event(
    *,
    campaign_id: str,
    sequence: int,
    event_type: str,
    occurred_at: str,
    idempotency_key: str,
    previous_event_digest: str | None,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Build one canonical, digest-bound event."""

    event = with_digest(
        {
            "schema_version": "1.0.0",
            "payload_version": "1.0.0",
            "campaign_id": campaign_id,
            "sequence": sequence,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "idempotency_key": idempotency_key,
            "previous_event_digest": previous_event_digest,
            "payload": dict(payload),
        },
        "event_digest",
    )
    validate_schema(
        "campaign-event",
        event,
        refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
    )
    return event


def validate_event_stream(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate sequence, schema, digest, and predecessor chain."""

    validated: list[dict[str, Any]] = []
    previous: str | None = None
    previous_time = None
    for expected_sequence, raw_event in enumerate(events, start=1):
        event = dict(raw_event)
        validate_schema(
            "campaign-event",
            event,
            refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
        )
        if event["sequence"] != expected_sequence:
            raise Refusal(
                RefusalCode.INTEGRITY_EVENT_SEQUENCE_INVALID,
                "The event stream sequence is not contiguous.",
                {
                    "expected_sequence": expected_sequence,
                    "observed_sequence": event["sequence"],
                },
            )
        if event["previous_event_digest"] != previous:
            raise Refusal(
                RefusalCode.INTEGRITY_EVENT_CHAIN_MISMATCH,
                "An event does not reference the preceding event digest.",
                {"sequence": expected_sequence},
            )
        verify_digest(event, "event_digest")
        event_time = parse_timestamp(str(event["occurred_at"]))
        if previous_time is not None and event_time < previous_time:
            raise Refusal(
                RefusalCode.RUNTIME_CLOCK_ROLLBACK,
                "Campaign event time moved backward.",
                {"sequence": expected_sequence},
            )
        previous_time = event_time
        previous = event["event_digest"]
        validated.append(event)
    if not validated:
        raise Refusal(
            RefusalCode.INTEGRITY_EVENT_SEQUENCE_INVALID,
            "A campaign event stream cannot be empty.",
        )
    return validated


def _created_projection(event: Mapping[str, Any]) -> CampaignProjection:
    payload = event["payload"]
    required = {
        "name",
        "specification_digest",
        "target",
        "replacement",
        "policy",
        "input_digests",
    }
    if set(payload) != required:
        raise Refusal(
            RefusalCode.INTEGRITY_DIGEST_MISMATCH,
            "The campaign creation payload fields are not exact.",
            {
                "missing": sorted(required - set(payload)),
                "unexpected": sorted(set(payload) - required),
            },
        )
    return CampaignProjection(
        campaign_id=str(event["campaign_id"]),
        name=str(payload["name"]),
        state=CampaignState.PROPOSED,
        specification_digest=str(payload["specification_digest"]),
        target=dict(payload["target"]),
        replacement=dict(payload["replacement"]),
        policy=dict(payload["policy"]),
        input_digests=dict(payload["input_digests"]),
        events=[dict(event)],
        generated_at=str(event["occurred_at"]),
    )


def _policy_result(
    projection: CampaignProjection,
    *,
    evaluated_at: str | None = None,
) -> PolicyResult:
    trusted_time = parse_timestamp(evaluated_at or projection.generated_at)
    for consumer in projection.consumers.values():
        receipt = consumer.get("receipt")
        if receipt is None:
            continue
        validate_trusted_clock(
            now=trusted_time,
            observed_at=parse_timestamp(receipt["captured_at"]),
            expires_at=(
                parse_timestamp(receipt["expires_at"])
                if receipt["expires_at"] is not None
                else None
            ),
        )
    return evaluate_policy(
        evidence_envelope=projection.evidence_envelope,
        consumers=list(projection.consumers.values()),
        inventory_consumer_ids=projection.inventory_consumer_ids,
        current_consumer_ids=projection.current_consumer_ids,
        reconciled=projection.reconciled,
        policy=projection.policy,
    )


def _apply_event(projection: CampaignProjection, event: dict[str, Any]) -> None:
    event_type = event["event_type"]
    payload = event["payload"]
    if event_type == "INVENTORY_RECORDED":
        if projection.state != CampaignState.INVENTORIED:
            require_campaign_transition(
                projection.state,
                CampaignState.INVENTORIED,
            )
        consumers = {
            str(consumer["id"]): {
                "id": str(consumer["id"]),
                "disposition": ConsumerDisposition(str(consumer["disposition"])),
                "receipt_digest": consumer.get("receipt_digest"),
            }
            for consumer in payload["consumers"]
        }
        if len(consumers) != len(payload["consumers"]):
            raise Refusal(
                RefusalCode.IDENTITY_AMBIGUOUS,
                "The inventory contains duplicate campaign consumer identities.",
            )
        permitted_inventory_dispositions = {
            ConsumerDisposition.DISCOVERED,
            ConsumerDisposition.IDENTIFIED,
            ConsumerDisposition.OPAQUE,
            ConsumerDisposition.UNRESOLVED,
        }
        if any(
            consumer["disposition"] not in permitted_inventory_dispositions
            for consumer in consumers.values()
        ):
            raise Refusal(
                RefusalCode.POLICY_ILLEGAL_CONSUMER_TRANSITION,
                "Inventory cannot import a closure disposition without evidence.",
            )
        projection.state = CampaignState.INVENTORIED
        projection.consumers = consumers
        projection.inventory_consumer_ids = sorted(consumers)
        projection.current_consumer_ids = sorted(consumers)
        projection.evidence_envelope = dict(payload["evidence_envelope"])
        projection.snapshot_digests.append(str(payload["snapshot_digest"]))
        projection.reconciled = False
    elif event_type == "APPROVAL_RECORDED":
        verify_digest(dict(payload["approval"]), "approval_digest")
        projection.approvals[str(payload["approval"]["plan_digest"])] = dict(
            payload["approval"]
        )
    elif event_type == "WAIVER_RECORDED":
        verify_digest(dict(payload["waiver"]), "waiver_digest")
        consumer_id = str(payload["waiver"]["consumer_id"])
        consumer = projection.consumers[consumer_id]
        current = ConsumerDisposition(str(consumer["disposition"]))
        require_consumer_transition(current, ConsumerDisposition.WAIVED)
        consumer["disposition"] = ConsumerDisposition.WAIVED
        projection.waivers[consumer_id] = dict(payload["waiver"])
    elif event_type == "NATIVE_IDENTITY_CLAIMED":
        pass
    elif event_type == "MIGRATION_STARTED":
        require_campaign_transition(projection.state, CampaignState.MIGRATING)
        projection.state = CampaignState.MIGRATING
    elif event_type == "CONSUMER_DISPOSITION_CHANGED":
        consumer = projection.consumers[str(payload["consumer_id"])]
        current = ConsumerDisposition(str(consumer["disposition"]))
        requested = ConsumerDisposition(str(payload["disposition"]))
        if requested in {
            ConsumerDisposition.VALIDATED,
            ConsumerDisposition.REMOVED,
            ConsumerDisposition.NOT_APPLICABLE,
            ConsumerDisposition.WAIVED,
        }:
            raise Refusal(
                RefusalCode.POLICY_ILLEGAL_CONSUMER_TRANSITION,
                "This closure disposition requires its dedicated evidence event.",
            )
        require_consumer_transition(current, requested)
        consumer["disposition"] = requested
        if requested == ConsumerDisposition.CHANGE_PROPOSED:
            required = {"plan_digest", "source_version", "approved_targets"}
            if not required.issubset(payload):
                raise Refusal(
                    RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                    "A proposed change must bind plan, source, and targets.",
                )
            consumer.update(
                {
                    "plan_digest": payload["plan_digest"],
                    "source_version": payload["source_version"],
                    "approved_targets": list(payload["approved_targets"]),
                }
            )
    elif event_type == "RECEIPT_ACCEPTED":
        consumer = projection.consumers[str(payload["consumer_id"])]
        current = ConsumerDisposition(str(consumer["disposition"]))
        require_consumer_transition(current, ConsumerDisposition.VALIDATED)
        receipt = dict(payload["receipt"])
        verify_digest(receipt, "receipt_digest")
        consumer["disposition"] = ConsumerDisposition.VALIDATED
        consumer["receipt_digest"] = receipt["receipt_digest"]
        consumer["receipt"] = receipt
        projection.receipt_digests.append(str(receipt["receipt_digest"]))
    elif event_type == "RECONCILIATION_RECORDED":
        require_campaign_transition(projection.state, CampaignState.RECONCILING)
        projection.state = CampaignState.RECONCILING
        observed_consumers = payload.get("consumers") or []
        for observed in observed_consumers:
            consumer_id = str(observed["id"])
            if consumer_id not in projection.consumers:
                projection.consumers[consumer_id] = {
                    "id": consumer_id,
                    "disposition": ConsumerDisposition(str(observed["disposition"])),
                    "receipt_digest": None,
                }
        projection.current_consumer_ids = sorted(
            str(item) for item in payload["consumer_ids"]
        )
        projection.evidence_envelope = dict(payload["evidence_envelope"])
        projection.snapshot_digests.append(str(payload["snapshot_digest"]))
        projection.reconciliations.append(dict(payload.get("comparison") or {}))
        projection.reconciled = True
    elif event_type == "PUBLICATION_RECORDED":
        publication = dict(payload["publication"])
        required = {
            "logical_key",
            "urn",
            "content_digest",
            "published_manifest_digest",
            "lifecycle_digest_before",
            "readback_verified",
        }
        if (
            set(publication) != required
            or publication["readback_verified"] is not False
        ):
            raise Refusal(
                RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                "A publication record must contain the exact unverified write receipt.",
            )
        if projection.publication is not None:
            if publication["logical_key"] != projection.publication["logical_key"]:
                raise Refusal(
                    RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                    "A campaign publication cannot change logical identity.",
                )
            if publication["urn"] != projection.publication["urn"]:
                raise Refusal(
                    RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                    "A campaign publication cannot move to another DataHub entity.",
                )
        projection.publication = publication
    elif event_type == "PUBLICATION_VERIFIED":
        if projection.publication is None:
            raise Refusal(
                RefusalCode.INTEGRITY_EVENT_SEQUENCE_INVALID,
                "Publication read-back cannot precede publication.",
            )
        required = {
            "urn",
            "content_digest",
            "lifecycle_digest_after",
            "readback_artifact_id",
            "verified_at",
        }
        if set(payload) != required:
            raise Refusal(
                RefusalCode.INTEGRITY_DIGEST_MISMATCH,
                "A publication verification payload has unexpected fields.",
            )
        if (
            payload["urn"] != projection.publication["urn"]
            or payload["content_digest"] != projection.publication["content_digest"]
            or payload["lifecycle_digest_after"]
            != projection.publication["lifecycle_digest_before"]
        ):
            raise Refusal(
                RefusalCode.EVIDENCE_PUBLICATION_MISMATCH,
                "Publication read-back or target lifecycle did not match "
                "the write receipt.",
            )
        projection.publication = {
            **projection.publication,
            "readback_verified": True,
            "readback_artifact_id": payload["readback_artifact_id"],
            "verified_at": payload["verified_at"],
            "lifecycle_digest_after": payload["lifecycle_digest_after"],
        }
    elif event_type == "POLICY_EVALUATED":
        require_bound_inputs(
            recorded=projection.input_digests,
            current=dict(payload["input_digests"]),
        )
        result = _policy_result(
            projection,
            evaluated_at=str(event["occurred_at"]),
        )
        observed_codes = sorted(item["code"] for item in result.blockers)
        if (
            payload["decision"] != result.decision
            or sorted(payload["blocker_codes"]) != observed_codes
        ):
            raise Refusal(
                RefusalCode.POLICY_EVENT_DECISION_MISMATCH,
                "The recorded decision differs from deterministic policy.",
            )
        requested_state = (
            CampaignState.READY
            if result.decision == Decision.READY_TO_RETIRE
            else CampaignState.BLOCKED
        )
        require_campaign_transition(projection.state, requested_state)
        projection.state = requested_state
        projection.last_policy_result = result
    elif event_type == "CAMPAIGN_BLOCKED":
        require_campaign_transition(projection.state, CampaignState.BLOCKED)
        projection.state = CampaignState.BLOCKED
    elif event_type == "CAMPAIGN_RESUMED":
        requested_state = CampaignState(str(payload["state"]))
        require_campaign_transition(projection.state, requested_state)
        projection.state = requested_state
    elif event_type == "CAMPAIGN_RETIRED":
        require_campaign_transition(projection.state, CampaignState.RETIRED)
        projection.state = CampaignState.RETIRED
    else:
        raise Refusal(
            RefusalCode.INTEGRITY_DIGEST_MISMATCH,
            "The event type is not understood by this projector.",
            {"event_type": event_type},
        )
    projection.events.append(event)
    projection.generated_at = str(event["occurred_at"])


def project_events(events: Sequence[Mapping[str, Any]]) -> CampaignProjection:
    """Rebuild campaign state exclusively from the immutable event stream."""

    validated = validate_event_stream(events)
    if validated[0]["event_type"] != "CAMPAIGN_CREATED":
        raise Refusal(
            RefusalCode.INTEGRITY_EVENT_SEQUENCE_INVALID,
            "The first event must create the campaign.",
        )
    projection = _created_projection(validated[0])
    for event in validated[1:]:
        if event["campaign_id"] != projection.campaign_id:
            raise Refusal(
                RefusalCode.INTEGRITY_EVENT_CHAIN_MISMATCH,
                "An event belongs to another campaign.",
            )
        _apply_event(projection, event)
    return projection


def manifest_from_projection(projection: CampaignProjection) -> dict[str, Any]:
    """Build the single canonical manifest consumed by every surface."""

    result = _policy_result(projection)
    review_requirements = [
        {
            key: requirement[key]
            for key in ("code", "message", "consumer_id")
            if key in requirement
        }
        for requirement in result.review_requirements
    ]
    review_fields = (
        {"review_requirements": review_requirements} if review_requirements else {}
    )
    manifest = with_digest(
        {
            "schema_version": "1.0.0",
            "campaign": {
                "id": projection.campaign_id,
                "name": projection.name,
                "state": projection.state,
            },
            "specification_digest": projection.specification_digest,
            "policy": {
                "id": projection.policy["id"],
                "version": projection.policy["version"],
                "requires_live_evidence": projection.policy["requires_live_evidence"],
            },
            "target": projection.target,
            "replacement": projection.replacement,
            "evidence_envelope": projection.evidence_envelope or {},
            "snapshot_digests": projection.snapshot_digests,
            "consumers": [
                {
                    "id": consumer["id"],
                    "disposition": consumer["disposition"],
                    "receipt_digest": consumer["receipt_digest"],
                }
                for consumer in sorted(
                    projection.consumers.values(), key=lambda item: str(item["id"])
                )
            ],
            "receipt_digests": sorted(projection.receipt_digests),
            "blockers": [
                {"code": blocker["code"], "message": blocker["message"]}
                for blocker in result.blockers
            ],
            **review_fields,
            "transition_history": [
                {
                    "sequence": event["sequence"],
                    "event_type": event["event_type"],
                    "event_digest": event["event_digest"],
                }
                for event in projection.events
            ],
            "publication": projection.publication,
            "decision": result.decision,
            "generated_at": projection.generated_at,
        },
        "manifest_digest",
    )
    validate_schema(
        "campaign-manifest",
        manifest,
        refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
    )
    verify_digest(manifest, "manifest_digest")
    return manifest


def event_stream_digest(events: Sequence[Mapping[str, Any]]) -> str:
    """Return the digest of a validated canonical event stream."""

    validated = validate_event_stream(events)
    return digest_json([canonical_json(event) for event in validated])
