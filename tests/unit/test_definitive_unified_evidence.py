from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import verify_digest

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "artifacts/public/definitive-unified-run/index.json"


def load_evidence() -> dict[str, Any]:
    value: object = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_definitive_run_binds_public_validation_and_lease_reversal() -> None:
    evidence = load_evidence()
    verify_digest(evidence, "index_digest")

    assert evidence["architecture"] == {
        "capability_bounded_claim": False,
        "datahub_context": "KEEP_BOUNDED",
        "nested_gemini_planner": "REMOVE",
        "project_skill": "KEEP",
        "retirement_conductor_mcp": "KEEP_PRIMARY_BOUNDARY",
    }
    assert evidence["bindings"]["github"]["check_conclusion"] == "SUCCESS"
    assert evidence["bindings"]["github"]["changed_files"] == [
        "models/orders_isolated_model.sql"
    ]
    assert evidence["bindings"]["watch"]["decision_before"] == "READY_TO_RETIRE"
    assert evidence["bindings"]["watch"]["decision_after"] == "UNSAFE"
    assert evidence["bindings"]["watch"]["lease_before"] == "ISSUED"
    assert evidence["bindings"]["watch"]["lease_after"] == "INVALIDATED"
    assert evidence["bindings"]["gate"] == {
        "refusal_code": "GATE_DECISION_NOT_READY",
        "result": "REFUSED",
        "sentinel_count": 0,
    }


def test_definitive_run_discloses_actual_capability_surface() -> None:
    evidence = load_evidence()
    host = evidence["host"]

    assert host["remaining_capabilities"]["shell"] is True
    assert host["remaining_capabilities"]["file_edit"] is True
    assert host["remaining_capabilities"]["datahub_metadata_mutations_advertised"]
    assert host["remaining_capabilities"]["capability_bounded"] is False
    assert evidence["observed_execution"]["unexpected_shell_call_count"] == 0
    assert evidence["observed_execution"]["unexpected_mcp_call_count"] == 0
    assert evidence["observed_execution"]["producer_action_count"] == 0
    assert evidence["shared_memory"]["document_found"] is True
    assert evidence["shared_memory"]["bounded_language_preserved"] is True
