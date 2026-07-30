"""Strict approval, waiver, receipt, and executable-input validation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from retirement_conductor.canonical import verify_digest
from retirement_conductor.clock import parse_timestamp, validate_trusted_clock
from retirement_conductor.errors import Refusal
from retirement_conductor.schemas import validate_schema
from retirement_conductor.vocabulary import (
    ConsumerDisposition,
    EvidenceMode,
    RefusalCode,
)


def validate_approval(
    approval: Mapping[str, Any] | None,
    *,
    campaign_id: str,
    plan_digest: str,
    source_version: str,
    targets: Sequence[str],
    required_scope: Sequence[str],
    authorization_digest: str,
    trusted_now: datetime,
    last_trusted_at: datetime | None = None,
) -> None:
    """Require an exact, unexpired, digest-bound apply approval."""

    if approval is None:
        raise Refusal(
            RefusalCode.AUTH_APPROVAL_MISSING,
            "Apply requires an explicit target-bound approval.",
        )
    value = dict(approval)
    validate_schema(
        "approval",
        value,
        refusal_code=RefusalCode.AUTH_APPROVAL_WRONG_SCOPE,
    )
    verify_digest(value, "approval_digest")
    if value["campaign_id"] != campaign_id:
        raise Refusal(
            RefusalCode.AUTH_APPROVAL_WRONG_CAMPAIGN,
            "The approval belongs to another campaign.",
        )
    if value["plan_digest"] != plan_digest:
        raise Refusal(
            RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
            "The approval is not bound to this plan.",
        )
    if value["source_version"] != source_version:
        raise Refusal(
            RefusalCode.AUTH_APPROVAL_WRONG_SOURCE,
            "The approval is bound to another source version.",
        )
    if sorted(value["targets"]) != sorted(targets):
        raise Refusal(
            RefusalCode.AUTH_APPROVAL_WRONG_SCOPE,
            "The approval target set does not exactly match the plan.",
        )
    if not set(required_scope).issubset(value["scope"]):
        raise Refusal(
            RefusalCode.AUTH_APPROVAL_WRONG_SCOPE,
            "The approval does not include every required capability.",
        )
    if value["authorization_digest"] != authorization_digest:
        raise Refusal(
            RefusalCode.AUTH_APPROVAL_WRONG_SCOPE,
            "The approval authorization configuration changed.",
        )
    validate_trusted_clock(
        now=trusted_now,
        observed_at=parse_timestamp(value["authorized_at"]),
        last_trusted_at=last_trusted_at,
        expires_at=parse_timestamp(value["expires_at"]),
        expiration_code=RefusalCode.AUTH_APPROVAL_EXPIRED,
    )


def validate_waiver(
    waiver: Mapping[str, Any],
    *,
    campaign_id: str,
    consumer_id: str,
    required_scope: Sequence[str],
    trusted_now: datetime,
) -> None:
    """Validate a visible, bounded waiver without treating it as validation."""

    value = dict(waiver)
    validate_schema(
        "waiver",
        value,
        refusal_code=RefusalCode.AUTH_WAIVER_INVALID,
    )
    verify_digest(value, "waiver_digest")
    if (
        value["campaign_id"] != campaign_id
        or value["consumer_id"] != consumer_id
        or not set(required_scope).issubset(value["scope"])
    ):
        raise Refusal(
            RefusalCode.AUTH_WAIVER_INVALID,
            "The waiver campaign, consumer, or scope does not match.",
        )
    validate_trusted_clock(
        now=trusted_now,
        observed_at=parse_timestamp(value["authorized_at"]),
        expires_at=parse_timestamp(value["expires_at"]),
        expiration_code=RefusalCode.AUTH_WAIVER_EXPIRED,
    )


def validate_consumer_receipt(
    receipt: Mapping[str, Any],
    *,
    campaign_id: str,
    consumer_id: str,
    plan_digest: str,
    source_version: str,
    approved_targets: Sequence[str],
    require_live: bool,
    trusted_now: datetime,
) -> None:
    """Accept only an intact source-native receipt bound to exact inputs."""

    value = dict(receipt)
    validate_schema(
        "consumer-receipt",
        value,
        refusal_code=RefusalCode.INTEGRITY_DIGEST_MISMATCH,
    )
    verify_digest(value, "receipt_digest")
    if value["campaign_id"] != campaign_id or value["consumer_id"] != consumer_id:
        raise Refusal(
            RefusalCode.IDENTITY_NOT_FOUND,
            "The receipt does not identify the expected campaign consumer.",
        )
    if require_live and value["adapter"]["mode"] != EvidenceMode.LIVE:
        raise Refusal(
            RefusalCode.EVIDENCE_RECEIPT_MODE_NOT_LIVE,
            "The policy requires a live native receipt.",
        )
    if value["plan"]["digest"] != plan_digest:
        raise Refusal(
            RefusalCode.AUTH_APPROVAL_WRONG_PLAN,
            "The receipt is bound to another plan.",
        )
    approved = sorted(approved_targets)
    if (
        sorted(value["plan"]["approved_targets"]) != approved
        or sorted(value["plan"]["proposed_targets"]) != approved
        or sorted(value["apply"]["actual_targets"]) != approved
    ):
        raise Refusal(
            RefusalCode.SCOPE_RECEIPT_TARGET_MISMATCH,
            "Proposed, approved, and actual receipt targets differ.",
        )
    if value["source_before"]["version"] != source_version:
        raise Refusal(
            RefusalCode.SOURCE_RECEIPT_VERSION_MISMATCH,
            "The receipt source version differs from the approved source.",
        )
    validation_result = value["validation"]["result"]
    if validation_result == "FAILED":
        raise Refusal(
            RefusalCode.VALIDATION_RECEIPT_FAILED,
            "The native validator failed.",
        )
    if validation_result != "PASSED":
        raise Refusal(
            RefusalCode.VALIDATION_RECEIPT_INCONCLUSIVE,
            "The native validator did not produce a passing result.",
        )
    if value["terminal_disposition"] != ConsumerDisposition.VALIDATED:
        raise Refusal(
            RefusalCode.VALIDATION_RECEIPT_FAILED,
            "The receipt does not close the consumer as validated.",
        )
    validate_trusted_clock(
        now=trusted_now,
        observed_at=parse_timestamp(value["captured_at"]),
        expires_at=(
            parse_timestamp(value["expires_at"])
            if value["expires_at"] is not None
            else None
        ),
    )


def require_bound_inputs(
    *,
    recorded: Mapping[str, str],
    current: Mapping[str, str],
) -> None:
    """Refuse any policy, validator, or authorization configuration drift."""

    changed = sorted(
        key
        for key in set(recorded) | set(current)
        if recorded.get(key) != current.get(key)
    )
    if changed:
        raise Refusal(
            RefusalCode.POLICY_INPUT_DRIFT,
            "Executable campaign inputs changed after evidence acceptance.",
            {"changed_inputs": changed},
        )
