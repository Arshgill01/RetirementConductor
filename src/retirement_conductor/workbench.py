"""Focused operator projection for the Retirement Workbench."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from retirement_conductor.operator import build_campaign_view
from retirement_conductor.vocabulary import Decision

_STAGES: tuple[tuple[str, str], ...] = (
    ("inventory", "Inventory"),
    ("plan", "Plan"),
    ("authorize", "Authorize"),
    ("apply", "Apply"),
    ("validate", "Validate"),
    ("reconcile", "Reconcile"),
    ("lease", "Lease"),
)

_STAGE_EVENTS: dict[str, frozenset[str]] = {
    "inventory": frozenset({"INVENTORY_RECORDED", "INVENTORY_EXTENDED"}),
    "plan": frozenset({"CONSUMER_DISPOSITION_CHANGED"}),
    "authorize": frozenset({"APPROVAL_RECORDED"}),
    "apply": frozenset({"MIGRATION_STARTED"}),
    "validate": frozenset({"RECEIPT_ACCEPTED"}),
    "reconcile": frozenset({"RECONCILIATION_RECORDED"}),
    "lease": frozenset(),
}


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: object) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return list(value)
    return []


def _event_types(events: Sequence[Mapping[str, Any]]) -> set[str]:
    return {str(event.get("event_type") or "") for event in events}


def _has_plan(events: Sequence[Mapping[str, Any]]) -> bool:
    return any(
        event.get("event_type") == "CONSUMER_DISPOSITION_CHANGED"
        and _mapping(event.get("payload")).get("disposition") == "CHANGE_PROPOSED"
        for event in events
    )


def _ready_reversed(events: Sequence[Mapping[str, Any]]) -> bool:
    decisions = [
        str(_mapping(event.get("payload")).get("decision") or "")
        for event in events
        if event.get("event_type") == "POLICY_EVALUATED"
    ]
    return Decision.READY_TO_RETIRE in decisions and decisions[-1:] == [Decision.UNSAFE]


def _latest_added_consumers(events: Sequence[Mapping[str, Any]]) -> list[str]:
    for event in reversed(events):
        if event.get("event_type") != "RECONCILIATION_RECORDED":
            continue
        comparison = _mapping(_mapping(event.get("payload")).get("comparison"))
        return sorted(str(item) for item in _sequence(comparison.get("added")))
    return []


def _last_event_time(
    events: Sequence[Mapping[str, Any]],
    accepted_types: frozenset[str],
) -> str | None:
    for event in reversed(events):
        if str(event.get("event_type") or "") in accepted_types:
            value = event.get("occurred_at")
            return str(value) if value else None
    return None


def _current_stage(
    *,
    view: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
) -> str:
    types = _event_types(events)
    decision = str(view["decision"])
    added = _latest_added_consumers(events)
    if added and decision == Decision.UNSAFE:
        return "reconcile"
    if "INVENTORY_RECORDED" not in types:
        return "inventory"
    if not _has_plan(events):
        return "plan"
    if "APPROVAL_RECORDED" not in types:
        return "authorize"
    if "MIGRATION_STARTED" not in types:
        return "apply"
    if "RECEIPT_ACCEPTED" not in types:
        return "validate"
    if "RECONCILIATION_RECORDED" not in types:
        return "reconcile"
    return "lease"


def _stages(
    *,
    view: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    types = _event_types(events)
    current = _current_stage(view=view, events=events)
    current_index = next(
        index for index, (key, _label) in enumerate(_STAGES) if key == current
    )
    reversed_readiness = _ready_reversed(events)
    result: list[dict[str, Any]] = []
    for index, (key, label) in enumerate(_STAGES):
        completed = bool(types & _STAGE_EVENTS[key])
        if key == "plan":
            completed = _has_plan(events)
        if key == "lease":
            completed = str(view["decision"]) == Decision.READY_TO_RETIRE
        if key == current:
            status = "current"
        elif key == "lease" and reversed_readiness:
            status = "invalidated"
        elif completed or index < current_index:
            status = "complete"
        else:
            status = "pending"
        result.append(
            {
                "key": key,
                "label": label,
                "number": f"{index + 1:02d}",
                "status": status,
                "occurred_at": _last_event_time(events, _STAGE_EVENTS[key]),
            }
        )
    return result


def _summary(
    *,
    view: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    decision = str(view["decision"])
    added = _latest_added_consumers(events)
    blockers = [_mapping(item) for item in _sequence(view.get("blockers"))]
    primary = next(
        (
            blocker
            for blocker in blockers
            if blocker.get("code") == "RECONCILIATION_NEW_CONSUMER"
        ),
        blockers[0] if blockers else {},
    )
    if decision == Decision.UNSAFE and added:
        headline = "A new consumer changed the answer."
        cause = str(primary.get("message") or "Fresh evidence added a consumer.")
    elif decision == Decision.READY_TO_RETIRE:
        headline = "The evidence supports retirement."
        cause = "Every known consumer is closed within the recorded evidence envelope."
    elif decision == Decision.REVIEW_REQUIRED:
        headline = "A human decision is still required."
        cause = str(primary.get("message") or "A review requirement remains open.")
    else:
        headline = "The campaign cannot move forward yet."
        cause = str(primary.get("message") or view.get("decision_label") or "Blocked.")
    return {"headline": headline, "cause": cause}


def _primary_action(
    *,
    view: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    current = _current_stage(view=view, events=events)
    if current == "inventory":
        return {
            "kind": "runtime",
            "operation": "inventory",
            "label": "Inventory consumers",
            "description": "Query the declared DataHub evidence envelope.",
        }
    if current == "reconcile" and not _latest_added_consumers(events):
        return {
            "kind": "runtime",
            "operation": "reconcile",
            "label": "Reconcile evidence",
            "description": "Refresh DataHub and compare the complete observed set.",
        }
    if _latest_added_consumers(events):
        return {
            "kind": "navigate",
            "view": "consumers",
            "label": "Review new consumer",
            "description": "Resolve the newly observed consumer before another lease.",
        }
    return {
        "kind": "navigate",
        "view": "evidence",
        "label": "Inspect evidence",
        "description": str(view.get("next_action") or "Inspect canonical evidence."),
    }


def build_workbench_view(
    manifest: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    *,
    actions_enabled: bool,
) -> dict[str, Any]:
    """Validate canonical inputs and build one deliberately narrow UI projection."""

    view = build_campaign_view(manifest)
    validated_events = [dict(event) for event in events]
    expected_history = [
        str(_mapping(item).get("event_digest") or "")
        for item in _sequence(manifest.get("transition_history"))
    ]
    observed_history = [str(event.get("event_digest") or "") for event in events]
    if expected_history != observed_history:
        raise ValueError(
            "Workbench events do not match the canonical manifest history."
        )

    added = set(_latest_added_consumers(validated_events))
    consumers = []
    for consumer_value in _sequence(view["consumers"]):
        consumer = _mapping(consumer_value)
        consumers.append({**consumer, "newly_observed": consumer.get("id") in added})

    change_paths: list[str] = []
    receipt: dict[str, Any] | None = None
    for event in validated_events:
        payload = _mapping(event.get("payload"))
        if event.get("event_type") == "CONSUMER_DISPOSITION_CHANGED":
            for path in _sequence(payload.get("approved_targets")):
                text = str(path)
                if text not in change_paths:
                    change_paths.append(text)
        elif event.get("event_type") == "RECEIPT_ACCEPTED":
            raw_receipt = _mapping(payload.get("receipt"))
            receipt = {
                "consumer_id": str(payload.get("consumer_id") or "unknown"),
                "accepted_at": str(payload.get("accepted_at") or "not recorded"),
                "digest": str(raw_receipt.get("receipt_digest") or "not recorded"),
                "adapter": str(
                    _mapping(raw_receipt.get("adapter")).get("name") or "unknown"
                ),
                "result": str(
                    _mapping(raw_receipt.get("apply")).get("result") or "unknown"
                ),
            }

    action = _primary_action(view=view, events=validated_events)
    action["enabled"] = actions_enabled if action["kind"] == "runtime" else True
    return {
        "schema_version": "1.0.0",
        "mode": "live-local" if actions_enabled else "read-only",
        "campaign": view["campaign"],
        "target": view["target"],
        "replacement": view["replacement"],
        "decision": view["decision"],
        "decision_label": view["decision_label"],
        "summary": _summary(view=view, events=validated_events),
        "stages": _stages(view=view, events=validated_events),
        "primary_action": action,
        "consumers": consumers,
        "new_consumer_ids": sorted(added),
        "change": {"paths": change_paths, "receipt": receipt},
        "evidence": view["evidence"],
        "publication": view["publication"],
        "blockers": view["blockers"],
        "review_requirements": view["review_requirements"],
        "activity": [
            {
                "sequence": event.get("sequence"),
                "event_type": str(event.get("event_type") or "UNKNOWN_EVENT"),
                "occurred_at": str(event.get("occurred_at") or "not recorded"),
                "event_digest": str(event.get("event_digest") or ""),
            }
            for event in reversed(validated_events)
        ],
        "generated_at": view["generated_at"],
        "manifest_digest": view["manifest_digest"],
    }
