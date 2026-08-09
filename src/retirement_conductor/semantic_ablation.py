"""Offline verification for the retained TE-01 semantic-ablation evidence."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from retirement_conductor.canonical import digest_json, with_digest, write_json
from retirement_conductor.semantic_ablation_oracle import (
    evaluate_attempt,
    load_oracle_corpus,
    truth_digest,
)

ARMS = ("deterministic", "gemini-dbt-only", "gemini-datahub-dbt")
ATTEMPTS_PER_ARM = 3
SCENARIO_COUNT = 15


def freeze_corpus(corpus_path: Path, freeze_path: Path) -> dict[str, Any]:
    """Create or verify the immutable pre-output corpus record."""

    record = _freeze_record(corpus_path)
    if freeze_path.exists():
        existing = json.loads(freeze_path.read_text(encoding="utf-8"))
        if existing != record:
            raise ValueError("the existing corpus freeze does not match current bytes")
        return record
    write_json(freeze_path, record)
    return record


def verify_frozen_corpus(corpus_path: Path, freeze_path: Path) -> dict[str, Any]:
    """Refuse verification when frozen truth or retained source shapes drift."""

    if not freeze_path.is_file():
        raise ValueError("the semantic ablation corpus has not been frozen")
    expected = json.loads(freeze_path.read_text(encoding="utf-8"))
    actual = _freeze_record(corpus_path)
    if expected != actual:
        raise ValueError("frozen semantic ablation corpus drifted after publication")
    corpus = load_oracle_corpus(corpus_path)
    _verify_retained_shapes(corpus, corpus_path.parents[2])
    return corpus


def verify_public_evidence(public_directory: Path) -> dict[str, Any]:
    """Verify retained evidence completely without credentials or a model call."""

    configuration = _load_digest_artifact(
        public_directory / "configuration.json", "configuration_digest"
    )
    results = _load_digest_artifact(public_directory / "results.json", "results_digest")
    review = _load_digest_artifact(
        public_directory / "review-artifact.json", "review_artifact_digest"
    )
    failures = _load_digest_artifact(
        public_directory / "observed-failures.json", "failure_artifact_digest"
    )
    summary = _load_digest_artifact(public_directory / "summary.json", "summary_digest")
    for key, value in {
        "configuration_digest": configuration["configuration_digest"],
        "results_digest": results["results_digest"],
        "review_artifact_digest": review["review_artifact_digest"],
        "failure_artifact_digest": failures["failure_artifact_digest"],
    }.items():
        if summary.get(key) != value:
            raise ValueError(f"public semantic ablation link mismatch: {key}")

    root = public_directory.parents[2]
    corpus = verify_frozen_corpus(
        root / "fixtures/semantic-ablation-v2/corpus.json",
        root / "fixtures/semantic-ablation-v2/FROZEN.json",
    )
    scenarios = {str(item["id"]): item for item in corpus["scenarios"]}
    attempts = results.get("attempts")
    expected_count = len(ARMS) * ATTEMPTS_PER_ARM * SCENARIO_COUNT
    if not isinstance(attempts, list) or results.get("attempt_count") != expected_count:
        raise ValueError("public semantic ablation attempt matrix is incomplete")

    identities: Counter[tuple[str, str]] = Counter()
    response_ids: list[str] = []
    for attempt in attempts:
        if not isinstance(attempt, dict):
            raise ValueError("public semantic ablation attempt is not an object")
        arm = str(attempt.get("arm"))
        scenario_id = str(attempt.get("scenario_id"))
        if arm not in ARMS or scenario_id not in scenarios:
            raise ValueError("public semantic ablation attempt has unknown identity")
        identities[(arm, scenario_id)] += 1
        observed = attempt.get("evaluation")
        recomputed = evaluate_attempt(scenarios[scenario_id], attempt)
        if observed != recomputed:
            raise ValueError(
                f"public semantic ablation evaluation drifted: {arm}/{scenario_id}"
            )
        values = attempt.get("response_ids", [])
        if not isinstance(values, list) or not all(
            isinstance(item, str) for item in values
        ):
            raise ValueError("public semantic ablation response IDs are invalid")
        response_ids.extend(values)

    if any(count != ATTEMPTS_PER_ARM for count in identities.values()):
        raise ValueError("public semantic ablation attempt identities are incomplete")
    if len(identities) != len(ARMS) * SCENARIO_COUNT:
        raise ValueError("public semantic ablation scenario coverage is incomplete")
    if len(response_ids) != 180 or len(set(response_ids)) != 180:
        raise ValueError("public semantic ablation native response identity drifted")
    if len(review.get("rows", [])) != expected_count:
        raise ValueError("public semantic ablation review artifact is incomplete")
    if (
        summary.get("nested_gemini_recommendation", {}).get("recommendation")
        != "REMOVE"
    ):
        raise ValueError("public semantic ablation recommendation drifted")
    if (
        summary.get("datahub_context_recommendation", {}).get("recommendation")
        != "ADDS_VALUE"
    ):
        raise ValueError("public semantic ablation DataHub finding drifted")
    return summary


def _freeze_record(corpus_path: Path) -> dict[str, Any]:
    corpus = load_oracle_corpus(corpus_path)
    return with_digest(
        {
            "schema_version": "1.0.0",
            "experiment_id": corpus["experiment_id"],
            "frozen_at": corpus["frozen_at"],
            "corpus_file_digest": _file_digest(corpus_path),
            "corpus_semantic_digest": digest_json(corpus),
            "truth_digest": truth_digest(corpus),
            "scenario_count": len(corpus["scenarios"]),
            "scenario_identities": [item["id"] for item in corpus["scenarios"]],
            "live_model_outputs_observed_before_freeze": False,
        },
        "freeze_record_digest",
    )


def _verify_retained_shapes(corpus: Mapping[str, Any], root: Path) -> None:
    for record in corpus["retained_live_context_shapes"]:
        path = root / str(record["artifact"])
        if _file_digest(path) != record["file_sha256"]:
            raise ValueError(
                f"retained live context shape drifted: {record['artifact']}"
            )


def _load_digest_artifact(path: Path, field: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"invalid artifact: {path}")
    expected = value.get(field)
    unsigned = dict(value)
    unsigned.pop(field, None)
    if expected != digest_json(unsigned):
        raise ValueError(f"artifact digest mismatch: {path}")
    return value


def _file_digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
