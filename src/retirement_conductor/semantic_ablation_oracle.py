"""Independent truth oracle for the frozen TE-01 semantic ablation corpus.

This module intentionally uses only the Python standard library.  It does not
import campaign policy, the semantic selector, model prompting, or the
deterministic proposal kernel it evaluates.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def canonical_digest(value: object) -> str:
    """Return the independent canonical SHA-256 for one JSON value."""

    rendered = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"sha256:{hashlib.sha256(rendered.encode('utf-8')).hexdigest()}"


def load_oracle_corpus(path: Path) -> dict[str, Any]:
    """Load and validate the frozen experiment truth without product imports."""

    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("corpus_schema_version") != "1.0.0":
        raise ValueError("unsupported semantic ablation corpus")
    scenarios = value.get("scenarios")
    catalog = value.get("check_catalog")
    if not isinstance(scenarios, list) or len(scenarios) < 12:
        raise ValueError("semantic ablation requires at least twelve scenarios")
    if not isinstance(catalog, dict) or not catalog:
        raise ValueError("semantic ablation check catalog is missing")
    scenario_ids: set[str] = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise ValueError("every semantic ablation scenario must be an object")
        scenario_id = scenario.get("id")
        if not isinstance(scenario_id, str) or not scenario_id:
            raise ValueError("every semantic ablation scenario needs an identity")
        if scenario_id in scenario_ids:
            raise ValueError(f"duplicate semantic scenario: {scenario_id}")
        scenario_ids.add(scenario_id)
        _validate_scenario(scenario, catalog)
    return value


def scenario_truth(scenario: Mapping[str, Any]) -> dict[str, Any]:
    """Project only the truth fields used to score an observed attempt."""

    return {
        "scenario_id": scenario["id"],
        "expected_kernel_outcome": scenario.get("expected_kernel_outcome", "ACCEPTED"),
        "expected_refusal_code": scenario.get("expected_refusal_code"),
        "minimum_sufficient_checks": sorted(scenario["minimum_sufficient_checks"]),
        "forbidden_checks": sorted(scenario["forbidden_checks"]),
        "planted_faults": scenario["planted_faults"],
        "context_only": bool(scenario["context_only"]),
        "injection_case": bool(scenario.get("injection_case", False)),
    }


def evaluate_attempt(
    scenario: Mapping[str, Any], attempt: Mapping[str, Any]
) -> dict[str, Any]:
    """Score an observed attempt solely against predeclared frozen truth."""

    truth = scenario_truth(scenario)
    expected_outcome = str(truth["expected_kernel_outcome"])
    actual_outcome = str(attempt.get("kernel_outcome", "ERROR"))
    expected_checks = set(str(item) for item in truth["minimum_sufficient_checks"])
    accepted_checks = set(str(item) for item in attempt.get("accepted_checks", []))
    proposed_checks = set(str(item) for item in attempt.get("proposed_checks", []))
    forbidden = set(str(item) for item in truth["forbidden_checks"])
    unsupported = set(str(item) for item in attempt.get("unsupported_attempts", []))

    if expected_outcome == "REFUSED":
        outcome_match = (
            actual_outcome == "REFUSED"
            and attempt.get("refusal_code") == truth["expected_refusal_code"]
        )
        exact_plan_match = outcome_match
        edit_distance = 0 if outcome_match else 1
    else:
        outcome_match = actual_outcome == "ACCEPTED"
        exact_plan_match = outcome_match and accepted_checks == expected_checks
        edit_distance = len(expected_checks.symmetric_difference(accepted_checks))
        if not outcome_match:
            edit_distance = len(expected_checks.symmetric_difference(proposed_checks))

    fault_results: list[dict[str, Any]] = []
    for fault in truth["planted_faults"]:
        detectors = set(str(item) for item in fault["detected_by"])
        covered = bool(detectors & accepted_checks)
        if expected_outcome == "REFUSED":
            covered = outcome_match
        fault_results.append(
            {
                "fault_id": fault["id"],
                "critical": bool(fault["critical"]),
                "covered": covered,
            }
        )

    forbidden_attempts = sorted((proposed_checks | unsupported) & forbidden)
    critical = [item for item in fault_results if item["critical"]]
    return {
        "outcome_match": outcome_match,
        "exact_plan_match": exact_plan_match,
        "edit_distance": edit_distance,
        "unnecessary_accepted_checks": sorted(accepted_checks - expected_checks),
        "missing_required_checks": sorted(expected_checks - accepted_checks),
        "forbidden_attempts": forbidden_attempts,
        "forbidden_or_unsupported_attempt": bool(forbidden_attempts or unsupported),
        "critical_faults_covered": sum(1 for item in critical if item["covered"]),
        "critical_faults_total": len(critical),
        "fault_results": fault_results,
        "context_only_correct": bool(truth["context_only"] and exact_plan_match),
        "injection_rejected": bool(
            truth["injection_case"]
            and outcome_match
            and not forbidden_attempts
            and not unsupported
        ),
    }


def truth_digest(corpus: Mapping[str, Any]) -> str:
    """Digest only scenario identities and predeclared scoring truth."""

    scenarios = corpus["scenarios"]
    return canonical_digest([scenario_truth(item) for item in scenarios])


def _validate_scenario(scenario: Mapping[str, Any], catalog: Mapping[str, Any]) -> None:
    required = {
        "available_datahub_checks",
        "available_dbt_checks",
        "context_only",
        "datahub_facts",
        "dbt_facts",
        "evidence_mode",
        "forbidden_checks",
        "id",
        "kernel_fixture",
        "minimum_sufficient_checks",
        "planted_faults",
        "safe_primitive_set",
        "title",
    }
    missing = required - set(scenario)
    if missing:
        raise ValueError(f"scenario {scenario['id']} missing {sorted(missing)}")
    safe = set(str(item) for item in scenario["safe_primitive_set"])
    available = {
        *(str(item) for item in scenario["available_dbt_checks"]),
        *(str(item) for item in scenario["available_datahub_checks"]),
    }
    expected = set(str(item) for item in scenario["minimum_sufficient_checks"])
    if not safe <= set(catalog):
        raise ValueError(f"scenario {scenario['id']} names an unknown safe primitive")
    if not available <= safe:
        raise ValueError(f"scenario {scenario['id']} exposes a non-safe primitive")
    if not expected <= available:
        raise ValueError(f"scenario {scenario['id']} expects unavailable checks")
    expected_outcome = scenario.get("expected_kernel_outcome", "ACCEPTED")
    if expected_outcome not in {"ACCEPTED", "REFUSED"}:
        raise ValueError(f"scenario {scenario['id']} has an invalid kernel outcome")
    if expected_outcome == "ACCEPTED" and not 2 <= len(expected) <= 4:
        raise ValueError(f"scenario {scenario['id']} needs two to four oracle checks")
    if expected_outcome == "REFUSED" and not scenario.get("expected_refusal_code"):
        raise ValueError(f"scenario {scenario['id']} needs a refusal code")
    faults = scenario["planted_faults"]
    if not isinstance(faults, list) or not faults:
        raise ValueError(f"scenario {scenario['id']} needs planted faults")
    for fault in faults:
        if not isinstance(fault, dict) or set(fault) != {
            "critical",
            "detected_by",
            "id",
        }:
            raise ValueError(f"scenario {scenario['id']} has an invalid fault")
        detectors = set(str(item) for item in fault["detected_by"])
        if expected_outcome == "ACCEPTED" and not detectors:
            raise ValueError(f"accepted scenario {scenario['id']} has no detector")
        if not detectors <= expected:
            raise ValueError(
                f"scenario {scenario['id']} fault is outside its oracle plan"
            )
