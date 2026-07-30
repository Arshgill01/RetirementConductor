"""Load and execute the repository's versioned JSON Schemas."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from retirement_conductor.errors import Refusal
from retirement_conductor.vocabulary import RefusalCode

SCHEMA_FILENAMES = {
    "approval": "approval-v1.schema.json",
    "retirement-spec": "retirement-spec-v1alpha1.schema.json",
    "evidence-envelope": "evidence-envelope-v1.schema.json",
    "consumer-receipt": "consumer-receipt-v1.schema.json",
    "datahub-snapshot": "datahub-snapshot-v1.schema.json",
    "git-dbt-plan": "git-dbt-plan-v1.schema.json",
    "campaign-manifest": "campaign-manifest-v1.schema.json",
    "campaign-event": "campaign-event-v1.schema.json",
    "fixture-scenario": "fixture-scenario-v1.schema.json",
    "waiver": "waiver-v1.schema.json",
}


def schema_directory() -> Path:
    """Locate packaged schemas or schemas in a source checkout."""

    candidates = (
        Path(__file__).resolve().parent / "schemas",
        Path(__file__).resolve().parents[2] / "schemas",
    )
    for directory in candidates:
        if directory.is_dir():
            return directory
    raise RuntimeError("versioned schemas are unavailable")


def load_schema(name: str) -> dict[str, Any]:
    """Load one named schema."""

    import json

    try:
        filename = SCHEMA_FILENAMES[name]
    except KeyError as exc:
        raise ValueError(f"unknown schema: {name}") from exc
    value = json.loads((schema_directory() / filename).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"schema is not an object: {filename}")
    Draft202012Validator.check_schema(value)
    return value


def validate_schema(
    name: str,
    value: Any,
    *,
    refusal_code: str = RefusalCode.SPEC_SCHEMA_INVALID,
) -> None:
    """Validate a value and return a stable, bounded refusal."""

    validator = Draft202012Validator(load_schema(name))
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
    if not errors:
        return
    first = errors[0]
    instance_path = "/".join(str(part) for part in first.absolute_path) or "$"
    schema_path = "/".join(str(part) for part in first.absolute_schema_path)
    raise Refusal(
        refusal_code,
        "The input does not satisfy its versioned schema.",
        {
            "schema": name,
            "instance_path": instance_path,
            "schema_path": schema_path,
            "error": first.message,
            "error_count": len(errors),
        },
    )
