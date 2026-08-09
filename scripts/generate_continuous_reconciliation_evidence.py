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
    ):
        raise RuntimeError("WS-03 evidence does not prove the acceptance contract")
    if summary["watch"]["receipt_digest"] != receipt["receipt_digest"]:
        raise RuntimeError("the public watch receipt is not bound to the live summary")
    write_json(PUBLIC_ROOT / "continuous-reconciliation.json", summary)
    write_json(PUBLIC_ROOT / "watch-receipt.json", receipt)
    index = {
        "schema_version": "1.0.0",
        "evidence_mode": "live local",
        "acceptance_evidence_digest": summary["evidence_digest"],
        "watch_receipt_digest": receipt["receipt_digest"],
        "files": [
            "continuous-reconciliation.json",
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
