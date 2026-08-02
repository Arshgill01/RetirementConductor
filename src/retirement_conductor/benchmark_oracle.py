"""Independent expected-result oracle for the data-quality benchmark.

This module intentionally does not import the campaign policy implementation.
It derives expected outcomes from truth-labeled scenario facts so benchmark
comparison can detect divergence instead of calling the code under test twice.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from retirement_conductor.canonical import with_digest
from retirement_conductor.schemas import validate_schema

ORACLE_VERSION = "1.0.0"

_ACCEPTED_DISPOSITIONS = frozenset({"VALIDATED", "REMOVED", "NOT_APPLICABLE"})
_UNSAFE_DISPOSITIONS = frozenset(
    {
        "APPLIED",
        "CHANGE_PROPOSED",
        "DISCOVERED",
        "FAILED",
        "IDENTIFIED",
        "OPAQUE",
        "STALE",
    }
)


def evaluate_scenario_facts(facts: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate truth facts without importing or calling campaign policy."""

    blocked: set[str] = set()
    unsafe: set[str] = set()

    identity_match_count = int(facts.get("identity_match_count", 0))
    if identity_match_count == 0:
        blocked.add("IDENTITY_NOT_FOUND")
    elif identity_match_count != 1:
        blocked.add("IDENTITY_AMBIGUOUS")

    if facts.get("replacement_compatible") is not True:
        unsafe.add("SPEC_REPLACEMENT_INCOMPATIBLE")

    if facts.get("evidence_status") != "COMPLETE":
        blocked.add("EVIDENCE_REQUIRED_SOURCE_INCOMPLETE")
    if facts.get("pagination_complete") is not True:
        blocked.add("EVIDENCE_PAGINATION_FAILED")
    if facts.get("native_data_fresh") is not True:
        blocked.add("EVIDENCE_REQUIRED_SOURCE_INCOMPLETE")

    quality_failures = facts.get("quality_failures", [])
    if isinstance(quality_failures, Sequence) and quality_failures:
        unsafe.add("VALIDATION_RECEIPT_FAILED")

    consumer_ids: list[str] = []
    consumers = facts.get("consumers", [])
    if isinstance(consumers, Sequence):
        for raw_consumer in consumers:
            if not isinstance(raw_consumer, Mapping):
                continue
            consumer_id = str(raw_consumer.get("id", ""))
            disposition = str(raw_consumer.get("disposition", ""))
            if consumer_id:
                consumer_ids.append(consumer_id)
            if disposition in _ACCEPTED_DISPOSITIONS:
                continue
            if disposition == "UNRESOLVED":
                blocked.add("IDENTITY_NOT_FOUND")
            elif disposition == "WAIVED":
                blocked.add("POLICY_WAIVER_FORBIDDEN")
            elif disposition in _UNSAFE_DISPOSITIONS:
                unsafe.add(f"POLICY_CONSUMER_{disposition}")

    inventory = _string_set(facts.get("inventory_consumer_ids"))
    current = _string_set(facts.get("current_consumer_ids"))
    if current - inventory:
        unsafe.add("RECONCILIATION_NEW_CONSUMER")
    if facts.get("reconciled") is not True:
        blocked.add("RECONCILIATION_REQUIRED")

    if unsafe:
        decision = "UNSAFE"
        refusal_codes = sorted(blocked | unsafe)
    elif blocked:
        decision = "BLOCKED"
        refusal_codes = sorted(blocked)
    else:
        decision = "READY_TO_RETIRE"
        refusal_codes = []
    return {
        "consumer_ids": sorted(set(consumer_ids)),
        "decision": decision,
        "refusal_codes": refusal_codes,
    }


def build_oracle(
    *,
    seed: int,
    scale: str,
    target_dataset_urn: str,
    expected_graph: Mapping[str, Any],
    scenarios: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build and schema-check one digest-bound benchmark oracle."""

    evaluated: list[dict[str, Any]] = []
    for scenario in scenarios:
        facts = _mapping(scenario.get("facts"))
        evaluated.append(
            {
                "description": str(scenario["description"]),
                "expected": evaluate_scenario_facts(facts),
                "facts": facts,
                "id": str(scenario["id"]),
            }
        )
    oracle = with_digest(
        {
            "campaign": {
                "legacy_field": "legacy_status",
                "replacement_field": "order_status",
                "target_dataset_urn": target_dataset_urn,
            },
            "expected_graph": dict(expected_graph),
            "oracle_version": ORACLE_VERSION,
            "scale": scale,
            "scenarios": sorted(evaluated, key=lambda item: str(item["id"])),
            "schema_version": "benchmark-oracle/v1",
            "seed": seed,
        },
        "oracle_digest",
    )
    validate_schema("benchmark-oracle", oracle)
    return oracle


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _string_set(value: object) -> set[str]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return set()
    return {str(item) for item in value}
