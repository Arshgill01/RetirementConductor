"""Pure campaign and consumer state machines."""

from __future__ import annotations

from retirement_conductor.errors import Refusal
from retirement_conductor.vocabulary import (
    CampaignState,
    ConsumerDisposition,
    RefusalCode,
)

CAMPAIGN_TRANSITIONS: dict[CampaignState, frozenset[CampaignState]] = {
    CampaignState.PROPOSED: frozenset(
        {CampaignState.INVENTORIED, CampaignState.BLOCKED}
    ),
    CampaignState.INVENTORIED: frozenset(
        {CampaignState.MIGRATING, CampaignState.RECONCILING, CampaignState.BLOCKED}
    ),
    CampaignState.MIGRATING: frozenset(
        {CampaignState.RECONCILING, CampaignState.BLOCKED}
    ),
    CampaignState.RECONCILING: frozenset({CampaignState.READY, CampaignState.BLOCKED}),
    CampaignState.READY: frozenset(
        {
            CampaignState.RETIRED,
            CampaignState.RECONCILING,
            CampaignState.BLOCKED,
        }
    ),
    CampaignState.RETIRED: frozenset(),
    CampaignState.BLOCKED: frozenset(
        {
            CampaignState.INVENTORIED,
            CampaignState.MIGRATING,
            CampaignState.RECONCILING,
            CampaignState.BLOCKED,
        }
    ),
}

CONSUMER_TRANSITIONS: dict[ConsumerDisposition, frozenset[ConsumerDisposition]] = {
    ConsumerDisposition.DISCOVERED: frozenset(
        {
            ConsumerDisposition.IDENTIFIED,
            ConsumerDisposition.OPAQUE,
            ConsumerDisposition.UNRESOLVED,
            ConsumerDisposition.NOT_APPLICABLE,
        }
    ),
    ConsumerDisposition.IDENTIFIED: frozenset(
        {
            ConsumerDisposition.CHANGE_PROPOSED,
            ConsumerDisposition.REMOVED,
            ConsumerDisposition.NOT_APPLICABLE,
            ConsumerDisposition.WAIVED,
            ConsumerDisposition.STALE,
        }
    ),
    ConsumerDisposition.CHANGE_PROPOSED: frozenset(
        {
            ConsumerDisposition.APPLIED,
            ConsumerDisposition.FAILED,
            ConsumerDisposition.STALE,
        }
    ),
    ConsumerDisposition.APPLIED: frozenset(
        {
            ConsumerDisposition.VALIDATED,
            ConsumerDisposition.FAILED,
            ConsumerDisposition.STALE,
        }
    ),
    ConsumerDisposition.VALIDATED: frozenset({ConsumerDisposition.STALE}),
    ConsumerDisposition.REMOVED: frozenset({ConsumerDisposition.STALE}),
    ConsumerDisposition.NOT_APPLICABLE: frozenset({ConsumerDisposition.STALE}),
    ConsumerDisposition.WAIVED: frozenset(
        {ConsumerDisposition.IDENTIFIED, ConsumerDisposition.STALE}
    ),
    ConsumerDisposition.OPAQUE: frozenset(
        {
            ConsumerDisposition.IDENTIFIED,
            ConsumerDisposition.NOT_APPLICABLE,
            ConsumerDisposition.WAIVED,
        }
    ),
    ConsumerDisposition.UNRESOLVED: frozenset(
        {
            ConsumerDisposition.IDENTIFIED,
            ConsumerDisposition.NOT_APPLICABLE,
            ConsumerDisposition.WAIVED,
        }
    ),
    ConsumerDisposition.STALE: frozenset(
        {
            ConsumerDisposition.IDENTIFIED,
            ConsumerDisposition.CHANGE_PROPOSED,
            ConsumerDisposition.FAILED,
        }
    ),
    ConsumerDisposition.FAILED: frozenset(
        {
            ConsumerDisposition.CHANGE_PROPOSED,
            ConsumerDisposition.STALE,
            ConsumerDisposition.WAIVED,
        }
    ),
}


def require_campaign_transition(
    current: CampaignState,
    requested: CampaignState,
) -> None:
    """Refuse an illegal campaign transition without side effects."""

    if requested not in CAMPAIGN_TRANSITIONS[current]:
        raise Refusal(
            RefusalCode.POLICY_ILLEGAL_CAMPAIGN_TRANSITION,
            "The requested campaign transition is not legal.",
            {"from": current, "to": requested},
        )


def require_consumer_transition(
    current: ConsumerDisposition,
    requested: ConsumerDisposition,
) -> None:
    """Refuse an illegal consumer transition without side effects."""

    if requested not in CONSUMER_TRANSITIONS[current]:
        raise Refusal(
            RefusalCode.POLICY_ILLEGAL_CONSUMER_TRANSITION,
            "The requested consumer transition is not legal.",
            {"from": current, "to": requested},
        )
