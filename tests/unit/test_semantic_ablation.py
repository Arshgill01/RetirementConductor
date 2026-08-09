from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from retirement_conductor.semantic_ablation import (
    freeze_corpus,
    verify_frozen_corpus,
    verify_public_evidence,
)
from retirement_conductor.semantic_ablation_oracle import (
    evaluate_attempt,
    load_oracle_corpus,
    truth_digest,
)

ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = ROOT / "fixtures/semantic-ablation-v2/corpus.json"
FREEZE_PATH = ROOT / "fixtures/semantic-ablation-v2/FROZEN.json"
PUBLIC_PATH = ROOT / "artifacts/public/semantic-ablation-v2"
ORACLE_PATH = ROOT / "src/retirement_conductor/semantic_ablation_oracle.py"


def test_frozen_corpus_covers_every_predeclared_case_without_policy_imports() -> None:
    corpus = load_oracle_corpus(CORPUS_PATH)
    scenario_ids = {item["id"] for item in corpus["scenarios"]}

    assert len(scenario_ids) == 15
    assert {
        "glossary-category-mapping",
        "query-aggregate-behavior",
        "quality-null-uniqueness",
        "native-freshness-not-ingestion",
        "exact-passthrough-consumer",
        "aggregate-consumer-not-exact",
        "physical-type-business-mismatch",
        "ownership-without-authority",
        "missing-optional-context",
        "contradictory-datahub-dbt",
        "prompt-injection-metadata-query",
        "irrelevant-rich-context",
        "expired-evidence-envelope",
        "source-fingerprint-mismatch",
    } <= scenario_ids
    assert truth_digest(corpus).startswith("sha256:")

    tree = ast.parse(ORACLE_PATH.read_text(encoding="utf-8"))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    assert imported_roots <= {
        "__future__",
        "collections",
        "hashlib",
        "json",
        "pathlib",
        "typing",
    }


def test_freeze_binds_exact_corpus_bytes_and_refuses_drift(tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_bytes(CORPUS_PATH.read_bytes())
    freeze_path = tmp_path / "FROZEN.json"

    record = freeze_corpus(corpus_path, freeze_path)

    assert record["scenario_count"] == 15
    assert record["live_model_outputs_observed_before_freeze"] is False
    assert freeze_corpus(corpus_path, freeze_path) == record
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    corpus["scenarios"][0]["title"] = "drifted after output"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
    with pytest.raises(ValueError, match=r"drifted|does not match"):
        verify_frozen_corpus(corpus_path, freeze_path)


def test_public_evidence_recomputes_every_attempt_offline() -> None:
    summary = verify_public_evidence(PUBLIC_PATH)

    assert summary["nested_gemini_recommendation"]["recommendation"] == "REMOVE"
    assert summary["datahub_context_recommendation"]["recommendation"] == "ADDS_VALUE"
    assert (
        summary["metrics"]["gemini-datahub-dbt"][
            "safety_critical_planted_fault_coverage"
        ]
        == 1.0
    )
    assert (
        summary["metrics"]["gemini-datahub-dbt"]["minimum_sufficient_plan_match_rate"]
        == 0.2
    )


def test_public_verifier_requires_no_live_model_configuration() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/run_semantic_value_ablation.py", "verify"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env={},
    )

    assert "verified offline" in completed.stdout
    assert "recommendation=REMOVE" in completed.stdout


def test_public_verifier_refuses_attempt_evaluation_drift(tmp_path: Path) -> None:
    public = tmp_path / "artifacts/public/semantic-ablation-v2"
    public.mkdir(parents=True)
    for source in PUBLIC_PATH.iterdir():
        if source.is_file():
            (public / source.name).write_bytes(source.read_bytes())
    fixture = tmp_path / "fixtures/semantic-ablation-v2"
    fixture.mkdir(parents=True)
    (fixture / "corpus.json").write_bytes(CORPUS_PATH.read_bytes())
    (fixture / "FROZEN.json").write_bytes(FREEZE_PATH.read_bytes())
    for record in load_oracle_corpus(CORPUS_PATH)["retained_live_context_shapes"]:
        source = ROOT / str(record["artifact"])
        target = tmp_path / str(record["artifact"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())

    results_path = public / "results.json"
    results: dict[str, Any] = json.loads(results_path.read_text(encoding="utf-8"))
    results["attempts"][0]["evaluation"]["exact_plan_match"] = not results["attempts"][
        0
    ]["evaluation"]["exact_plan_match"]
    results_path.write_text(json.dumps(results), encoding="utf-8")

    with pytest.raises(ValueError, match="artifact digest mismatch"):
        verify_public_evidence(public)


def test_oracle_counts_forbidden_and_unnecessary_checks() -> None:
    corpus = load_oracle_corpus(CORPUS_PATH)
    scenario = next(
        item
        for item in corpus["scenarios"]
        if item["id"] == "aggregate-consumer-not-exact"
    )
    attempt: dict[str, Any] = {
        "kernel_outcome": "ACCEPTED",
        "refusal_code": None,
        "accepted_checks": ["exact_model_output_parity", "type_compatibility"],
        "proposed_checks": ["exact_model_output_parity", "type_compatibility"],
        "unsupported_attempts": [],
    }

    result = evaluate_attempt(scenario, attempt)

    assert result["exact_plan_match"] is False
    assert result["missing_required_checks"] == ["aggregate_parity"]
    assert result["unnecessary_accepted_checks"] == ["exact_model_output_parity"]
    assert result["forbidden_attempts"] == ["exact_model_output_parity"]
