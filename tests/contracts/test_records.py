from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from retirement_conductor.canonical import with_digest
from retirement_conductor.errors import Refusal
from retirement_conductor.records import (
    require_bound_inputs,
    validate_approval,
    validate_consumer_receipt,
    validate_waiver,
)

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
CAMPAIGN_ID = "ret-orders-legacy-status"
CONSUMER_ID = "consumer-dbt-order-summary"
PLAN_DIGEST = f"sha256:{'a' * 64}"
AUTHORIZATION_DIGEST = f"sha256:{'b' * 64}"
TARGETS = ["models/order_summary.sql"]


def valid_approval() -> dict[str, Any]:
    return with_digest(
        {
            "schema_version": "1.0.0",
            "approval_id": "approval-one",
            "campaign_id": CAMPAIGN_ID,
            "plan_digest": PLAN_DIGEST,
            "source_version": "commit-one",
            "targets": TARGETS,
            "principal": "fixture-operator",
            "scope": ["apply", "validate"],
            "authorization_digest": AUTHORIZATION_DIGEST,
            "authorized_at": "2026-01-01T11:00:00Z",
            "expires_at": "2026-01-01T13:00:00Z",
        },
        "approval_digest",
    )


def validate_selected_approval(approval: dict[str, Any] | None) -> None:
    validate_approval(
        approval,
        campaign_id=CAMPAIGN_ID,
        plan_digest=PLAN_DIGEST,
        source_version="commit-one",
        targets=TARGETS,
        required_scope=["apply"],
        authorization_digest=AUTHORIZATION_DIGEST,
        trusted_now=NOW,
    )


def valid_live_receipt() -> dict[str, Any]:
    receipt = json.loads(
        (ROOT / "artifacts/public/phase00/receipt.json").read_text(encoding="utf-8")
    )
    receipt["adapter"]["mode"] = "live"
    receipt["apply"]["result"] = "APPLIED"
    receipt["apply"]["actual_targets"] = TARGETS
    receipt["plan"]["digest"] = PLAN_DIGEST
    receipt["source_before"]["version"] = "commit-one"
    receipt["captured_at"] = "2026-01-01T11:00:00Z"
    receipt["expires_at"] = "2026-01-01T13:00:00Z"
    return with_digest(receipt, "receipt_digest")


def validate_selected_receipt(receipt: dict[str, Any]) -> None:
    validate_consumer_receipt(
        receipt,
        campaign_id=CAMPAIGN_ID,
        consumer_id=CONSUMER_ID,
        plan_digest=PLAN_DIGEST,
        source_version="commit-one",
        approved_targets=TARGETS,
        require_live=True,
        trusted_now=NOW,
    )


def test_exact_approval_and_live_receipt_pass() -> None:
    validate_selected_approval(valid_approval())
    validate_selected_receipt(valid_live_receipt())


def test_missing_approval_refuses() -> None:
    with pytest.raises(Refusal, match="AUTH_APPROVAL_MISSING"):
        validate_selected_approval(None)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("campaign_id", "other", "AUTH_APPROVAL_WRONG_CAMPAIGN"),
        ("plan_digest", f"sha256:{'c' * 64}", "AUTH_APPROVAL_WRONG_PLAN"),
        ("source_version", "commit-other", "AUTH_APPROVAL_WRONG_SOURCE"),
        ("targets", ["models/other.sql"], "AUTH_APPROVAL_WRONG_SCOPE"),
        ("scope", ["read"], "AUTH_APPROVAL_WRONG_SCOPE"),
        ("expires_at", "2026-01-01T12:00:00Z", "AUTH_APPROVAL_EXPIRED"),
    ],
)
def test_wrong_or_expired_approval_refuses(
    field: str,
    value: object,
    code: str,
) -> None:
    approval = valid_approval()
    approval[field] = value
    approval = with_digest(approval, "approval_digest")

    with pytest.raises(Refusal, match=code):
        validate_selected_approval(approval)


@pytest.mark.parametrize("mode", ["fixture", "replay"])
def test_non_live_receipt_refuses_live_policy(mode: str) -> None:
    receipt = valid_live_receipt()
    receipt["adapter"]["mode"] = mode
    receipt = with_digest(receipt, "receipt_digest")

    with pytest.raises(Refusal, match="EVIDENCE_RECEIPT_MODE_NOT_LIVE"):
        validate_selected_receipt(receipt)


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ({"expires_at": "2026-01-01T12:00:00Z"}, "EVIDENCE_RECEIPT_EXPIRED"),
        ({"plan.digest": f"sha256:{'c' * 64}"}, "AUTH_APPROVAL_WRONG_PLAN"),
        (
            {"source_before.version": "commit-other"},
            "SOURCE_RECEIPT_VERSION_MISMATCH",
        ),
        (
            {"apply.actual_targets": ["models/other.sql"]},
            "SCOPE_RECEIPT_TARGET_MISMATCH",
        ),
        ({"validation.result": "FAILED"}, "VALIDATION_RECEIPT_FAILED"),
        (
            {"validation.result": "INCONCLUSIVE"},
            "VALIDATION_RECEIPT_INCONCLUSIVE",
        ),
    ],
)
def test_invalid_receipt_refuses(
    mutation: dict[str, object],
    code: str,
) -> None:
    receipt = valid_live_receipt()
    for dotted_key, value in mutation.items():
        parts = dotted_key.split(".")
        target = receipt
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value
    receipt = with_digest(receipt, "receipt_digest")

    with pytest.raises(Refusal, match=code):
        validate_selected_receipt(receipt)


def test_digest_mismatch_refuses_receipt() -> None:
    receipt = valid_live_receipt()
    receipt["validation"]["validator"] = "tampered"

    with pytest.raises(Refusal, match="INTEGRITY_DIGEST_MISMATCH"):
        validate_selected_receipt(receipt)


def test_waiver_is_bounded_and_expiring() -> None:
    waiver = with_digest(
        {
            "schema_version": "1.0.0",
            "campaign_id": CAMPAIGN_ID,
            "consumer_id": CONSUMER_ID,
            "authority": "fixture-risk-owner",
            "scope": ["consumer"],
            "reason": "bounded fixture exception",
            "residual_risk": "consumer may still depend on the field",
            "authorized_at": "2026-01-01T11:00:00Z",
            "expires_at": "2026-01-01T13:00:00Z",
        },
        "waiver_digest",
    )
    validate_waiver(
        waiver,
        campaign_id=CAMPAIGN_ID,
        consumer_id=CONSUMER_ID,
        required_scope=["consumer"],
        trusted_now=NOW,
    )
    expired = deepcopy(waiver)
    expired["expires_at"] = "2026-01-01T12:00:00Z"
    expired = with_digest(expired, "waiver_digest")

    with pytest.raises(Refusal, match="AUTH_WAIVER_EXPIRED"):
        validate_waiver(
            expired,
            campaign_id=CAMPAIGN_ID,
            consumer_id=CONSUMER_ID,
            required_scope=["consumer"],
            trusted_now=NOW,
        )

    wrong_scope = deepcopy(waiver)
    wrong_scope["scope"] = ["other"]
    wrong_scope = with_digest(wrong_scope, "waiver_digest")
    with pytest.raises(Refusal, match="AUTH_WAIVER_INVALID"):
        validate_waiver(
            wrong_scope,
            campaign_id=CAMPAIGN_ID,
            consumer_id=CONSUMER_ID,
            required_scope=["consumer"],
            trusted_now=NOW,
        )


def test_executable_input_drift_refuses() -> None:
    with pytest.raises(Refusal, match="POLICY_INPUT_DRIFT"):
        require_bound_inputs(
            recorded={"policy": "one", "validator": "one", "authorization": "one"},
            current={"policy": "one", "validator": "two", "authorization": "one"},
        )
