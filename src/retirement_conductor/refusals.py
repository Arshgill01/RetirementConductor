"""Stable refusal registry and family validation."""

from __future__ import annotations

from retirement_conductor.vocabulary import RefusalCode

ALLOWED_FAMILIES = {
    "APPLY",
    "AUTH",
    "COMPENSATION",
    "DATASET",
    "EVIDENCE",
    "GATE",
    "IDENTITY",
    "INTEGRITY",
    "POLICY",
    "RECONCILIATION",
    "RUNTIME",
    "SCOPE",
    "SOURCE",
    "SPEC",
    "VALIDATION",
}

REFUSAL_REGISTRY = {code.value: code.value.split("_", 1)[0] for code in RefusalCode}


def validate_refusal_registry() -> None:
    """Fail development checks if a code escapes the documented families."""

    invalid = {
        code: family
        for code, family in REFUSAL_REGISTRY.items()
        if family not in ALLOWED_FAMILIES
    }
    if invalid:
        raise RuntimeError(f"invalid refusal families: {invalid}")
