#!/usr/bin/env python3
"""Promote inspected WS-03 live-local evidence into public-safe artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import verify_digest, write_json
from retirement_conductor.schemas import validate_schema

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / ".retirement-conductor" / "e2e" / "continuous-reconciliation"
PUBLIC_ROOT = ROOT / "artifacts" / "public" / "ws03"


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected one JSON object: {path.name}")
    return value


def run() -> dict[str, Any]:
    summary = load_object(RUNTIME_ROOT / "latest.json")
    receipt = load_object(RUNTIME_ROOT / "latest-watch-receipt.json")
    verify_digest(summary, "evidence_digest")
    verify_digest(receipt, "receipt_digest")
    validate_schema("watch-receipt", receipt)
    if summary.get("evidence_mode") != "live local":
        raise RuntimeError("WS-03 evidence mode is not live local")
    if (
        summary["watch"]["result"] != "REVERSED"
        or summary["watch"]["before_decision"] != "READY_TO_RETIRE"
        or summary["watch"]["after_decision"] != "UNSAFE"
        or summary["lease"]["issued_status"] != "ISSUED"
        or summary["lease"]["after_watch_status"] != "INVALIDATED"
        or summary["watch"]["publication_verified"] is not True
        or summary["gate"]["refusal_code"] != "GATE_DECISION_NOT_READY"
        or summary["gate"]["sentinel_count_before"]
        != summary["gate"]["sentinel_count_after"]
        or summary["recovery"]["decision_after_edge_removal"] != "UNSAFE"
        or summary["late_consumer"]["confidence_basis"] != "column_lineage_edge"
    ):
        raise RuntimeError("WS-03 evidence does not prove the acceptance contract")
    if summary["watch"]["receipt_digest"] != receipt["receipt_digest"]:
        raise RuntimeError("the public watch receipt is not bound to the live summary")
    run_root = RUNTIME_ROOT / str(summary["runtime_run_id"])
    write_receipt = load_object(run_root / "late-datahub-write-receipt.json")
    verify_digest(write_receipt, "refresh_digest")
    snapshot_digest = summary["late_consumer"]["independent_snapshot_digest"]
    matches = []
    for path in (run_root / "independent-reread" / "late-consumer").rglob(
        "snapshot.json"
    ):
        candidate = load_object(path)
        if candidate.get("snapshot_digest") == snapshot_digest:
            matches.append(candidate)
    if len(matches) != 1:
        raise RuntimeError("the exact independent late-consumer reread is ambiguous")
    snapshot = matches[0]
    late_claim_id = summary["late_consumer"]["exact_field_claim_id"]
    late_claims = [
        claim for claim in snapshot["claims"] if claim.get("claim_id") == late_claim_id
    ]
    if (
        len(late_claims) != 1
        or late_claims[0].get("confidence_basis") != "column_lineage_edge"
    ):
        raise RuntimeError("the late-consumer reread lacks exact field lineage")
    late_subject = late_claims[0]["subject"]
    late_consumers = [
        consumer
        for consumer in snapshot["consumers"]
        if consumer.get("datahub_urn") == late_subject
    ]
    if len(late_consumers) != 1:
        raise RuntimeError("the exact late consumer is absent from the reread")
    reread = {
        "schema_version": "1.0.0",
        "evidence_mode": "live local",
        "captured_at": snapshot["captured_at"],
        "snapshot_digest": snapshot["snapshot_digest"],
        "consumer": late_consumers[0],
        "claim": late_claims[0],
        "pagination": snapshot["pagination"],
        "limitations": [
            (
                "This proves the exact disposable DataHub field edge inside the "
                "declared scope."
            ),
            "It does not prove visibility outside the recorded evidence envelope.",
        ],
    }
    write_json(PUBLIC_ROOT / "continuous-reconciliation.json", summary)
    write_json(PUBLIC_ROOT / "watch-receipt.json", receipt)
    write_json(PUBLIC_ROOT / "late-datahub-write-receipt.json", write_receipt)
    write_json(PUBLIC_ROOT / "late-consumer-reread.json", reread)
    index = {
        "schema_version": "1.0.0",
        "evidence_mode": "live local",
        "acceptance_evidence_digest": summary["evidence_digest"],
        "watch_receipt_digest": receipt["receipt_digest"],
        "files": [
            "continuous-reconciliation.json",
            "late-consumer-reread.json",
            "late-datahub-write-receipt.json",
            "watch-receipt.json",
        ],
        "limitations": summary["limitations"],
    }
    write_json(PUBLIC_ROOT / "index.json", index)
    return index


def main() -> int:
    result = run()
    print(
        "WS-03 evidence promoted: "
        f"acceptance={result['acceptance_evidence_digest']} "
        f"watch={result['watch_receipt_digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
