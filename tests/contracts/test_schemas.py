from __future__ import annotations

from jsonschema import Draft202012Validator

from retirement_conductor.schemas import SCHEMA_FILENAMES, load_schema


def test_every_versioned_schema_is_valid_draft_2020_12() -> None:
    for name in sorted(SCHEMA_FILENAMES):
        Draft202012Validator.check_schema(load_schema(name))


def test_schema_set_covers_every_phase_zero_contract() -> None:
    assert set(SCHEMA_FILENAMES) >= {
        "retirement-spec",
        "evidence-envelope",
        "consumer-receipt",
        "campaign-manifest",
        "dataset-registry",
        "dataset-cache-receipt",
        "benchmark-oracle",
        "benchmark-fault-manifest",
        "benchmark-quality-report",
        "benchmark-generation-receipt",
    }
