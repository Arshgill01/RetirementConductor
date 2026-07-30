"""Retirement specification parsing and semantic validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from retirement_conductor.canonical import digest_json
from retirement_conductor.errors import Refusal
from retirement_conductor.schemas import validate_schema
from retirement_conductor.vocabulary import RefusalCode

IDENTITY_COMPONENTS = ("platform", "instance", "database", "schema", "table")


def load_specification(path: Path) -> dict[str, Any]:
    """Parse and validate one specification without resolving secrets."""

    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise Refusal(
            RefusalCode.SPEC_PARSE_FAILED,
            "The retirement specification could not be parsed.",
            {"file": path.name, "error_type": type(exc).__name__},
        ) from exc
    if not isinstance(parsed, dict):
        raise Refusal(
            RefusalCode.SPEC_SCHEMA_INVALID,
            "The retirement specification must be a mapping.",
            {"file": path.name},
        )
    validate_schema("retirement-spec", parsed)
    validate_specification_semantics(parsed)
    normalized = dict(parsed)
    normalized["specification_digest"] = digest_json(parsed)
    return normalized


def validate_specification_semantics(specification: dict[str, Any]) -> None:
    """Apply cross-field rules that JSON Schema cannot express clearly."""

    target = specification["target"]
    replacement = specification["replacement"]
    if all(target[key] == replacement[key] for key in (*IDENTITY_COMPONENTS, "field")):
        raise Refusal(
            RefusalCode.SPEC_IDENTICAL_FIELDS,
            "The legacy and replacement fields must be different.",
        )
    changed_components = [
        key for key in IDENTITY_COMPONENTS if target[key] != replacement[key]
    ]
    if changed_components:
        raise Refusal(
            RefusalCode.SPEC_UNSUPPORTED_REPLACEMENT,
            "The initial contract supports a replacement on the same table only.",
            {"changed_identity_components": changed_components},
        )
