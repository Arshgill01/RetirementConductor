from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from retirement_conductor.errors import Refusal
from retirement_conductor.events import (
    CampaignProjection,
    build_event,
    manifest_from_projection,
    project_events,
)
from retirement_conductor.policy import default_policy
from retirement_conductor.vocabulary import CampaignState

ROOT = Path(__file__).resolve().parents[2]


def fixture_events() -> list[dict[str, Any]]:
    fixture = json.loads(
        (ROOT / "fixtures/campaigns/blocked/events.json").read_text(encoding="utf-8")
    )
    return cast(list[dict[str, Any]], fixture["events"])


def test_wrong_event_sequence_refuses() -> None:
    events = fixture_events()
    events[1]["sequence"] = 4

    with pytest.raises(Refusal, match="INTEGRITY_EVENT_SEQUENCE_INVALID"):
        project_events(events)


def test_wrong_event_predecessor_refuses() -> None:
    events = fixture_events()
    prior = events[:2]
    wrong = build_event(
        campaign_id=str(events[0]["campaign_id"]),
        sequence=3,
        event_type="CAMPAIGN_BLOCKED",
        occurred_at="2026-01-02T00:00:00Z",
        idempotency_key="wrong-chain",
        previous_event_digest=f"sha256:{'0' * 64}",
        payload={"reason": "wrong predecessor"},
    )

    with pytest.raises(Refusal, match="INTEGRITY_EVENT_CHAIN_MISMATCH"):
        project_events([*prior, wrong])


def test_recorded_policy_cannot_claim_another_decision() -> None:
    events = fixture_events()
    prior = events[:2]
    false_ready = build_event(
        campaign_id=str(events[0]["campaign_id"]),
        sequence=3,
        event_type="POLICY_EVALUATED",
        occurred_at="2026-01-02T00:00:00Z",
        idempotency_key="false-ready",
        previous_event_digest=str(prior[-1]["event_digest"]),
        payload={
            "input_digests": events[0]["payload"]["input_digests"],
            "decision": "READY_TO_RETIRE",
            "blocker_codes": [],
        },
    )

    with pytest.raises(Refusal, match="POLICY_EVENT_DECISION_MISMATCH"):
        project_events([*prior, false_ready])


def test_review_requirement_is_visible_in_canonical_manifest() -> None:
    policy = default_policy()
    policy["allow_waivers"] = True
    projection = CampaignProjection(
        campaign_id="review-campaign",
        name="Review one bounded waiver",
        state=CampaignState.RECONCILING,
        specification_digest=f"sha256:{'1' * 64}",
        target={"field": "legacy_status"},
        replacement={"field": "order_status"},
        policy=policy,
        input_digests={},
        evidence_envelope={
            "mode": "live",
            "sources": [
                {
                    "id": "datahub",
                    "required": True,
                    "status": "COMPLETE",
                }
            ],
        },
        inventory_consumer_ids=["consumer-one"],
        current_consumer_ids=["consumer-one"],
        consumers={
            "consumer-one": {
                "id": "consumer-one",
                "disposition": "WAIVED",
                "receipt_digest": None,
            }
        },
        reconciled=True,
        generated_at="2026-01-01T00:00:00Z",
    )

    manifest = manifest_from_projection(projection)

    assert manifest["decision"] == "REVIEW_REQUIRED"
    assert manifest["review_requirements"] == [
        {
            "code": "POLICY_WAIVER_REVIEW",
            "consumer_id": "consumer-one",
            "message": "An allowed waiver remains visibly reviewable.",
        }
    ]
