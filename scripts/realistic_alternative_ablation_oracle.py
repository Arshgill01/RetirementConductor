#!/usr/bin/env python3
"""Independent observable-facts oracle for CP-03.

This module intentionally does not import Retirement Conductor policy, the gate,
the comparison arms, or the scenario runner.  It validates only frozen inputs
and observable native outcomes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class OracleError(ValueError):
    """Raised when the frozen protocol or an observed result is inconsistent."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def digest_json(value: Any) -> str:
    return f"sha256:{hashlib.sha256(canonical_json(value).encode()).hexdigest()}"


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise OracleError(f"expected a JSON object: {path}")
    return value


def unsigned_frozen(protocol: dict[str, Any]) -> dict[str, Any]:
    value = dict(protocol)
    value.pop("frozen_digest", None)
    return value


def verify_frozen_protocol(protocol: dict[str, Any]) -> None:
    expected = protocol.get("frozen_digest")
    actual = digest_json(unsigned_frozen(protocol))
    if expected != actual:
        raise OracleError(
            f"post-hoc oracle or input edit detected: expected {expected}, got {actual}"
        )
    if protocol.get("frozen_before_execution") is not True:
        raise OracleError(
            "protocol does not assert that it was frozen before execution"
        )
    if protocol.get("base_commit") != "b8a839acd0b411d905fa0ed142838cd76ab618f4":
        raise OracleError("protocol is not bound to the assigned base commit")


def _expected_from_facts(scenario: dict[str, Any]) -> dict[str, Any]:
    facts = scenario["action_time_facts"]
    graph_complete = facts["datahub_status"] == "COMPLETE"
    graph_unchanged = facts["consumer_membership"] == facts["approved_membership"]
    source_bound = facts["producer_fingerprint_matches"]
    validation_bound = (
        facts["git_dbt_validation_matches"] and facts["superset_validation_matches"]
    )
    approval_bound = facts["approval_valid_for_scope_and_time"]
    safety_known = (
        graph_complete
        and graph_unchanged
        and source_bound
        and validation_bound
        and approval_bound
    )
    destructive_may_execute = safety_known and facts["audit_sink_available"]
    action_fault = facts["action_fault"]
    committed = 1 if destructive_may_execute else 0
    column_present = not bool(committed)
    unresolved = (
        action_fault == "LOST_RESPONSE_AFTER_COMMIT"
        and not facts["native_outcome_reread_available"]
    )
    return {
        "producer_action_safe": safety_known,
        "destructive_statement_may_execute": destructive_may_execute,
        "expected_max_committed_action_count": committed,
        "expected_final_column_present": column_present,
        "expected_downstream_workload_health": column_present
        or facts["downstream_uses_replacement_only"],
        "prior_approval_operationally_reusable": safety_known,
        "must_retain_unresolved_outcome": unresolved,
        "minimum_audit_fields": [
            "graph",
            "source",
            "approval",
            "validation",
            "action",
            "outcome",
        ],
    }


def expected_properties(protocol: dict[str, Any]) -> dict[str, dict[str, Any]]:
    verify_frozen_protocol(protocol)
    result: dict[str, dict[str, Any]] = {}
    for scenario in protocol["scenarios"]:
        scenario_id = scenario["id"]
        computed = _expected_from_facts(scenario)
        if computed != scenario["expected_properties"]:
            raise OracleError(
                f"frozen expected properties disagree with facts: {scenario_id}"
            )
        result[scenario_id] = computed
    return result


def scenario_input_digest(scenario: dict[str, Any]) -> str:
    return digest_json(
        {
            "id": scenario["id"],
            "action_time_facts": scenario["action_time_facts"],
            "expected_properties": scenario["expected_properties"],
        }
    )


def oracle_digest(protocol: dict[str, Any]) -> str:
    return digest_json(expected_properties(protocol))


def verify_observation(
    expected: dict[str, Any], observation: dict[str, Any]
) -> dict[str, Any]:
    unsafe_committed = int(
        observation["committed_actions"] > 0 and not expected["producer_action_safe"]
    )
    false_refusal = bool(
        expected["destructive_statement_may_execute"]
        and observation["committed_actions"] == 0
        and observation["final_outcome"] == "REFUSED"
    )
    duplicate_commit = observation["committed_actions"] > int(
        expected["expected_max_committed_action_count"]
    )
    unknown_correct = (
        observation["outcome_unknown"] is expected["must_retain_unresolved_outcome"]
    )
    final_column_correct = (
        observation["column_present"] is expected["expected_final_column_present"]
    )
    return {
        "unsafe_committed_producer_actions": unsafe_committed,
        "false_refusal": false_refusal,
        "duplicate_commit": duplicate_commit,
        "outcome_unknown_state_correct": unknown_correct,
        "final_column_state_matches_oracle": final_column_correct,
    }
