"""Pure deterministic campaign policy."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from retirement_conductor.vocabulary import (
    ConsumerDisposition,
    Decision,
    EvidenceMode,
    EvidenceStatus,
)

ACCEPTED_DISPOSITIONS = frozenset(
    {
        ConsumerDisposition.VALIDATED,
        ConsumerDisposition.REMOVED,
        ConsumerDisposition.NOT_APPLICABLE,
    }
)
UNSAFE_DISPOSITIONS = frozenset(
    {
        ConsumerDisposition.DISCOVERED,
        ConsumerDisposition.IDENTIFIED,
        ConsumerDisposition.CHANGE_PROPOSED,
        ConsumerDisposition.APPLIED,
        ConsumerDisposition.OPAQUE,
        ConsumerDisposition.STALE,
        ConsumerDisposition.FAILED,
    }
)


@dataclass(frozen=True)
class PolicyResult:
    decision: Decision
    blockers: tuple[dict[str, str], ...]
    review_requirements: tuple[dict[str, str], ...]
    new_consumers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "blockers": list(self.blockers),
            "review_requirements": list(self.review_requirements),
            "new_consumers": list(self.new_consumers),
        }


def default_policy() -> dict[str, Any]:
    """Return the one initial versioned policy."""

    return {
        "id": "default-column-retirement",
        "version": 1,
        "requires_live_evidence": True,
        "require_reconciliation": True,
        "allow_waivers": False,
        "waivers_satisfy_closure": False,
    }


def _entry(code: str, message: str, consumer_id: str | None = None) -> dict[str, str]:
    result = {"code": code, "message": message}
    if consumer_id is not None:
        result["consumer_id"] = consumer_id
    return result


def evaluate_policy(
    *,
    evidence_envelope: Mapping[str, Any] | None,
    consumers: Sequence[Mapping[str, Any]],
    inventory_consumer_ids: Sequence[str],
    current_consumer_ids: Sequence[str],
    reconciled: bool,
    policy: Mapping[str, Any] | None = None,
    bound_inputs_match: bool = True,
    semantic_reviews: Sequence[Mapping[str, str]] = (),
) -> PolicyResult:
    """Evaluate exactly one of the four final decisions."""

    configuration = dict(policy or default_policy())
    blockers: list[dict[str, str]] = []
    unsafe: list[dict[str, str]] = []
    reviews = [dict(item) for item in semantic_reviews]

    if not bound_inputs_match:
        blockers.append(
            _entry(
                "POLICY_INPUT_DRIFT",
                "Policy, validator, or authorization inputs changed.",
            )
        )
    if evidence_envelope is None:
        blockers.append(
            _entry(
                "EVIDENCE_REQUIRED_SOURCE_INCOMPLETE",
                "No evidence envelope exists.",
            )
        )
    else:
        mode = evidence_envelope.get("mode")
        if configuration["requires_live_evidence"] and mode != EvidenceMode.LIVE:
            blockers.append(
                _entry(
                    "EVIDENCE_MODE_NOT_LIVE",
                    "The policy requires live evidence.",
                )
            )
        sources = evidence_envelope.get("sources", [])
        required_sources = [source for source in sources if source.get("required")]
        if not required_sources:
            blockers.append(
                _entry(
                    "EVIDENCE_REQUIRED_SOURCE_INCOMPLETE",
                    "No required evidence source was declared.",
                )
            )
        for source in required_sources:
            if source.get("status") != EvidenceStatus.COMPLETE:
                blockers.append(
                    _entry(
                        "EVIDENCE_REQUIRED_SOURCE_INCOMPLETE",
                        f"Required source {source.get('id', 'unknown')} is incomplete.",
                    )
                )

    if not consumers:
        blockers.append(
            _entry(
                "EVIDENCE_EMPTY_RESULT_UNPROVEN",
                "An empty inventory cannot independently prove absence.",
            )
        )
    for consumer in sorted(consumers, key=lambda item: str(item["id"])):
        consumer_id = str(consumer["id"])
        disposition = ConsumerDisposition(str(consumer["disposition"]))
        if disposition in ACCEPTED_DISPOSITIONS:
            continue
        if disposition == ConsumerDisposition.WAIVED:
            if not configuration["allow_waivers"]:
                blockers.append(
                    _entry(
                        "POLICY_WAIVER_FORBIDDEN",
                        "The active policy does not accept waivers.",
                        consumer_id,
                    )
                )
            elif not configuration["waivers_satisfy_closure"]:
                reviews.append(
                    _entry(
                        "POLICY_WAIVER_REVIEW",
                        "An allowed waiver remains visibly reviewable.",
                        consumer_id,
                    )
                )
            continue
        if disposition == ConsumerDisposition.UNRESOLVED:
            blockers.append(
                _entry(
                    "IDENTITY_NOT_FOUND",
                    "The consumer has no unique native identity.",
                    consumer_id,
                )
            )
            continue
        if disposition in UNSAFE_DISPOSITIONS:
            unsafe.append(
                _entry(
                    f"POLICY_CONSUMER_{disposition.value}",
                    f"Consumer remains {disposition.value.lower()}.",
                    consumer_id,
                )
            )

    new_consumers = tuple(
        sorted(set(current_consumer_ids) - set(inventory_consumer_ids))
    )
    for consumer_id in new_consumers:
        unsafe.append(
            _entry(
                "RECONCILIATION_NEW_CONSUMER",
                "A consumer appeared after the frozen inventory.",
                consumer_id,
            )
        )
    if configuration["require_reconciliation"] and not reconciled:
        blockers.append(
            _entry(
                "RECONCILIATION_REQUIRED",
                "A fresh equivalent reconciliation has not completed.",
            )
        )

    def sort_key(item: dict[str, str]) -> tuple[str, str]:
        return (item["code"], item.get("consumer_id", ""))

    if unsafe:
        decision = Decision.UNSAFE
        blockers.extend(unsafe)
    elif blockers:
        decision = Decision.BLOCKED
    elif reviews:
        decision = Decision.REVIEW_REQUIRED
    else:
        decision = Decision.READY_TO_RETIRE
    return PolicyResult(
        decision=decision,
        blockers=tuple(sorted(blockers, key=sort_key)),
        review_requirements=tuple(sorted(reviews, key=sort_key)),
        new_consumers=new_consumers,
    )
