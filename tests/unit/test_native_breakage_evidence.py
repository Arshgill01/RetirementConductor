from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from scripts.run_native_breakage_lab import canonical_json, digest_json

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "fixtures/native-breakage-lab/contract.json"
PUBLIC = ROOT / "artifacts/public/native-breakage-outcome-lab"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def verify(value: dict[str, Any], field: str) -> None:
    unsigned = dict(value)
    expected = unsigned.pop(field)
    assert expected == digest_json(unsigned)


def test_frozen_generator_matches_declared_safe_digests() -> None:
    contract = load(CONTRACT_PATH)
    generator = contract["generator"]
    statuses = tuple(contract["allowed_status_values"])
    producer_lines: list[str] = []
    workload_lines: list[str] = []
    for row_id in range(1, int(generator["row_count"]) + 1):
        status = statuses[(row_id * 17 + int(generator["seed"])) % len(statuses)]
        amount = (row_id * 137 + int(generator["seed"])) % 50000 + 100
        producer_lines.append(f"{row_id}|{status}|{status}|{amount}")
        workload_lines.append(f"{row_id}|{status.upper()}|{amount}")
    assert (
        "sha256:" + hashlib.sha256("\n".join(producer_lines).encode()).hexdigest()
        == contract["safe_digests"]["producer_whole_result"]
    )
    assert (
        "sha256:" + hashlib.sha256("\n".join(workload_lines).encode()).hexdigest()
        == contract["safe_digests"]["workload_semantic_result"]
    )


def test_schema_contract_digests_are_frozen() -> None:
    before = [
        {
            "ordinal_position": 1,
            "column_name": "id",
            "data_type": "integer",
            "is_nullable": "NO",
        },
        {
            "ordinal_position": 2,
            "column_name": "legacy_status",
            "data_type": "text",
            "is_nullable": "NO",
        },
        {
            "ordinal_position": 3,
            "column_name": "order_status",
            "data_type": "text",
            "is_nullable": "NO",
        },
        {
            "ordinal_position": 4,
            "column_name": "amount_cents",
            "data_type": "bigint",
            "is_nullable": "NO",
        },
    ]
    after = [before[0], before[2], before[3]]
    contract = load(CONTRACT_PATH)
    assert digest_json(before) == contract["schema_digests"]["before_drop"]
    assert digest_json(after) == contract["schema_digests"]["after_drop"]
    assert canonical_json(before) != canonical_json(after)


def test_public_native_breakage_evidence_is_bound_and_attributable() -> None:
    index = load(PUBLIC / "index.json")
    verify(index, "self_digest")
    assert index["result"] == "NATIVE_BREAKAGE_OUTCOME_LAB_PASSED"
    assert index["recommendation"] == "KEEP_SPARK"
    assert index["fallback_classification"] == "NOT_USED_SPARK_ACHIEVED"
    assert len(index["unsafe_action_runs"]) == 2
    assert index["schema_digests"]["before"] == index["schema_digests"]["reconstructed"]
    assert index["schema_digests"]["before"] != index["schema_digests"]["after"]
    assert index["missing_column_error"] == {
        "exit_code": 42,
        "missing_field": "legacy_status",
        "normalized_outcome": "LEGACY_COLUMN_MISSING",
        "sqlstate": "42703",
    }
    assert index["destructive_statement_count"] == 2
    for run_summary in index["unsafe_action_runs"]:
        assert run_summary["legacy_before"] == "SUCCEEDED"
        assert run_summary["legacy_after"] == "LEGACY_COLUMN_MISSING"
        assert (
            run_summary["replacement_before_digest"]
            == run_summary["replacement_after_digest"]
        )
    assert index["prevented_action"]["result"] == "UNSAFE_ACTION_PREVENTED"
    assert index["prevented_action"]["legacy"] == "SUCCEEDED"
    assert index["prevented_action"]["replacement"] == "SUCCEEDED"


def test_public_artifacts_have_valid_digests_and_no_private_payloads() -> None:
    paths = sorted(PUBLIC.glob("*.json"))
    assert {path.name for path in paths} == {
        "consumer-descriptor.json",
        "frozen-inputs.json",
        "index.json",
        "isolation.json",
        "prevented-control.json",
        "reconstruction.json",
        "unsafe-run-1.json",
        "unsafe-run-2.json",
    }
    forbidden = re.compile(
        r"(?:/home/|/Users/)|"
        r'(?i:"(?:password|token|secret|stderr|stdout|stacktrace|message)"\s*:)|'
        r'(?i:"(?:id|legacy_status|order_status|amount_cents)"\s*:)'
    )
    for path in paths:
        value = load(path)
        field = (
            "self_digest"
            if path.name == "index.json"
            else "descriptor_digest"
            if path.name == "consumer-descriptor.json"
            else "artifact_digest"
        )
        verify(value, field)
        assert forbidden.search(path.read_text(encoding="utf-8")) is None


def test_consumer_descriptor_is_a_handoff_not_lineage_evidence() -> None:
    descriptor = load(PUBLIC / "consumer-descriptor.json")
    verify(descriptor, "descriptor_digest")
    assert descriptor["workload"]["type"] == "Apache Spark batch over PostgreSQL JDBC"
    assert descriptor["producer"]["field_usage"]["field"] == "legacy_status"
    assert descriptor["observation"]["outcome"] == "SUCCEEDED"
    assert any(
        "not DataHub lineage evidence" in value for value in descriptor["limitations"]
    )
