from __future__ import annotations

import pytest

from retirement_conductor.errors import Refusal
from retirement_conductor.state import (
    CAMPAIGN_TRANSITIONS,
    CONSUMER_TRANSITIONS,
    require_campaign_transition,
    require_consumer_transition,
)
from retirement_conductor.vocabulary import CampaignState, ConsumerDisposition


def test_every_declared_campaign_transition_is_legal() -> None:
    for current, requested_states in CAMPAIGN_TRANSITIONS.items():
        for requested in requested_states:
            require_campaign_transition(current, requested)


def test_every_undeclared_campaign_transition_refuses() -> None:
    for current, requested_states in CAMPAIGN_TRANSITIONS.items():
        for requested in CampaignState:
            if requested in requested_states:
                continue
            with pytest.raises(Refusal, match="POLICY_ILLEGAL_CAMPAIGN_TRANSITION"):
                require_campaign_transition(current, requested)


def test_every_declared_consumer_transition_is_legal() -> None:
    for current, requested_states in CONSUMER_TRANSITIONS.items():
        for requested in requested_states:
            require_consumer_transition(current, requested)


def test_every_undeclared_consumer_transition_refuses() -> None:
    for current, requested_states in CONSUMER_TRANSITIONS.items():
        for requested in ConsumerDisposition:
            if requested in requested_states:
                continue
            with pytest.raises(Refusal, match="POLICY_ILLEGAL_CONSUMER_TRANSITION"):
                require_consumer_transition(current, requested)
