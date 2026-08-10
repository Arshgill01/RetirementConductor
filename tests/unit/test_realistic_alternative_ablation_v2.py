from __future__ import annotations

import ast
import copy
from pathlib import Path
from typing import Any

import pytest

from retirement_conductor.canonical import digest_json, verify_digest
from scripts.realistic_alternative_ablation import (
    ARM_IDS,
    EvaluationError,
    evaluate_run,
    load_object,
    run_arm,
    run_foundation_matrix,
    validate_baseline_capability,
    verify_public_evidence,
)
from scripts.realistic_alternative_ablation_oracle import (
    OracleError,
    expected_properties,
    oracle_digest,
    verify_frozen_protocol,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = ROOT / "fixtures/realistic-alternative-ablation-v2/FROZEN.json"
ORACLE_PATH = ROOT / "scripts/realistic_alternative_ablation_oracle.py"


def _protocol() -> dict[str, Any]:
    return load_object(PROTOCOL_PATH)


def _run_record(protocol: dict[str, Any]) -> dict[str, Any]:
    return {
        "frozen_digest": protocol["frozen_digest"],
        "results": [
            run_arm(arm, scenario, protocol)
            for scenario in protocol["scenarios"]
            for arm in ARM_IDS
        ],
    }


def _resign(protocol: dict[str, Any]) -> None:
    unsigned = dict(protocol)
    unsigned.pop("frozen_digest", None)
    protocol["frozen_digest"] = digest_json(unsigned)


def test_frozen_protocol_covers_the_required_matrix_with_independent_oracle() -> None:
    protocol = _protocol()
    verify_frozen_protocol(protocol)
    expected = expected_properties(protocol)

    assert len(expected) == 13
    assert set(expected) == {
        "no-drift-clean-control",
        "late-exact-field-consumer",
        "late-table-only-ambiguous-edge",
        "datahub-unavailable-at-action-time",
        "incomplete-pagination",
        "producer-schema-drift",
        "git-dbt-source-or-validation-drift",
        "superset-native-drift",
        "approval-expired-or-scope-changed",
        "action-replay",
        "crash-before-action",
        "lost-response-after-action-intent",
        "publication-or-audit-artifact-unavailable",
    }
    assert oracle_digest(protocol).startswith("sha256:")

    tree = ast.parse(ORACLE_PATH.read_text(encoding="utf-8"))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    assert imported_roots <= {
        "__future__",
        "hashlib",
        "json",
        "pathlib",
        "typing",
    }


def test_complete_matrix_classifies_no_material_advantage() -> None:
    protocol = _protocol()
    evaluated = evaluate_run(_run_record(protocol), protocol)

    assert evaluated["classification"] == "NO_MATERIAL_ADVANTAGE"
    assert evaluated["recommendation"] == "SIMPLIFY"
    clean = [
        row
        for row in evaluated["matrix"]
        if row["scenario_id"] == "no-drift-clean-control"
    ]
    assert all(row["observation"]["committed_actions"] == 1 for row in clean)
    assert all(row["metrics"]["false_refusal"] is False for row in clean)

    late = [
        row
        for row in evaluated["matrix"]
        if row["scenario_id"] == "late-exact-field-consumer"
    ]
    assert (
        next(row for row in late if row["arm"] == "point-in-time")["metrics"][
            "unsafe_committed_producer_actions"
        ]
        == 1
    )
    assert all(
        row["observation"]["committed_actions"] == 0
        for row in late
        if row["arm"] != "point-in-time"
    )


def test_evaluator_rejects_missing_arms_changed_inputs_and_unmatched_actions() -> None:
    protocol = _protocol()
    run_record = _run_record(protocol)

    missing = copy.deepcopy(run_record)
    missing["results"].pop()
    with pytest.raises(EvaluationError, match="missing arms"):
        evaluate_run(missing, protocol)

    changed = copy.deepcopy(run_record)
    changed["frozen_digest"] = "sha256:" + "0" * 64
    with pytest.raises(EvaluationError, match="inputs changed"):
        evaluate_run(changed, protocol)

    unmatched = copy.deepcopy(run_record)
    unmatched["results"][0]["native_action_contract_digest"] = "sha256:" + "1" * 64
    with pytest.raises(EvaluationError, match="unmatched native actions"):
        evaluate_run(unmatched, protocol)


def test_oracle_and_baseline_refuse_post_hoc_or_biased_changes() -> None:
    protocol = _protocol()
    changed_oracle = copy.deepcopy(protocol)
    changed_oracle["scenarios"][0]["expected_properties"]["producer_action_safe"] = (
        False
    )
    with pytest.raises(OracleError, match="post-hoc oracle"):
        verify_frozen_protocol(changed_oracle)

    biased = copy.deepcopy(protocol)
    biased["fresh_ci_capability_statement"]["capabilities"][
        "complete_paged_inventory"
    ] = False
    _resign(biased)
    with pytest.raises(EvaluationError, match="biased fresh-CI"):
        validate_baseline_capability(biased)


def test_runner_writes_self_digested_public_and_ignored_raw_evidence(
    tmp_path: Path,
) -> None:
    public = tmp_path / "public"
    raw = tmp_path / "private" / "raw-run.json"
    index = run_foundation_matrix(PROTOCOL_PATH, public_root=public, raw_path=raw)

    verify_digest(index, "index_digest")
    assert index["classification"] == "NO_MATERIAL_ADVANTAGE"
    assert index["recommendation"] == "SIMPLIFY"
    assert raw.is_file()
    verified = verify_public_evidence(PROTOCOL_PATH, public)
    assert verified["index_digest"] == index["index_digest"]
    failures = load_object(public / "failure-attempts.json")
    assert [probe["passed"] for probe in failures["probes"]] == [True] * 5
