from __future__ import annotations

from copy import deepcopy

from retirement_conductor.policy import default_policy, evaluate_policy
from retirement_conductor.vocabulary import Decision


def live_envelope() -> dict[str, object]:
    return {
        "mode": "live",
        "sources": [
            {
                "id": "datahub",
                "required": True,
                "status": "COMPLETE",
            }
        ],
    }


def validated_consumer() -> dict[str, str | None]:
    return {
        "id": "consumer-one",
        "disposition": "VALIDATED",
        "receipt_digest": f"sha256:{'1' * 64}",
    }


def evaluate(
    *,
    envelope: dict[str, object] | None = None,
    consumers: list[dict[str, str | None]] | None = None,
    current: list[str] | None = None,
    reconciled: bool = True,
    policy: dict[str, object] | None = None,
    reviews: list[dict[str, str]] | None = None,
) -> Decision:
    selected_consumers = consumers or [validated_consumer()]
    return evaluate_policy(
        evidence_envelope=envelope or live_envelope(),
        consumers=selected_consumers,
        inventory_consumer_ids=["consumer-one"],
        current_consumer_ids=current or ["consumer-one"],
        reconciled=reconciled,
        policy=policy,
        semantic_reviews=reviews or [],
    ).decision


def test_policy_produces_exactly_four_decisions() -> None:
    assert evaluate() == Decision.READY_TO_RETIRE
    assert (
        evaluate(reviews=[{"code": "SEMANTIC_REVIEW", "message": "review"}])
        == Decision.REVIEW_REQUIRED
    )
    fixture = live_envelope()
    fixture["mode"] = "fixture"
    assert evaluate(envelope=fixture) == Decision.BLOCKED
    unsafe = validated_consumer()
    unsafe["disposition"] = "FAILED"
    assert evaluate(consumers=[unsafe]) == Decision.UNSAFE


def test_late_consumer_reopens_ready_evaluation_as_unsafe() -> None:
    assert evaluate() == Decision.READY_TO_RETIRE
    assert evaluate(current=["consumer-one", "consumer-late"]) == Decision.UNSAFE


def test_default_waiver_blocks_but_permitted_waiver_remains_visible() -> None:
    waived = validated_consumer()
    waived["disposition"] = "WAIVED"
    assert evaluate(consumers=[waived]) == Decision.BLOCKED

    policy = deepcopy(default_policy())
    policy["allow_waivers"] = True
    assert evaluate(consumers=[waived], policy=policy) == Decision.REVIEW_REQUIRED
    policy["waivers_satisfy_closure"] = True
    assert evaluate(consumers=[waived], policy=policy) == Decision.READY_TO_RETIRE


def test_empty_inventory_and_missing_reconciliation_block() -> None:
    empty = evaluate_policy(
        evidence_envelope=live_envelope(),
        consumers=[],
        inventory_consumer_ids=[],
        current_consumer_ids=[],
        reconciled=False,
    )

    assert empty.decision == Decision.BLOCKED
    assert {item["code"] for item in empty.blockers} >= {
        "EVIDENCE_EMPTY_RESULT_UNPROVEN",
        "RECONCILIATION_REQUIRED",
    }


def test_bound_input_drift_blocks() -> None:
    result = evaluate_policy(
        evidence_envelope=live_envelope(),
        consumers=[validated_consumer()],
        inventory_consumer_ids=["consumer-one"],
        current_consumer_ids=["consumer-one"],
        reconciled=True,
        bound_inputs_match=False,
    )

    assert result.decision == Decision.BLOCKED
    assert result.blockers[0]["code"] == "POLICY_INPUT_DRIFT"
