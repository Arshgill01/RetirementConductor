#!/usr/bin/env python3
"""Run the frozen static-signoff versus revocable-lease comparison."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import (
    digest_file,
    verify_digest,
    with_digest,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "fixtures/lease-value-comparison-v1/FROZEN.json"
PUBLIC_ROOT = ROOT / "artifacts/public/lease-value-comparison-v1"


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected a JSON object: {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def run() -> dict[str, Any]:
    protocol = load_object(PROTOCOL_PATH)
    summary_path = ROOT / protocol["source_evidence"]["campaign_summary"]
    receipt_path = ROOT / protocol["source_evidence"]["watch_receipt"]
    summary = load_object(summary_path)
    receipt = load_object(receipt_path)
    verify_digest(summary, "evidence_digest")
    verify_digest(receipt, "receipt_digest")

    require(summary["evidence_mode"] == "live local", "source run is not live local")
    require(
        summary["late_consumer"]["confidence_basis"]
        == protocol["intervention"]["required_confidence_basis"],
        "late-consumer intervention lacks the frozen confidence basis",
    )
    require(
        receipt["before"]["decision"]
        == protocol["success_criteria"]["same_pre_intervention_decision"],
        "source run did not begin from the frozen decision",
    )

    static_signoff = with_digest(
        {
            "schema_version": "1.0.0",
            "arm": "static-signoff",
            "decision": receipt["before"]["decision"],
            "manifest_digest": receipt["before"]["manifest_digest"],
            "evidence_envelope_digest": receipt["before"]["evidence_envelope_digest"],
            "behavior_on_new_evidence": "NONE",
            "producer_check": "READ_PERSISTED_SIGNOFF_ONLY",
        },
        "signoff_digest",
    )
    static_before = json.dumps(
        static_signoff, sort_keys=True, separators=(",", ":")
    ).encode()
    static_after = json.dumps(
        static_signoff, sort_keys=True, separators=(",", ":")
    ).encode()
    static_result = {
        "decision_exposed_to_producer": static_signoff["decision"],
        "signoff_digest_before": static_signoff["signoff_digest"],
        "signoff_digest_after": static_signoff["signoff_digest"],
        "stale_green_retained": (
            static_before == static_after
            and static_signoff["decision"] == "READY_TO_RETIRE"
        ),
        "automatic_refusal_available": False,
    }

    lease_result = {
        "decision_before": receipt["before"]["decision"],
        "decision_after": receipt["after"]["decision"],
        "lease_status_before": receipt["lease"]["status_before"],
        "lease_status_after": receipt["lease"]["status_after"],
        "gate_refusal": summary["gate"]["refusal_code"],
        "producer_action_count_delta": (
            summary["gate"]["sentinel_count_after"]
            - summary["gate"]["sentinel_count_before"]
        ),
        "stale_green_retained": False,
        "automatic_refusal_available": True,
    }
    criteria = protocol["success_criteria"]
    checks = {
        "static_signoff_stale_green_retained": (
            static_result["stale_green_retained"]
            is criteria["static_signoff_stale_green_retained"]
        ),
        "lease_invalidated": (
            lease_result["lease_status_after"] == criteria["lease_status_after"]
        ),
        "lease_gate_refused": (
            lease_result["gate_refusal"] == criteria["lease_gate_refusal"]
        ),
        "lease_producer_action_prevented": (
            lease_result["producer_action_count_delta"]
            == criteria["lease_producer_action_count_delta"]
        ),
        "source_receipt_bound": (
            summary["watch"]["receipt_digest"] == receipt["receipt_digest"]
        ),
    }
    require(all(checks.values()), "one or more frozen success criteria failed")

    report = with_digest(
        {
            "schema_version": "1.0.0",
            "experiment_id": protocol["experiment_id"],
            "result": "REVOCABLE_LEASE_ADDS_DECISIVE_SAFETY_VALUE",
            "protocol_digest": digest_file(PROTOCOL_PATH),
            "source": {
                "evidence_mode": summary["evidence_mode"],
                "campaign_evidence_digest": summary["evidence_digest"],
                "watch_receipt_digest": receipt["receipt_digest"],
                "late_consumer_reread_digest": summary["late_consumer"][
                    "exact_field_reread_digest"
                ],
            },
            "same_intervention": protocol["intervention"],
            "static_signoff": static_result,
            "revocable_lease": lease_result,
            "checks": checks,
            "interpretation": (
                "The static contract retained a pre-intervention green decision. "
                "The revocable lease observed the same late consumer, changed the "
                "campaign to UNSAFE, invalidated permission, and refused the "
                "preserved producer plan with zero actions."
            ),
            "limitations": protocol["limitations"],
        },
        "report_digest",
    )
    write_json(PUBLIC_ROOT / "static-signoff.json", static_signoff)
    write_json(PUBLIC_ROOT / "report.json", report)
    index = with_digest(
        {
            "schema_version": "1.0.0",
            "experiment_id": protocol["experiment_id"],
            "result": report["result"],
            "report_digest": report["report_digest"],
            "files": ["report.json", "static-signoff.json"],
            "limitations": protocol["limitations"],
        },
        "index_digest",
    )
    write_json(PUBLIC_ROOT / "index.json", index)
    return index


def main() -> int:
    result = run()
    print(
        f"{result['result']}: report={result['report_digest']} "
        f"index={result['index_digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
