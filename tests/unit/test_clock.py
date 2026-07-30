from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from retirement_conductor.clock import parse_timestamp, validate_trusted_clock
from retirement_conductor.errors import Refusal

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_clock_accepts_observation_inside_policy() -> None:
    validate_trusted_clock(
        now=NOW,
        observed_at=NOW - timedelta(seconds=1),
        last_trusted_at=NOW - timedelta(seconds=2),
        expires_at=NOW + timedelta(seconds=1),
        source_clock_at=NOW + timedelta(seconds=10),
    )


@pytest.mark.parametrize(
    ("arguments", "code"),
    [
        (
            {"last_trusted_at": NOW + timedelta(seconds=1)},
            "RUNTIME_CLOCK_ROLLBACK",
        ),
        (
            {"observed_at": NOW + timedelta(seconds=31)},
            "RUNTIME_CLOCK_FUTURE",
        ),
        (
            {"source_clock_at": NOW + timedelta(seconds=301)},
            "RUNTIME_CLOCK_SKEW",
        ),
        (
            {"expires_at": NOW},
            "EVIDENCE_RECEIPT_EXPIRED",
        ),
    ],
)
def test_clock_boundary_failures_refuse(
    arguments: dict[str, Any],
    code: str,
) -> None:
    with pytest.raises(Refusal, match=code):
        validate_trusted_clock(now=NOW, **arguments)


@pytest.mark.parametrize("value", ["not-a-time", "2026-01-01T12:00:00"])
def test_invalid_or_naive_timestamp_refuses(value: str) -> None:
    with pytest.raises(Refusal, match="RUNTIME_CLOCK_INVALID"):
        parse_timestamp(value)
