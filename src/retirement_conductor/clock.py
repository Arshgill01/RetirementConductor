"""Injected trusted-clock checks for freshness and expiration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from retirement_conductor.errors import Refusal
from retirement_conductor.vocabulary import RefusalCode


def parse_timestamp(value: str) -> datetime:
    """Parse one timezone-aware RFC-3339 timestamp."""

    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise Refusal(
            RefusalCode.RUNTIME_CLOCK_INVALID,
            "A timestamp is not valid RFC-3339.",
        ) from exc
    if parsed.tzinfo is None:
        raise Refusal(
            RefusalCode.RUNTIME_CLOCK_INVALID,
            "A timestamp does not include a trusted timezone.",
        )
    return parsed.astimezone(UTC)


def validate_trusted_clock(
    *,
    now: datetime,
    observed_at: datetime | None = None,
    last_trusted_at: datetime | None = None,
    expires_at: datetime | None = None,
    source_clock_at: datetime | None = None,
    maximum_future_skew_seconds: int = 30,
    maximum_source_skew_seconds: int = 300,
    expiration_code: RefusalCode = RefusalCode.EVIDENCE_RECEIPT_EXPIRED,
) -> None:
    """Refuse rollback, future evidence, excessive skew, and expiration."""

    trusted_now = now.astimezone(UTC)
    if last_trusted_at is not None and trusted_now < last_trusted_at.astimezone(UTC):
        raise Refusal(
            RefusalCode.RUNTIME_CLOCK_ROLLBACK,
            "The trusted clock moved backward.",
        )
    if observed_at is not None and observed_at.astimezone(
        UTC
    ) > trusted_now + timedelta(seconds=maximum_future_skew_seconds):
        raise Refusal(
            RefusalCode.RUNTIME_CLOCK_FUTURE,
            "Evidence was captured too far in the future.",
        )
    if source_clock_at is not None:
        skew = abs((source_clock_at.astimezone(UTC) - trusted_now).total_seconds())
        if skew > maximum_source_skew_seconds:
            raise Refusal(
                RefusalCode.RUNTIME_CLOCK_SKEW,
                "The source and trusted clocks differ beyond policy.",
                {"observed_skew_seconds": int(skew)},
            )
    if expires_at is not None and trusted_now >= expires_at.astimezone(UTC):
        raise Refusal(
            expiration_code,
            "The evidence expired at or before the trusted evaluation time.",
        )
