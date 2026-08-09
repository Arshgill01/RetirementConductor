from __future__ import annotations

import ast
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from retirement_conductor.semantic_ablation import (
    _run_deterministic_attempt,
    _scenario_inputs,
    freeze_corpus,
    run_authority_probes,
    verify_frozen_corpus,
)
from retirement_conductor.semantic_ablation_oracle import (
    evaluate_attempt,
    load_oracle_corpus,
    truth_digest,
)

ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = ROOT / "fixtures/semantic-ablation-v2/corpus.json"
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


def test_context_arms_share_identity_but_datahub_is_masked_only_in_dbt_arm() -> None:
    corpus = load_oracle_corpus(CORPUS_PATH)
    scenario = _scenario(corpus, "glossary-category-mapping")

    dbt_git, _, masked, dbt_context = _scenario_inputs(
        corpus, scenario, arm="gemini-dbt-only"
    )
    full_git, _, full, full_dbt = _scenario_inputs(
        corpus, scenario, arm="gemini-datahub-dbt"
    )

    assert dbt_git["campaign_id"] == full_git["campaign_id"]
    assert dbt_context["manifest"] == full_dbt["manifest"]
    assert masked["supported_relevant_checks"] == []
    assert masked["facts"] == {}
    assert {item["primitive"] for item in full["supported_relevant_checks"]} == {
        "accepted_values_coverage",
        "category_mapping_completeness",
    }


def test_deterministic_arm_is_repeatable_and_expected_refusals_fail_closed() -> None:
    corpus = load_oracle_corpus(CORPUS_PATH)
    exact = _scenario(corpus, "exact-passthrough-consumer")
    first = _run_deterministic_attempt(corpus, exact, attempt_number=1)
    second = _run_deterministic_attempt(corpus, exact, attempt_number=2)

    assert first["proposal_digest"] == second["proposal_digest"]
    assert first["accepted_checks"] == [
        "exact_model_output_parity",
        "type_compatibility",
    ]
    assert evaluate_attempt(exact, first)["exact_plan_match"] is True

    for scenario_id, refusal_code in (
        ("contradictory-datahub-dbt", "SPEC_REPLACEMENT_INCOMPATIBLE"),
        ("expired-evidence-envelope", "EVIDENCE_REQUIRED_SOURCE_INCOMPLETE"),
        ("source-fingerprint-mismatch", "SOURCE_FINGERPRINT_MISMATCH"),
    ):
        scenario = _scenario(corpus, scenario_id)
        attempt = _run_deterministic_attempt(corpus, scenario, attempt_number=1)
        assert attempt["kernel_outcome"] == "REFUSED"
        assert attempt["refusal_code"] == refusal_code
        assert evaluate_attempt(scenario, attempt)["exact_plan_match"] is True


def test_kernel_rejects_every_authority_smuggling_probe() -> None:
    corpus = load_oracle_corpus(CORPUS_PATH)
    probes = run_authority_probes(corpus)

    assert {item["probe"] for item in probes} == {
        "arbitrary_target",
        "authorization",
        "executable_sql",
        "foreign_identity",
        "policy_override",
        "unsupported_evidence",
    }
    assert all(item["accepted"] is False for item in probes)


def test_oracle_counts_forbidden_and_unnecessary_checks() -> None:
    corpus = load_oracle_corpus(CORPUS_PATH)
    scenario = _scenario(corpus, "aggregate-consumer-not-exact")
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


def test_incompatible_replacement_contract_refuses_before_check_selection() -> None:
    corpus = load_oracle_corpus(CORPUS_PATH)
    scenario = deepcopy(_scenario(corpus, "exact-passthrough-consumer"))
    scenario["kernel_fixture"]["compatible"] = False

    attempt = _run_deterministic_attempt(corpus, scenario, attempt_number=1)

    assert attempt["kernel_outcome"] == "REFUSED"
    assert attempt["refusal_code"] == "SPEC_REPLACEMENT_INCOMPATIBLE"


def _scenario(corpus: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    return next(item for item in corpus["scenarios"] if item["id"] == scenario_id)
