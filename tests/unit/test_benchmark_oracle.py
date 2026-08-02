from __future__ import annotations

import inspect

from retirement_conductor import benchmark_oracle
from retirement_conductor.benchmark_oracle import (
    build_oracle,
    evaluate_scenario_facts,
)
from retirement_conductor.canonical import verify_digest


def base_facts() -> dict[str, object]:
    return {
        "consumers": [{"id": "dbt:orders", "disposition": "VALIDATED"}],
        "current_consumer_ids": ["dbt:orders"],
        "evidence_status": "COMPLETE",
        "identity_match_count": 1,
        "inventory_consumer_ids": ["dbt:orders"],
        "native_data_fresh": True,
        "pagination_complete": True,
        "quality_failures": [],
        "reconciled": True,
        "replacement_compatible": True,
    }


def test_oracle_is_independent_and_changes_with_truth_facts() -> None:
    assert "retirement_conductor.policy" not in inspect.getsource(benchmark_oracle)
    ready = evaluate_scenario_facts(base_facts())
    changed = base_facts()
    changed["native_data_fresh"] = False
    stale = evaluate_scenario_facts(changed)

    assert ready == {
        "consumer_ids": ["dbt:orders"],
        "decision": "READY_TO_RETIRE",
        "refusal_codes": [],
    }
    assert stale["decision"] == "BLOCKED"
    assert stale["refusal_codes"] == ["EVIDENCE_REQUIRED_SOURCE_INCOMPLETE"]


def test_oracle_keeps_late_and_failed_consumers_unsafe() -> None:
    facts = base_facts()
    facts["consumers"] = [
        {"id": "dbt:orders", "disposition": "FAILED"},
        {"id": "spark:late", "disposition": "DISCOVERED"},
    ]
    facts["inventory_consumer_ids"] = ["dbt:orders"]
    facts["current_consumer_ids"] = ["dbt:orders", "spark:late"]
    facts["quality_failures"] = [{"id": "semantic-drift"}]

    result = evaluate_scenario_facts(facts)

    assert result["decision"] == "UNSAFE"
    assert result["refusal_codes"] == [
        "POLICY_CONSUMER_DISCOVERED",
        "POLICY_CONSUMER_FAILED",
        "RECONCILIATION_NEW_CONSUMER",
        "VALIDATION_RECEIPT_FAILED",
    ]


def test_built_oracle_is_deterministic_and_digest_bound() -> None:
    scenario = {
        "description": "One controlled clean scenario.",
        "facts": base_facts(),
        "id": "clean",
    }
    arguments = {
        "seed": 7,
        "scale": "small",
        "target_dataset_urn": "urn:li:dataset:(fixture)",
        "expected_graph": {"edges": [], "entities": []},
        "scenarios": [scenario],
    }

    first = build_oracle(**arguments)  # type: ignore[arg-type]
    second = build_oracle(**arguments)  # type: ignore[arg-type]

    assert first == second
    verify_digest(first, "oracle_digest")
    assert first["scenarios"][0]["expected"]["decision"] == "READY_TO_RETIRE"
