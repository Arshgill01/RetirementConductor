from __future__ import annotations

import json
from pathlib import Path

from retirement_conductor.canonical import verify_digest

ROOT = Path(__file__).resolve().parents[2]


def test_live_heterogeneous_campaign_evidence_is_bound_and_consequential() -> None:
    evidence = json.loads(
        (ROOT / "artifacts/public/heterogeneous-campaign/evidence.json").read_text(
            encoding="utf-8"
        )
    )
    index = json.loads(
        (ROOT / "artifacts/public/heterogeneous-campaign/index.json").read_text(
            encoding="utf-8"
        )
    )

    verify_digest(evidence, "evidence_digest")
    verify_digest(index, "index_digest")
    assert index["evidence_digest"] == evidence["evidence_digest"]
    assert evidence["result"] == "HETEROGENEOUS_CAMPAIGN_PASSED"
    assert evidence["campaign"] == {
        "blocker_codes_after": ["POLICY_CONSUMER_STALE"],
        "consumer_count": 2,
        "decision_after_superset_removal": "UNSAFE",
        "decision_before_superset_removal": "READY_TO_RETIRE",
        "multiple_native_migrations_recorded": 2,
        "receipt_count_at_ready": 2,
    }
    assert evidence["superset"]["semantic_parity"] is True
    assert evidence["datahub"]["before_connector"]["exit_code"] == 0
    assert evidence["datahub"]["after_connector"]["exit_code"] == 0
