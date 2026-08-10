from __future__ import annotations

import json
from pathlib import Path

from retirement_conductor.canonical import verify_digest
from scripts.run_lease_value_comparison import run

ROOT = Path(__file__).resolve().parents[2]


def test_frozen_lease_value_comparison_is_decisive() -> None:
    result = run()
    report = json.loads(
        (ROOT / "artifacts/public/lease-value-comparison-v1/report.json").read_text(
            encoding="utf-8"
        )
    )

    verify_digest(result, "index_digest")
    verify_digest(report, "report_digest")
    assert result["result"] == "REVOCABLE_LEASE_ADDS_DECISIVE_SAFETY_VALUE"
    assert report["static_signoff"]["stale_green_retained"] is True
    assert report["revocable_lease"] == {
        "automatic_refusal_available": True,
        "decision_after": "UNSAFE",
        "decision_before": "READY_TO_RETIRE",
        "gate_refusal": "GATE_DECISION_NOT_READY",
        "lease_status_after": "INVALIDATED",
        "lease_status_before": "ISSUED",
        "producer_action_count_delta": 0,
        "stale_green_retained": False,
    }
    assert all(report["checks"].values())
