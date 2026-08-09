from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import verify_digest

ROOT = Path(__file__).resolve().parents[2]


def load_json(relative_path: str) -> dict[str, Any]:
    value = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_public_full_agent_run_proves_positive_path_and_revocation() -> None:
    evidence = load_json("artifacts/public/agent/full-run.json")

    verify_digest(evidence, "agent_full_run_digest")
    assert evidence["actor_boundary"]["independent_operator_evidence"] == "NOT_RUN"
    assert (
        evidence["human_authorization_pause"]["agent_authorization_tool_exposed"]
        is False
    )
    assert evidence["change_receipt"]["result"] == "PASSED"
    assert evidence["ready_path"]["gate_result"] == "EXECUTED"
    assert evidence["late_consumer_reversal"]["decision_before"] == "READY_TO_RETIRE"
    assert evidence["late_consumer_reversal"]["decision_after"] == "UNSAFE"
    assert evidence["late_consumer_reversal"]["blocker_codes"] == [
        "POLICY_CONSUMER_OPAQUE",
        "RECONCILIATION_NEW_CONSUMER",
    ]
    assert evidence["late_consumer_reversal"]["new_retirement_lease_prepared"] is False
    assert evidence["late_consumer_reversal"]["second_gate_called"] is False
    assert evidence["acceptance"]["agent_shell_call_count"] == 0


def test_concrete_agent_examples_are_digest_bound() -> None:
    for filename in (
        "change-receipt.json",
        "retirement-lease.json",
        "readiness-reversal.json",
    ):
        value = load_json(f"examples/agent-run/{filename}")
        verify_digest(value, "example_digest")

    patch = (ROOT / "examples/agent-run/migration.patch").read_text(encoding="utf-8")
    assert "-    legacy_status as normalized_status" in patch
    assert "+    order_status as normalized_status" in patch
